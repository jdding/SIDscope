#!/usr/bin/env python3
"""Paired user-level uncertainty analysis for the G22 DACT handoff case."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "experiments/v1_evidence_chain/gate22_diagnose_repair_reaudit/remote_runs/20260809T032107Z/primary"
DEFAULT_OUTPUT = ROOT / "docs/reproducibility/g22_handoff_uncertainty.json"
STATES = [
    "stale_old_model_old_mapping",
    "mapping_only_old_model_new_mapping",
    "adapted_model_new_mapping_seed2025",
    "adapted_model_new_mapping_seed2026",
    "adapted_model_new_mapping_seed2027",
]
RECOVERY_FRACTION = 0.90


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ndcg_gain(ranks: pd.Series, cutoff: int = 20) -> np.ndarray:
    numeric = pd.to_numeric(ranks, errors="coerce").to_numpy(float)
    hit = np.isfinite(numeric) & (numeric <= cutoff)
    gains = np.zeros(len(numeric), dtype=float)
    gains[hit] = 1.0 / np.log2(numeric[hit] + 1.0)
    return gains


def recall_hit(ranks: pd.Series, cutoff: int = 20) -> np.ndarray:
    numeric = pd.to_numeric(ranks, errors="coerce").to_numpy(float)
    return (np.isfinite(numeric) & (numeric <= cutoff)).astype(float)


def interval(values: np.ndarray) -> list[float]:
    return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def load_states(input_dir: Path) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    frames: dict[str, pd.DataFrame] = {}
    hashes: dict[str, str] = {}
    identity: pd.DataFrame | None = None
    for state in STATES:
        path = input_dir / f"{state}_outcomes.parquet"
        frame = pd.read_parquet(path).sort_values("released_row_index").reset_index(drop=True)
        key = frame[["released_row_index", "user_id", "target_item_id", "target_stratum"]]
        if identity is None:
            identity = key
        elif not key.equals(identity):
            raise RuntimeError(f"G22 paired outcome identity differs for {state}")
        if frame["user_id"].nunique() != len(frame):
            raise RuntimeError(f"G22 outcome rows are not one row per user for {state}")
        frames[state] = frame
        hashes[path.name] = sha256(path)
    return frames, hashes


def run_analysis(input_dir: Path, samples: int, seed: int) -> dict[str, object]:
    frames, hashes = load_states(input_dir)
    first = frames[STATES[0]]
    common_positions = np.flatnonzero(first["target_stratum"].to_numpy() == "common")
    new_positions = np.flatnonzero(first["target_stratum"].to_numpy() == "new")
    common_gain = {state: ndcg_gain(frame.loc[common_positions, "target_path_rank"]) for state, frame in frames.items()}
    new_hit = {state: recall_hit(frame.loc[new_positions, "target_unique_item_rank"]) for state, frame in frames.items()}

    points = {
        state: {
            "common_path_ndcg_at_20": float(common_gain[state].mean()),
            "new_item_recall_at_20": float(new_hit[state].mean()),
        }
        for state in STATES
    }
    rng = np.random.default_rng(seed)
    common_boot = {state: np.empty(samples, dtype=float) for state in STATES}
    new_boot = {state: np.empty(samples, dtype=float) for state in STATES}
    for draw in range(samples):
        common_sample = rng.integers(0, len(common_positions), size=len(common_positions))
        new_sample = rng.integers(0, len(new_positions), size=len(new_positions))
        for state in STATES:
            common_boot[state][draw] = float(common_gain[state][common_sample].mean())
            new_boot[state][draw] = float(new_hit[state][new_sample].mean())

    state_results = {}
    for state in STATES:
        state_results[state] = {
            **points[state],
            "common_path_ndcg_at_20_ci": interval(common_boot[state]),
            "new_item_recall_at_20_ci": interval(new_boot[state]),
        }

    stale = STATES[0]
    mapping = STATES[1]
    adapted = STATES[2:]
    disruption_point = max(0.0, points[stale]["common_path_ndcg_at_20"] - points[mapping]["common_path_ndcg_at_20"])
    threshold_point = points[stale]["common_path_ndcg_at_20"] - (1.0 - RECOVERY_FRACTION) * disruption_point
    disruption_boot = np.maximum(0.0, common_boot[stale] - common_boot[mapping])
    threshold_boot = common_boot[stale] - (1.0 - RECOVERY_FRACTION) * disruption_boot

    adapted_results = {}
    joint_gate = np.ones(samples, dtype=bool)
    for state in adapted:
        delta = common_boot[state] - common_boot[mapping]
        gate = (delta > 0.0) & (common_boot[state] >= threshold_boot) & (new_boot[state] > 0.0)
        joint_gate &= gate
        adapted_results[state] = {
            "common_ndcg_delta_vs_mapping_only": points[state]["common_path_ndcg_at_20"] - points[mapping]["common_path_ndcg_at_20"],
            "common_ndcg_delta_vs_mapping_only_ci": interval(delta),
            "probability_above_mapping_only": float(np.mean(delta > 0.0)),
            "probability_meeting_relative_recovery": float(np.mean(common_boot[state] >= threshold_boot)),
            "probability_reaching_new_items": float(np.mean(new_boot[state] > 0.0)),
            "probability_full_gate": float(np.mean(gate)),
        }

    return {
        "schema": "sidscope.g22.handoff_uncertainty.v1",
        "input_dir": str(input_dir.relative_to(ROOT)),
        "input_sha256": hashes,
        "paired_users": int(len(first)),
        "common_users": int(len(common_positions)),
        "new_item_users": int(len(new_positions)),
        "bootstrap": {"samples": samples, "seed": seed, "unit": "paired user", "stratified_by": "target_stratum"},
        "states": state_results,
        "mapping_only_vs_stale": {
            "common_ndcg_delta": points[mapping]["common_path_ndcg_at_20"] - points[stale]["common_path_ndcg_at_20"],
            "common_ndcg_delta_ci": interval(common_boot[mapping] - common_boot[stale]),
            "probability_mapping_below_stale": float(np.mean(common_boot[mapping] < common_boot[stale])),
            "interpretation": "The mapping-only common-item change is not statistically resolved; its new-item recall is exactly zero in this case.",
        },
        "relative_recovery_threshold": {
            "fraction": RECOVERY_FRACTION,
            "point": float(threshold_point),
            "bootstrap_ci": interval(threshold_boot),
        },
        "adapted_vs_mapping_only": adapted_results,
        "probability_all_adapted_seeds_pass": float(np.mean(joint_gate)),
        "claim_boundary": "Paired user-level uncertainty within one released DACT lifecycle case; not cross-lifecycle or causal generalization.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-samples", type=int, default=4999)
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()
    result = run_analysis(args.input_dir.resolve(), samples=args.bootstrap_samples, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
