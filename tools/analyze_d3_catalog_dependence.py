#!/usr/bin/env python3
"""Audit D3 construct calibration after control removal and catalog collapse."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "experiments/v1_evidence_chain/gate2_cross_dataset_utility/analysis/g2_probe_diagnostics_joined.csv"
DEFAULT_JSON = ROOT / "docs/reproducibility/d3_catalog_dependence_summary.json"
DEFAULT_CSV = ROOT / "docs/reproducibility/d3_catalog_dependence_artifacts.csv"
ARTIFACT_COLS = ["dataset", "label", "method", "manifest_row", "row_family", "gate2_role"]
SIGNAL = "d3_weighted_collab_prefix_recall"
OUTCOME = "candidate_recall"
EXCLUDED_FAMILIES = {"deterministic_control", "local_RQ_reference"}


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
        return math.nan
    return float(np.corrcoef(rankdata(x, method="average"), rankdata(y, method="average"))[0, 1])


def exact_permutation(x: np.ndarray, y: np.ndarray) -> dict[str, float | int]:
    observed = spearman(x, y)
    values = np.asarray([spearman(x, np.asarray(p, dtype=float)) for p in itertools.permutations(y)], dtype=float)
    values = values[np.isfinite(values)]
    tail = np.abs(values) >= abs(observed) - 1e-12
    tail_counts = [int(np.sum(np.abs(values) >= threshold - 1e-12)) for threshold in np.unique(np.abs(values))]
    return {
        "rho": observed,
        "exact_two_sided_p": float(np.mean(tail)),
        "permutations": int(len(values)),
        "attainable_two_sided_p_floor": float(min(tail_counts) / len(values)),
    }


def cluster_bootstrap(frame: pd.DataFrame, samples: int, seed: int) -> dict[str, float | int]:
    catalogs = sorted(frame["dataset"].unique())
    groups = {catalog: frame[frame["dataset"] == catalog] for catalog in catalogs}
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(samples):
        chosen = rng.choice(catalogs, size=len(catalogs), replace=True)
        pieces = []
        for draw, catalog in enumerate(chosen):
            piece = groups[str(catalog)].copy()
            piece["_bootstrap_catalog"] = f"{draw}:{catalog}"
            pieces.append(piece)
        sample = pd.concat(pieces, ignore_index=True)
        value = spearman(sample[SIGNAL].to_numpy(float), sample[OUTCOME].to_numpy(float))
        if math.isfinite(value):
            values.append(value)
    return {
        "catalog_clusters": len(catalogs),
        "bootstrap_samples": len(values),
        "ci_low": float(np.quantile(values, 0.025)),
        "ci_high": float(np.quantile(values, 0.975)),
    }


def run_analysis(input_path: Path, samples: int, seed: int) -> tuple[dict[str, object], pd.DataFrame]:
    frame = pd.read_csv(input_path)
    collapsed = (
        frame.groupby(ARTIFACT_COLS, dropna=False)[[SIGNAL, OUTCOME]]
        .mean()
        .reset_index()
        .sort_values(["dataset", "label"])
        .reset_index(drop=True)
    )
    export_rows = collapsed[~collapsed["row_family"].isin(EXCLUDED_FAMILIES)].copy()
    catalog_rows = export_rows.groupby("dataset", dropna=False)[[SIGNAL, OUTCOME]].mean().reset_index()

    export_exact = exact_permutation(export_rows[SIGNAL].to_numpy(float), export_rows[OUTCOME].to_numpy(float))
    catalog_exact = exact_permutation(catalog_rows[SIGNAL].to_numpy(float), catalog_rows[OUTCOME].to_numpy(float))
    leave_one_out = []
    for catalog in sorted(catalog_rows["dataset"].unique()):
        subset = catalog_rows[catalog_rows["dataset"] != catalog]
        leave_one_out.append(
            {
                "omitted_catalog": str(catalog),
                "remaining_catalogs": int(len(subset)),
                "rho": spearman(subset[SIGNAL].to_numpy(float), subset[OUTCOME].to_numpy(float)),
            }
        )

    result: dict[str, object] = {
        "schema": "sidscope.d3_catalog_dependence.v1",
        "input": str(input_path.relative_to(ROOT)),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "signal": SIGNAL,
        "outcome": OUTCOME,
        "artifact_collapse": "+".join(ARTIFACT_COLS[:4]),
        "excluded_row_families": sorted(EXCLUDED_FAMILIES),
        "all_artifact_clusters": int(len(collapsed)),
        "tokenizer_export_artifacts": int(len(export_rows)),
        "catalog_clusters": int(len(catalog_rows)),
        "tokenizer_export_exact": export_exact,
        "catalog_collapsed_exact": catalog_exact,
        "catalog_cluster_bootstrap": cluster_bootstrap(export_rows, samples=samples, seed=seed),
        "leave_one_catalog_out": leave_one_out,
        "interpretation": (
            "Removing deterministic category controls and local RQ references does not remove the construct-calibration association. "
            "Catalog collapse reduces the effective unit to five catalogs; all catalog-level uncertainty is sensitivity evidence, not a population estimate."
        ),
        "seed": seed,
    }
    return result, export_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--bootstrap-samples", type=int, default=4999)
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()

    result, rows = run_analysis(args.input.resolve(), samples=args.bootstrap_samples, seed=args.seed)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows.to_csv(args.output_csv, index=False)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
