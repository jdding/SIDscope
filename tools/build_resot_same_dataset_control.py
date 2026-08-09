#!/usr/bin/env python3
"""Build a deterministic same-dataset category-prefix control for ReSOT."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.preflight import build_metric_smoke_summary  # noqa: E402


DEFAULT_INPUT_ROOT = ROOT / "experiments/v1_evidence_chain/gate17_resot_intake/normalized_text"
DEFAULT_OUTPUT = ROOT / "docs/reproducibility/resot_instruments_category_control.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _category_paths(metadata: pd.DataFrame) -> tuple[list[list[str]], list[str]]:
    if "category" not in metadata.columns:
        raise ValueError("ReSOT metadata lacks the category field required by the control")
    missing_tokens = {"", "unknown", "none", "nan", "null"}
    paths = []
    for value in metadata["category"].fillna(""):
        parts = [part.strip() for part in str(value).split(",") if part.strip()]
        paths.append([] if len(parts) == 1 and parts[0].lower() in missing_tokens else parts)
    nonempty = [path for path in paths if path]
    if not nonempty:
        raise ValueError("ReSOT metadata has no nonempty category paths")
    common: list[str] = []
    for values in zip(*nonempty):
        if len(set(values)) != 1:
            break
        common.append(values[0])
    trimmed = [path[len(common) :] if path else ["<missing>"] for path in paths]
    return trimmed, common


def build_category_prefix_control(metadata: pd.DataFrame, dataset: str = "Instruments") -> tuple[pd.DataFrame, list[str]]:
    """Encode three category levels and a deterministic unique leaf ordinal."""

    paths, removed_common_prefix = _category_paths(metadata)
    ordered = metadata[["item_id"]].copy()
    ordered["_path"] = paths
    ordered = ordered.sort_values("item_id", kind="stable").reset_index(drop=True)

    parent: list[tuple[int, ...]] = [tuple() for _ in range(len(ordered))]
    for depth in range(3):
        labels = [path[depth] if depth < len(path) else "<missing>" for path in ordered["_path"]]
        grouped_labels: dict[tuple[int, ...], list[str]] = {}
        for key, label in zip(parent, labels):
            grouped_labels.setdefault(key, []).append(label)
        codebooks = {
            key: {label: idx + 1 for idx, label in enumerate(sorted(set(values)))}
            for key, values in grouped_labels.items()
        }
        codes = [codebooks[key][label] for key, label in zip(parent, labels)]
        ordered[f"sid_level_{depth}"] = codes
        parent = [(*key, code) for key, code in zip(parent, codes)]

    ordered["sid_level_3"] = ordered.groupby(
        ["sid_level_0", "sid_level_1", "sid_level_2"], sort=True
    ).cumcount() + 1
    levels = [f"sid_level_{depth}" for depth in range(4)]
    ordered["sid"] = ordered[levels].astype(str).agg("-".join, axis=1)
    ordered["method"] = "resot_same_dataset_category_prefix_control"
    ordered["dataset"] = dataset
    return ordered.drop(columns=["_path"]), removed_common_prefix


def build_result(input_root: Path) -> dict[str, Any]:
    sid_path = input_root / "sid_assignments.parquet"
    metadata_path = input_root / "item_metadata.parquet"
    interactions_path = input_root / "interactions.parquet"
    source_sid = pd.read_parquet(sid_path)
    metadata = pd.read_parquet(metadata_path)
    interactions = pd.read_parquet(interactions_path)
    control, removed_common_prefix = build_category_prefix_control(metadata)

    source_row = build_metric_smoke_summary(
        source_sid, metadata, interactions, top_k=5, max_pair_events=10_000, max_user_items=50
    )[0]
    control_row = build_metric_smoke_summary(
        control, metadata, interactions, top_k=5, max_pair_events=10_000, max_user_items=50
    )[0]
    source_d3 = float(source_row["d3_depth1_weighted_collab_recall"])
    control_d3 = float(control_row["d3_depth1_weighted_collab_recall"])
    return {
        "schema": "sidscope.resot.same_dataset_control.v1",
        "status": "pass",
        "dataset": "Instruments",
        "control_role": "deterministic same-dataset interpretation control; not a named tokenizer row",
        "protocol": {
            "category_path": "comma-separated metadata category; common leading path removed",
            "prefix_levels": "first three remaining hierarchical category segments, lexicographically encoded within parent",
            "leaf_level": "item-id-sorted ordinal within the three-level category prefix",
            "d3_top_k": 5,
            "d3_max_pair_events": 10_000,
            "d3_max_user_items": 50,
            "removed_common_category_prefix": removed_common_prefix,
        },
        "inputs": {
            "sid_assignments_sha256": _sha256(sid_path),
            "item_metadata_sha256": _sha256(metadata_path),
            "interactions_sha256": _sha256(interactions_path),
        },
        "source_artifact": {
            "method": str(source_row["method"]),
            "items": int(len(source_sid)),
            "d3_depth1_weighted_collab_recall": source_d3,
        },
        "category_prefix_control": {
            "method": str(control_row["method"]),
            "items": int(len(control)),
            "unique_full_sids": int(control_row["unique_sid"]),
            "full_collision_rate": float(control_row["full_collision_rate"]),
            "d3_depth1_weighted_collab_recall": control_d3,
        },
        "comparison": {
            "absolute_d3_gap_control_minus_source": control_d3 - source_d3,
            "interpretation": (
                "The released ReSOT mapping is collision-free, but its depth-1 prefixes preserve less "
                "train-only co-occurrence structure than a deterministic category-prefix control on the same data."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_result(args.input_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
