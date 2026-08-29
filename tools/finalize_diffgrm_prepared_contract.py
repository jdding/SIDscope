#!/usr/bin/env python3
"""Finalize SIDScope DiffGRM manifests after official OPQ4 generation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


BUCKETS = ("short", "30-90d", "90-180d", "180-365d", ">365d")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    runtime = load(args.runtime_manifest)
    join = load(args.evaluation_join)
    sid = load(args.semantic_ids)
    if runtime.get("schema") != "genrec_dormant.diffgrm_private_runtime.v1":
        raise ValueError("runtime schema mismatch")
    if join.get("runtime_manifest_sha256") != canonical_hash(runtime):
        raise ValueError("evaluator join is not bound to runtime")
    by_key = {str(row["runtime_item_key"]): row for row in runtime["catalog"]}
    if set(sid) != set(by_key):
        raise ValueError("official SID cache does not equal frozen runtime catalog")
    catalog = []
    for runtime_key, row in sorted(by_key.items(), key=lambda pair: pair[1]["normalized_item_id"]):
        codes = [int(value) for value in sid[runtime_key]]
        if len(codes) != 4 or any(not 0 <= value < 256 for value in codes):
            raise ValueError("official DiffGRM SID must be OPQ4/256")
        catalog.append({
            "normalized_item_id": str(row["normalized_item_id"]),
            "semantic_codes": codes,
            "model_vocabulary_tokens": [code + 3 + position * 256 for position, code in enumerate(codes)],
        })
    runtime_to_normalized = {
        str(row["runtime_item_key"]): str(row["normalized_item_id"])
        for row in runtime["catalog"]
    }
    episode_index = [
        {
            "episode_id": str(row["episode_id"]),
            "split": "test",
            "target_normalized_item_id": runtime_to_normalized[row["item_seq"][-1]],
            "catalog_reachable": True,
        }
        for row in runtime["splits"]["test"]
    ]
    prepared = {
        "schema": "sidscope.diffgrm_prepared_dataset.v1",
        "route_id": "diffgrm_www2026",
        "dataset": "DormantFirstReturn",
        "category": str(runtime["domain"]),
        "profile": "frozen_train_only_plus_rigor_original_test_v1",
        "split_sha256": {
            split: canonical_hash(runtime["splits"][split]) for split in ("train", "val", "test")
        } | {"validation": canonical_hash(runtime["splits"]["val"])},
        "train_observed_catalog_count": len(catalog),
        "train_observed_catalog_sha256": canonical_hash(
            [row["normalized_item_id"] for row in catalog]
        ),
        "canonical_target_universe_sha256": canonical_hash(catalog),
        "source_item_ids_exported": False,
        "dormancy_fields_in_generator_input": False,
        "sid_contract": {
            "n_digit": 4, "codebook_size": 256, "pad_token": 0, "bos_token": 1,
            "eos_token": 2, "mask_token": -1, "sid_offset": 3,
            "position_disjoint_vocabulary": True, "quantizer": "opq_pq",
            "index_factory": "OPQ4,IVF1,PQ4x8",
            "dedup_semantics": "preserve_all_item_collisions",
            "tokenizer_factor": "official_diffgrm_opq4_separately_frozen",
        },
        "episode_index": episode_index,
        "catalog": catalog,
    }
    # The verifier expects only train/validation/test names.
    prepared["split_sha256"].pop("val")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prepared_path = args.output_dir / "prepared_dataset.json"
    write(prepared_path, prepared)
    join_by_episode = {str(row["episode_id"]): row for row in join["rows"] if row["catalog_reachable"]}
    indexed = {row["episode_id"]: row for row in episode_index}
    selection_hashes: dict[str, str] = {}
    for per_bucket in args.episodes_per_bucket:
        if per_bucket <= 0:
            raise ValueError("episodes per bucket must be positive")
        selected = []
        for bucket in BUCKETS:
            candidates = []
            for episode_id, evaluator in join_by_episode.items():
                if evaluator["gap_bucket"] != bucket:
                    continue
                rank = hashlib.sha256(f"{args.selection_seed}:{episode_id}".encode()).hexdigest()
                candidates.append((rank, episode_id, evaluator))
            for _, episode_id, evaluator in sorted(candidates)[:per_bucket]:
                selected.append({
                    "selection_ordinal": len(selected) + 1,
                    "episode_id": episode_id,
                    "split": "test",
                    "target_normalized_item_id": indexed[episode_id]["target_normalized_item_id"],
                    "gap_bucket": evaluator["gap_bucket"],
                    "generator_input_contains_bucket_or_label": False,
                })
            if sum(row["gap_bucket"] == bucket for row in selected) != per_bucket:
                raise ValueError(f"DiffGRM bucket {bucket} lacks {per_bucket} eligible episodes")
        selection = {
            "schema": "sidscope.diffgrm_episode_selection.v1",
            "route_id": "diffgrm_www2026",
            "prepared_dataset_contract_sha256": canonical_hash(prepared),
            "selection_policy": f"sha256_ranked_episode_id_within_bucket_seed{args.selection_seed}",
            "first_n_fallback_allowed": False,
            "episodes": selected,
        }
        path = args.output_dir / f"episode_selection_{per_bucket}pb.json"
        write(path, selection)
        selection_hashes[str(per_bucket)] = sha256_file(path)
    report = {
        "schema": "genrec_dormant.diffgrm_prepared_finalization.v1",
        "status": "pass",
        "source_revision": runtime["source_revision"],
        "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
        "semantic_id_cache_sha256": sha256_file(args.semantic_ids),
        "prepared_dataset_sha256": sha256_file(prepared_path),
        "catalog_rows": len(catalog),
        "collision_excess": len(catalog) - len({tuple(row["semantic_codes"]) for row in catalog}),
        "selection_sha256": selection_hashes,
        "next_gate": "official SIDScope prepared/selection validation and checkpoint-bound smoke",
    }
    write(args.output_dir / "finalization_manifest.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--evaluation-join", type=Path, required=True)
    parser.add_argument("--semantic-ids", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--selection-seed", type=int, default=20240828)
    parser.add_argument("--episodes-per-bucket", type=int, nargs="+", default=[1, 50])
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(finalize(parse_args()), indent=2, sort_keys=True))
