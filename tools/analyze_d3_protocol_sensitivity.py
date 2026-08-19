#!/usr/bin/env python3
"""Evaluate D3 route-order sensitivity to neighbor and per-user caps."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.metrics import alignment  # noqa: E402


DEFAULT_MANIFEST = ROOT / "experiments/v1_evidence_chain/gate2_cross_dataset_utility/g2_manifest.csv"
DEFAULT_JSON = ROOT / "docs/reproducibility/d3_protocol_sensitivity.json"
DEFAULT_CSV = ROOT / "docs/reproducibility/d3_protocol_sensitivity_rows.csv"
ROUTE_LABELS = [
    "resid_gaoq_video_pilot",
    "grid_faithful_p5_beauty",
    "card_rqvae_p5_beauty",
    "diger_rqvae_beauty",
    "diger_rqvae_yelp",
    "resot_text_index_instruments",
    "letter_official_instruments",
    "lcrec_official_instruments",
]
TOP_K = (5, 10, 20)
USER_CAPS = (50, 100, 200)
PAIR_BUDGET = 10_000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        by_label = {row["label"]: row for row in csv.DictReader(handle)}
    missing = sorted(set(ROUTE_LABELS) - set(by_label))
    if missing:
        raise RuntimeError(f"Sensitivity manifest lacks routes: {missing}")
    return [by_label[label] for label in ROUTE_LABELS]


def depth1_d3(row: dict[str, str], top_k: int, user_cap: int) -> float:
    sid = pd.read_parquet(row["sid_assignments"])
    metadata = pd.read_parquet(row["item_metadata"])
    interactions = pd.read_parquet(row["interactions"])
    result = alignment(
        sid,
        metadata,
        interactions,
        top_k=top_k,
        max_pair_events=PAIR_BUDGET,
        max_user_items=user_cap,
    )
    selected = result[result["prefix_depth"] == 1]
    if len(selected) != 1:
        raise RuntimeError(f"Expected one depth-1 D3 row for {row['label']}, found {len(selected)}")
    return float(selected.iloc[0]["weighted_collab_prefix_recall"])


def run_analysis(manifest_path: Path) -> tuple[dict[str, object], pd.DataFrame]:
    manifest = load_manifest(manifest_path)
    records = []
    input_hashes: dict[str, dict[str, str]] = {}
    for row in manifest:
        input_hashes[row["label"]] = {
            key: sha256(Path(row[key])) for key in ("sid_assignments", "item_metadata", "interactions")
        }
        for top_k in TOP_K:
            for user_cap in USER_CAPS:
                records.append(
                    {
                        "route_label": row["label"],
                        "dataset": row["dataset"],
                        "row_family": row["row_family"],
                        "top_k": top_k,
                        "max_user_items": user_cap,
                        "max_pair_events": PAIR_BUDGET,
                        "d3_depth1_weighted": depth1_d3(row, top_k=top_k, user_cap=user_cap),
                    }
                )
    frame = pd.DataFrame(records)
    primary = frame[(frame["top_k"] == 5) & (frame["max_user_items"] == 50)].set_index("route_label")
    primary_order = primary["d3_depth1_weighted"].rank(method="average", ascending=False)
    configs = []
    for (top_k, user_cap), group in frame.groupby(["top_k", "max_user_items"], sort=True):
        current = group.set_index("route_label").loc[primary.index]
        rho = float(spearmanr(primary["d3_depth1_weighted"], current["d3_depth1_weighted"]).statistic)
        current_order = current["d3_depth1_weighted"].rank(method="average", ascending=False)
        configs.append(
            {
                "top_k": int(top_k),
                "max_user_items": int(user_cap),
                "route_rank_spearman_vs_primary": rho,
                "maximum_absolute_rank_shift": float((current_order - primary_order).abs().max()),
            }
        )
    result: dict[str, object] = {
        "schema": "sidscope.d3.protocol_sensitivity.v1",
        "primary": {"top_k": 5, "max_user_items": 50, "max_pair_events": PAIR_BUDGET},
        "routes": len(manifest),
        "route_labels": ROUTE_LABELS,
        "configurations": configs,
        "minimum_rank_spearman_vs_primary": min(row["route_rank_spearman_vs_primary"] for row in configs),
        "maximum_rank_shift_over_grid": max(row["maximum_absolute_rank_shift"] for row in configs),
        "input_sha256": input_hashes,
        "claim_boundary": "Secondary route-order sensitivity around the fixed C3 protocol; the primary paper values remain m=5, U=50, B=10000.",
    }
    return result, frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    result, rows = run_analysis(args.manifest.resolve())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows.to_csv(args.output_csv, index=False)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
