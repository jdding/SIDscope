#!/usr/bin/env python3
"""Prepare the frozen dormant-user protocol for official DiffGRM.

The command creates a private runtime manifest for the official model and a
public evaluator join.  It deliberately does not create semantic IDs: the
pinned DiffGRM tokenizer must generate OPQ4/256 over this exact catalog before
the SIDScope prepared contract is finalized.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import gzip
import hashlib
import hmac
import json
from pathlib import Path
import pickle
from typing import Any, Iterable

import numpy as np


DIFFGRM_REVISION = "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c"
RUNTIME_SCHEMA = "genrec_dormant.diffgrm_private_runtime.v1"
BUCKETS = ("short", "30-90d", "90-180d", "180-365d", ">365d")
RIGOR_TO_PUBLIC = {
    "le_30d": "short",
    "30_90d": "30-90d",
    "90_180d": "90-180d",
    "180_365d": "180-365d",
    "gt_365d": ">365d",
}
INDEX_TO_PUBLIC = {
    0: "short",
    1: "30-90d",
    2: "90-180d",
    3: "180-365d",
    4: ">365d",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pseudonym(key: bytes, namespace: str, value: str) -> str:
    digest = hmac.new(key, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()
    return f"{namespace}-{digest[:24]}"


def load_train_surface(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = pickle.load(stream)
    if not isinstance(value, dict) or "test_samples" in value:
        raise ValueError("invalid or contaminated train-only surface")
    required = {"train_samples", "idx_to_item", "item_vocab_size"}
    if not required.issubset(value):
        raise ValueError("train-only surface lacks required fields")
    return value


def _metadata_rows(path: Path) -> Iterable[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        first = stream.read(1)
        stream.seek(0)
        if first in "[{":
            try:
                payload = json.load(stream)
            except json.JSONDecodeError:
                stream.seek(0)
            else:
                if isinstance(payload, dict):
                    for item_id, value in payload.items():
                        if isinstance(value, dict):
                            yield {"asin": item_id, **value}
                        else:
                            yield {"asin": item_id, "title": value}
                    return
                if isinstance(payload, list):
                    yield from payload
                    return
        for line in stream:
            line = line.strip()
            if line:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    try:
                        row = ast.literal_eval(line)
                    except (SyntaxError, ValueError) as exc:
                        raise ValueError("metadata line is neither JSON nor a Python literal") from exc
                if not isinstance(row, dict):
                    raise ValueError("metadata line must contain an object")
                yield row


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if value is None:
        return ""
    return str(value)


def load_metadata(path: Path, required_ids: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in _metadata_rows(path):
        item_id = str(row.get("asin") or row.get("item_id") or row.get("id") or "")
        if item_id not in required_ids:
            continue
        parts = [
            _text(row.get("title")),
            _text(row.get("brand")),
            _text(row.get("category") or row.get("categories")),
            _text(row.get("description")),
        ]
        text = " ".join(part.strip() for part in parts if part.strip())
        result[item_id] = text or "unknown item"
    missing = required_ids - set(result)
    if missing:
        sample = sorted(missing)[:5]
        raise ValueError(f"metadata misses {len(missing)} catalog items; sample={sample}")
    return result


def load_test_protocol(protocol: Any) -> tuple[np.ndarray, ...]:
    if "episode_id" in protocol.files:
        required = {
            "episode_id", "history_offsets", "history_item_idx", "target_idx",
            "gap_days", "gap_bucket",
        }
        missing = required.difference(protocol.files)
        if missing:
            raise ValueError(f"exported evaluator protocol misses {sorted(missing)}")
        episode_ids = np.asarray(protocol["episode_id"]).astype(np.str_)
        offsets = np.asarray(protocol["history_offsets"], dtype=np.int64)
        histories = np.asarray(protocol["history_item_idx"], dtype=np.int64)
        targets = np.asarray(protocol["target_idx"], dtype=np.int64)
        gaps = np.asarray(protocol["gap_days"], dtype=np.float32)
        raw_buckets = np.asarray(protocol["gap_bucket"]).astype(np.str_)
        buckets = np.asarray([RIGOR_TO_PUBLIC[str(value)] for value in raw_buckets])
    elif "test_user_id" in protocol.files:
        required = {
            "test_user_id", "test_seq_offsets", "test_seq_values", "test_target_idx",
            "test_gap_days", "test_bucket",
        }
        missing = required.difference(protocol.files)
        if missing:
            raise ValueError(f"frozen split protocol misses {sorted(missing)}")
        episode_ids = np.asarray(protocol["test_user_id"]).astype(np.str_)
        offsets = np.asarray(protocol["test_seq_offsets"], dtype=np.int64)
        histories = np.asarray(protocol["test_seq_values"], dtype=np.int64)
        targets = np.asarray(protocol["test_target_idx"], dtype=np.int64)
        gaps = np.asarray(protocol["test_gap_days"], dtype=np.float32)
        raw_buckets = np.asarray(protocol["test_bucket"], dtype=np.int64)
        try:
            buckets = np.asarray([INDEX_TO_PUBLIC[int(value)] for value in raw_buckets])
        except KeyError as exc:
            raise ValueError("frozen split protocol contains an unknown bucket index") from exc
    else:
        raise ValueError("unsupported DiffGRM test protocol schema")
    rows = len(episode_ids)
    if any(len(value) != rows for value in (targets, gaps, buckets)):
        raise ValueError("DiffGRM test protocol row arrays differ in length")
    if len(offsets) != rows + 1 or offsets[0] != 0 or offsets[-1] != len(histories):
        raise ValueError("DiffGRM test protocol offsets are invalid")
    if np.any(offsets[1:] < offsets[:-1]):
        raise ValueError("DiffGRM test protocol offsets are not monotone")
    if len(set(episode_ids.tolist())) != rows:
        raise ValueError("DiffGRM test protocol episode identity is not unique")
    return episode_ids, offsets, histories, targets, gaps, buckets


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    hmac_key = args.hmac_key_file.read_bytes()
    if len(hmac_key) < 32:
        raise ValueError("HMAC key must contain at least 32 bytes")
    surface = load_train_surface(args.train_only_pickle)
    idx_to_item = {int(key): str(value) for key, value in surface["idx_to_item"].items()}
    if args.expected_train_only_sha256 and sha256_file(args.train_only_pickle) != args.expected_train_only_sha256:
        raise ValueError("train-only surface SHA-256 mismatch")
    if args.expected_protocol_sha256 and sha256_file(args.protocol_npz) != args.expected_protocol_sha256:
        raise ValueError("frozen protocol SHA-256 mismatch")

    compact_observed = surface.get("train_observed_indices")
    observed: set[int] = set()
    if compact_observed is not None:
        if not isinstance(compact_observed, list):
            raise ValueError("train_observed_indices must be a list")
        observed = {int(value) for value in compact_observed}
        if len(observed) != len(compact_observed):
            raise ValueError("train_observed_indices contains duplicates")
        if any(value not in idx_to_item for value in observed):
            raise ValueError("train_observed_indices is outside the source catalog")
    latest_by_user: dict[str, dict[str, Any]] = {}
    for row in surface["train_samples"]:
        indices = [int(value) for value in row["seq_idx"]] + [int(row["target_idx"])]
        if compact_observed is None:
            observed.update(indices)
        user = str(row["user_id"])
        if user not in latest_by_user or int(row["target_timestamp"]) > int(latest_by_user[user]["target_timestamp"]):
            latest_by_user[user] = row
    observed_indices = sorted(observed)
    normalized_by_source = {source: index for index, source in enumerate(observed_indices)}
    source_ids = {idx_to_item[index] for index in observed_indices}
    if args.embedding_source is not None:
        embedding_rows = args.embedding_source.stat().st_size // (args.embedding_dim * 4)
        if args.embedding_source.stat().st_size % (args.embedding_dim * 4):
            raise ValueError("precomputed embedding size is not divisible by its width")
        if embedding_rows != len(observed_indices):
            raise ValueError(
                f"precomputed embedding rows {embedding_rows} differ from catalog {len(observed_indices)}"
            )
        metadata = {item: "precomputed sentence-t5 embedding" for item in source_ids}
    else:
        metadata = load_metadata(args.metadata, source_ids)
    runtime_key = {
        source: pseudonym(hmac_key, "item", f"{args.domain}:{idx_to_item[source]}")
        for source in observed_indices
    }

    catalog = [
        {
            "normalized_item_id": f"n{normalized_by_source[source]:08d}",
            "runtime_item_key": runtime_key[source],
            "metadata_text": metadata[idx_to_item[source]],
        }
        for source in observed_indices
    ]

    train: list[dict[str, Any]] = []
    val: list[dict[str, Any]] = []
    for user, row in sorted(latest_by_user.items()):
        sequence = [int(value) for value in row["seq_idx"]] + [int(row["target_idx"])]
        if len(sequence) < 3 or any(item not in normalized_by_source for item in sequence):
            continue
        episode = pseudonym(hmac_key, "episode", f"{args.domain}:inner:{user}")
        if len(sequence[:-2]) >= 2:
            train.append({"episode_id": f"{episode}-train", "item_seq": [runtime_key[item] for item in sequence[:-2]]})
        val.append({"episode_id": f"{episode}-validation", "item_seq": [runtime_key[item] for item in sequence[:-1]]})

    with np.load(args.protocol_npz, allow_pickle=False) as protocol:
        episode_ids, offsets, histories, targets, gaps, buckets = load_test_protocol(protocol)
    test: list[dict[str, Any]] = []
    evaluator: list[dict[str, Any]] = []
    counts = Counter()
    for row_index, source_episode in enumerate(episode_ids):
        bucket = str(buckets[row_index])
        counts[bucket] += 1
        history = [int(value) for value in histories[int(offsets[row_index]):int(offsets[row_index + 1])]]
        if any(item not in normalized_by_source for item in history):
            raise ValueError("frozen test history is outside train-observed catalog")
        target = int(targets[row_index])
        episode = pseudonym(hmac_key, "episode", f"{args.domain}:test:{source_episode}")
        reachable = target in normalized_by_source
        prepared_index = None
        normalized_target = None
        if reachable:
            prepared_index = len(test)
            normalized_target = f"n{normalized_by_source[target]:08d}"
            test.append({"episode_id": episode, "item_seq": [runtime_key[item] for item in history] + [runtime_key[target]]})
        evaluator.append({
            "episode_id": episode,
            "source_protocol_row_index": row_index,
            "prepared_test_split_row_index": prepared_index,
            "target_normalized_item_id": normalized_target,
            "catalog_reachable": reachable,
            "gap_bucket": bucket,
            "gap_days": float(gaps[row_index]),
        })

    if not train or not val or not test:
        raise ValueError("prepared DiffGRM splits must be non-empty")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    runtime = {
        "schema": RUNTIME_SCHEMA,
        "domain": args.domain,
        "source_revision": DIFFGRM_REVISION,
        "catalog": catalog,
        "splits": {"train": train, "val": val, "test": test},
        "bindings": {
            "train_only_sha256": sha256_file(args.train_only_pickle),
            "protocol_sha256": sha256_file(args.protocol_npz),
            "metadata_sha256": sha256_file(args.metadata) if args.metadata else None,
            "precomputed_embedding_sha256": (
                sha256_file(args.embedding_source) if args.embedding_source else None
            ),
        },
    }
    runtime_path = args.output_dir / "runtime_private.json"
    join_path = args.output_dir / "evaluation_join.json"
    write_json(runtime_path, runtime)
    write_json(join_path, {
        "schema": "genrec_dormant.diffgrm_evaluator_join.v1",
        "runtime_manifest_sha256": canonical_hash(runtime),
        "rows": evaluator,
    })
    report = {
        "schema": "genrec_dormant.diffgrm_protocol_preflight.v1",
        "status": "pass",
        "source_revision": DIFFGRM_REVISION,
        "counts": {
            "catalog": len(catalog), "train": len(train), "validation": len(val),
            "test_reachable": len(test), "test_full": len(evaluator),
            "test_unreachable": len(evaluator) - len(test),
            "bucket_counts": {bucket: counts[bucket] for bucket in BUCKETS},
        },
        "output_sha256": {
            "runtime_private": sha256_file(runtime_path),
            "evaluation_join": sha256_file(join_path),
        },
        "privacy": {"source_item_ids_exported": 0, "raw_user_ids_exported": 0, "dormancy_fields_in_generator_input": 0},
        "next_gate": "official DiffGRM OPQ4 generation and CPU runtime construction",
    }
    write_json(args.output_dir / "preflight_manifest.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--train-only-pickle", type=Path, required=True)
    parser.add_argument("--protocol-npz", type=Path, required=True)
    metadata_group = parser.add_mutually_exclusive_group(required=True)
    metadata_group.add_argument("--metadata", type=Path)
    metadata_group.add_argument("--embedding-source", type=Path)
    parser.add_argument("--embedding-dim", type=int, default=768)
    parser.add_argument("--hmac-key-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-train-only-sha256")
    parser.add_argument("--expected-protocol-sha256")
    return parser.parse_args()


def main() -> None:
    print(json.dumps(prepare(parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
