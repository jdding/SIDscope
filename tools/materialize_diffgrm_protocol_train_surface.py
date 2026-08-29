#!/usr/bin/env python3
"""Materialize a compact train-only DiffGRM surface from a frozen NPZ protocol.

The DiffGRM prepared-data bridge consumes only the latest training row per
user.  This command extracts exactly that consumer-equivalent surface without
reading validation or test arrays and records the reduction explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
from typing import Any

import numpy as np


SCHEMA = "sidscope.diffgrm_train_surface_materialization.v1"
REQUIRED_TRAIN_KEYS = {
    "train_user_id",
    "train_target_idx",
    "train_seq_offsets",
    "train_seq_values",
    "item_num",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_inverse_vocab(path: Path, catalog_rows: int) -> dict[int, str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    raw_to_index = value.get("raw_to_index") if isinstance(value, dict) else None
    if not isinstance(raw_to_index, dict) or int(value.get("padding_id", -1)) != 0:
        raise ValueError("item vocabulary must contain raw_to_index and padding_id=0")
    inverse = {int(index): str(raw) for raw, index in raw_to_index.items()}
    if len(inverse) != len(raw_to_index):
        raise ValueError("item vocabulary maps multiple raw IDs to one index")
    if set(inverse) != set(range(1, catalog_rows + 1)):
        raise ValueError("item vocabulary must be dense and 1-based")
    return inverse


def materialize(protocol_path: Path, vocab_path: Path, output_path: Path) -> dict[str, Any]:
    with np.load(protocol_path, allow_pickle=False) as protocol:
        missing = REQUIRED_TRAIN_KEYS.difference(protocol.files)
        if missing:
            raise ValueError(f"frozen protocol misses train fields: {sorted(missing)}")
        users = np.asarray(protocol["train_user_id"], dtype=np.int64)
        targets = np.asarray(protocol["train_target_idx"], dtype=np.int64)
        offsets = np.asarray(protocol["train_seq_offsets"], dtype=np.int64)
        sequences = np.asarray(protocol["train_seq_values"], dtype=np.int64)
        item_num_value = np.asarray(protocol["item_num"], dtype=np.int64).reshape(-1)
    if len(item_num_value) != 1 or int(item_num_value[0]) <= 0:
        raise ValueError("protocol item_num must be one positive scalar")
    protocol_item_num = int(item_num_value[0])
    catalog_rows = protocol_item_num - 1
    if catalog_rows <= 0:
        raise ValueError("protocol item_num must include padding plus catalog rows")
    if len(users) == 0 or len(targets) != len(users) or len(offsets) != len(users) + 1:
        raise ValueError("protocol train arrays have inconsistent lengths")
    if offsets[0] != 0 or offsets[-1] != len(sequences) or np.any(offsets[1:] < offsets[:-1]):
        raise ValueError("protocol train sequence offsets are invalid")
    if np.any(targets < 1) or np.any(targets > catalog_rows):
        raise ValueError("protocol train target is outside the dense catalog")
    if np.any(sequences < 1) or np.any(sequences > catalog_rows):
        raise ValueError("protocol train history is outside the dense catalog")
    inverse = _load_inverse_vocab(vocab_path, catalog_rows)

    last_row_by_user: dict[int, int] = {}
    closed_users: set[int] = set()
    previous_user: int | None = None
    for row_index, raw_user in enumerate(users):
        user = int(raw_user)
        if previous_user is not None and user != previous_user:
            closed_users.add(previous_user)
        if user in closed_users:
            raise ValueError("protocol train rows are not contiguous by user")
        last_row_by_user[user] = row_index
        previous_user = user

    train_samples: list[dict[str, Any]] = []
    for user, row_index in sorted(last_row_by_user.items()):
        start = int(offsets[row_index])
        stop = int(offsets[row_index + 1])
        history = [int(value) for value in sequences[start:stop]]
        if not history:
            raise ValueError("latest train row has an empty history")
        train_samples.append(
            {
                "user_id": str(user),
                "seq_idx": history,
                "target_idx": int(targets[row_index]),
                "target_timestamp": row_index,
            }
        )

    surface = {
        "train_samples": train_samples,
        "train_observed_indices": sorted(
            {int(value) for value in sequences}.union(int(value) for value in targets)
        ),
        "idx_to_item": inverse,
        "item_vocab_size": catalog_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        pickle.dump(surface, stream, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(temporary, output_path)
    return {
        "schema": SCHEMA,
        "status": "pass",
        "protocol_sha256": sha256_file(protocol_path),
        "item_vocab_sha256": sha256_file(vocab_path),
        "output_sha256": sha256_file(output_path),
        "source_train_rows": len(users),
        "consumer_train_rows": len(train_samples),
        "protocol_item_num_including_padding": protocol_item_num,
        "catalog_rows": catalog_rows,
        "selection": "last_contiguous_train_row_per_user",
        "consumer_equivalence": "prepare_diffgrm_protocol_latest_by_user",
        "catalog_equivalence": "union_of_all_train_history_and_target_indices",
        "validation_arrays_read": False,
        "test_arrays_read": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--item-vocab", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256")
    parser.add_argument("--expected-item-vocab-sha256")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.expected_protocol_sha256 and sha256_file(args.protocol) != args.expected_protocol_sha256:
        raise ValueError("frozen protocol SHA-256 mismatch")
    if args.expected_item_vocab_sha256 and sha256_file(args.item_vocab) != args.expected_item_vocab_sha256:
        raise ValueError("item vocabulary SHA-256 mismatch")
    result = materialize(args.protocol, args.item_vocab, args.output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
