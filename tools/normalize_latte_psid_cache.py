#!/usr/bin/env python3
"""Normalize one frozen Latte/PSID processed cache into SIDScope tables."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sidinspector.adapters.latte import (
    latte_vocabulary_tokens,
    normalize_latte_interactions,
    normalize_latte_metadata,
    normalize_latte_sem_ids,
    psid_vocabulary_tokens,
    read_latte_item_mapping,
    read_sem_ids_cache,
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
    parser.add_argument("--dataset", default="musical_instruments")
    parser.add_argument("--category", default="Musical_Instruments")
    parser.add_argument("--method", default="latte_psid_rqkmeans_official_code_derived")
    parser.add_argument("--vq-method", default="rqkmeans")
    parser.add_argument("--n-codebooks", type=int, default=3)
    parser.add_argument("--codebook-size", type=int, default=256)
    parser.add_argument(
        "--sem-ids-filename", default="sentence-t5-base_rqkmeans_3x256_psid.sem_ids"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mapping = args.processed_dir / "id_mapping.json"
    sem_ids = args.processed_dir / args.sem_ids_filename
    metadata_source = args.processed_dir / "metadata.sentence.json"
    sequences = args.processed_dir / "all_item_seqs.json"
    sid = normalize_latte_sem_ids(
        sem_ids,
        mapping,
        method=args.method,
        dataset=args.dataset,
        vq_method=args.vq_method,
        n_codebooks=args.n_codebooks,
        codebook_size=args.codebook_size,
    )
    metadata = normalize_latte_metadata(
        mapping,
        dataset=args.dataset,
        category=args.category,
        metadata_path=metadata_source,
    )
    interactions = normalize_latte_interactions(sequences, mapping, dataset=args.dataset)
    identities = read_latte_item_mapping(mapping)
    cache = read_sem_ids_cache(
        sem_ids,
        expected_source_items=(item.source_item_id for item in identities),
        n_codebooks=args.n_codebooks,
        codebook_size=args.codebook_size,
    )
    psid_reverse = {
        psid_vocabulary_tokens(codes, args.codebook_size): source_item_id
        for source_item_id, codes in cache.items()
    }
    latte_reverse = {
        latte_vocabulary_tokens(codes, args.codebook_size, 8): source_item_id
        for source_item_id, codes in cache.items()
    }
    if len(psid_reverse) != len(cache) or len(latte_reverse) != len(cache):
        raise RuntimeError("model-vocabulary round-trip is not conflict-free")
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
    result = {
        "schema": "sidscope.latte_psid_normalized_intake.v1",
        "status": "pass",
        "method": args.method,
        "dataset": args.dataset,
        "source_cache_sha256": sha256(sem_ids),
        "input_sha256": {name: sha256(path) for name, path in paths.items()},
        "rows": {
            "sid_assignments": len(sid),
            "item_metadata": len(metadata),
            "interactions": len(interactions),
        },
        "roundtrip": {
            "checked_items": len(cache),
            "source_to_normalized_item": "pass",
            "normalized_item_to_sid": "pass",
            "sid_to_psid_vocabulary_to_source_item": "pass",
            "sid_to_latte_vocabulary_to_source_item": "pass",
            "psid_vocabulary_unique_items": len(psid_reverse),
            "latte_vocabulary_unique_items": len(latte_reverse),
            "latte_n_latent_tokens": 8,
        },
        "preflight": preflight,
        "redistribution": "normalized tables remain external; only hashes, counts, and bounded diagnostics are public",
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
