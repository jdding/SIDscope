#!/usr/bin/env python3
"""Finalize LLaDA-Rec prepared/selection contracts from a frozen split."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_REVISION = "83dbcd6061da9266adcd8f68b16d1de7cc2612f3"


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    base = load(args.base_prepared)
    semantic = load(args.semantic_ids)
    tokenizer_manifest = load(args.tokenizer_training_manifest)
    if base.get("schema") != "sidscope.diffgrm_prepared_dataset.v1":
        raise ValueError("LLaDA-Rec base prepared schema mismatch")
    if (
        tokenizer_manifest.get("schema")
        != "sidscope.llada_rec_tokenizer_training.v1"
        or tokenizer_manifest.get("status") != "pass"
        or tokenizer_manifest.get("semantic_ids_sha256")
        != sha256_file(args.semantic_ids)
    ):
        raise ValueError("LLaDA-Rec formal tokenizer manifest mismatch")
    normalized = [str(row["normalized_item_id"]) for row in base.get("catalog", [])]
    if len(normalized) != len(set(normalized)) or set(normalized) != set(semantic):
        raise ValueError("LLaDA-Rec semantic IDs do not equal the frozen catalog")

    catalog = []
    for normalized_id in normalized:
        codes = semantic[normalized_id]
        if (
            not isinstance(codes, list)
            or len(codes) != 4
            or any(not isinstance(code, int) or code < 0 or code >= 256 for code in codes)
        ):
            raise ValueError("LLaDA-Rec semantic ID violates the 4x256 contract")
        catalog.append({
            "normalized_item_id": normalized_id,
            "semantic_codes": list(codes),
            "model_vocabulary_tokens": [
                int(code) + position * 256 + 1
                for position, code in enumerate(codes)
            ],
        })

    prepared = {
        "schema": "sidscope.llada_rec_prepared_dataset.v1",
        "route_id": "llada_rec",
        "dataset": base["dataset"],
        "category": base["category"],
        "profile": base["profile"],
        "source_revision": SOURCE_REVISION,
        "split_sha256": base["split_sha256"],
        "train_observed_catalog_count": len(catalog),
        "train_observed_catalog_sha256": canonical_hash(normalized),
        "canonical_target_universe_sha256": canonical_hash(catalog),
        "source_item_ids_exported": False,
        "dormancy_fields_in_generator_input": False,
        "tokenizer_training_manifest_sha256": sha256_file(
            args.tokenizer_training_manifest
        ),
        "semantic_ids_sha256": sha256_file(args.semantic_ids),
        "sid_contract": {
            "n_digit": 4,
            "codebook_sizes": [256, 256, 256, 256],
            "pad_token": 0,
            "eos_token": 1025,
            "mask_token": 1026,
            "position_offsets_plus_padding": [1, 257, 513, 769],
            "position_disjoint_vocabulary": True,
            "quantizer": "official_multihead_vqvae_pca128_whitened",
            "dedup_semantics": "preserve_all_item_collisions",
            "tokenizer_factor": "official_llada_rec_project_bound_separately_frozen",
        },
        "episode_index": base["episode_index"],
        "catalog": catalog,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prepared_path = args.output_dir / "prepared_dataset.json"
    write(prepared_path, prepared)

    base_hash = canonical_hash(base)
    selection_hashes: dict[str, str] = {}
    for input_path in args.base_selection:
        selection = load(input_path)
        if selection.get("schema") != "sidscope.diffgrm_episode_selection.v1":
            raise ValueError("LLaDA-Rec base selection schema mismatch")
        if selection.get("prepared_dataset_contract_sha256") != base_hash:
            raise ValueError("LLaDA-Rec base selection binding mismatch")
        episodes = selection.get("episodes", [])
        ordinals = [int(row["selection_ordinal"]) for row in episodes]
        if ordinals != list(range(1, len(episodes) + 1)):
            raise ValueError("LLaDA-Rec selection ordinals are not contiguous")
        output = {
            "schema": "sidscope.llada_rec_episode_selection.v1",
            "route_id": "llada_rec",
            "prepared_dataset_contract_sha256": canonical_hash(prepared),
            "selection_policy": selection["selection_policy"],
            "first_n_fallback_allowed": False,
            "episodes": episodes,
        }
        output_path = args.output_dir / input_path.name
        write(output_path, output)
        selection_hashes[input_path.name] = sha256_file(output_path)

    collision_excess = len(catalog) - len(
        {tuple(row["semantic_codes"]) for row in catalog}
    )
    report = {
        "schema": "sidscope.llada_rec_prepared_finalization.v1",
        "status": "pass",
        "source_revision": SOURCE_REVISION,
        "base_prepared_sha256": sha256_file(args.base_prepared),
        "tokenizer_training_manifest_sha256": sha256_file(
            args.tokenizer_training_manifest
        ),
        "semantic_ids_sha256": sha256_file(args.semantic_ids),
        "prepared_dataset_sha256": sha256_file(prepared_path),
        "prepared_dataset_contract_sha256": canonical_hash(prepared),
        "catalog_rows": len(catalog),
        "collision_excess": collision_excess,
        "selection_sha256": selection_hashes,
        "next_gate": "official_generator_checkpoint_and_native_trace",
    }
    write(args.output_dir / "finalization_manifest.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-prepared", type=Path, required=True)
    parser.add_argument("--base-selection", type=Path, nargs="+", required=True)
    parser.add_argument("--tokenizer-training-manifest", type=Path, required=True)
    parser.add_argument("--semantic-ids", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(finalize(parse_args()), indent=2, sort_keys=True))
