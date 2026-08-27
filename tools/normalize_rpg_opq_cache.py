#!/usr/bin/env python3
"""Normalize one frozen official-code-derived RPG OPQ cache."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from sidinspector.adapters.rpg import (
    model_vocabulary_tokens,
    normalize_rpg_interactions,
    normalize_rpg_metadata,
    normalize_rpg_sem_ids,
    read_rpg_item_mapping,
    read_rpg_sem_ids,
)
from sidinspector.preflight import preflight_inputs


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--dataset", default="beauty")
    parser.add_argument("--category", default="Beauty")
    parser.add_argument("--method", default="rpg_opq_official_code_derived")
    parser.add_argument("--n-codebooks", type=int, default=32)
    parser.add_argument("--codebook-size", type=int, default=256)
    parser.add_argument(
        "--sem-ids-filename", default="sentence-t5-base_OPQ32,IVF1,PQ32x8.sem_ids"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mapping = args.processed_dir / "id_mapping.json"
    sem_ids = args.processed_dir / args.sem_ids_filename
    sequences = args.processed_dir / "all_item_seqs.json"
    sid = normalize_rpg_sem_ids(
        sem_ids,
        mapping,
        method=args.method,
        dataset=args.dataset,
        n_codebooks=args.n_codebooks,
        codebook_size=args.codebook_size,
    )
    metadata = normalize_rpg_metadata(mapping, dataset=args.dataset, category=args.category)
    interactions = normalize_rpg_interactions(sequences, mapping, dataset=args.dataset)
    identities = read_rpg_item_mapping(mapping)
    cache = read_rpg_sem_ids(
        sem_ids,
        expected_source_items=(item.source_item_id for item in identities),
        n_codebooks=args.n_codebooks,
        codebook_size=args.codebook_size,
    )
    reverse: dict[tuple[int, ...], list[int]] = defaultdict(list)
    source_to_node = {item.source_item_id: item.rpg_item_node_id for item in identities}
    for source_item_id, codes in cache.items():
        reverse[model_vocabulary_tokens(codes, args.codebook_size)].append(
            source_to_node[source_item_id]
        )
    collisions = [nodes for nodes in reverse.values() if len(nodes) > 1]

    paths = {
        "sid_assignments": args.output_dir / "sid_assignments.parquet",
        "item_metadata": args.output_dir / "item_metadata.parquet",
        "interactions": args.output_dir / "interactions.parquet",
    }
    sid.to_parquet(paths["sid_assignments"], index=False)
    metadata.to_parquet(paths["item_metadata"], index=False)
    interactions.to_parquet(paths["interactions"], index=False)
    preflight = preflight_inputs(
        paths["sid_assignments"],
        paths["item_metadata"],
        paths["interactions"],
        run_metric_smoke=True,
        max_metric_items=50_000,
        top_k=5,
        max_pair_events=10_000,
        max_user_items=50,
    )
    for table in preflight["tables"].values():
        table.pop("path", None)
        table["availability"] = "summary_only_raw_not_redistributed"
    result = {
        "schema": "sidscope.rpg_opq_normalized_intake.v1",
        "status": "pass",
        "method": args.method,
        "dataset": args.dataset,
        "configuration": {
            "n_codebooks": args.n_codebooks,
            "codebook_size": args.codebook_size,
            "split": "leave_one_out",
            "identity": "unordered_codebook_disjoint_token_set",
        },
        "source_sha256": {
            "id_mapping.json": sha256(mapping),
            "all_item_seqs.json": sha256(sequences),
            args.sem_ids_filename: sha256(sem_ids),
        },
        "normalized_sha256": {name: sha256(path) for name, path in paths.items()},
        "rows": {
            "sid_assignments": len(sid),
            "item_metadata": len(metadata),
            "interactions": len(interactions),
        },
        "split_rows": {
            str(key): int(value) for key, value in interactions["split"].value_counts().items()
        },
        "roundtrip": {
            "checked_items": len(cache),
            "source_item_to_normalized_item": "pass",
            "normalized_item_to_sid": "pass",
            "sid_to_model_vocabulary": "pass",
            "model_vocabulary_to_item_nodes": "pass",
            "unique_unordered_token_sets": len(reverse),
            "colliding_token_set_count": len(collisions),
            "items_in_collision_groups": sum(len(nodes) for nodes in collisions),
            "maximum_collision_group_size": max(map(len, collisions), default=1),
            "collision_policy": "retain every item node; do not collapse token-set collisions",
        },
        "preflight": preflight,
        "redistribution": "normalized tables and upstream assets remain external; only hashes, counts, and bounded diagnostics are public",
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
