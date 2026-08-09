"""Shared target-level accounting for normalized D7 beam traces."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from sidinspector.d7_trace import (
    CONSTRAINED_SURVIVABLE,
    deterministic_label_check,
    label_traces,
    summarize_trace_labels,
)


def bootstrap_user_rate(
    frame: pd.DataFrame, *, value_col: str, samples: int, seed: int
) -> dict[str, float | int]:
    if frame.empty:
        return {"users": 0, "targets": 0, "rate": math.nan, "ci_low": math.nan, "ci_high": math.nan}
    user_values = {
        str(user): group[value_col].astype(float).to_numpy()
        for user, group in frame.groupby("user_id", sort=False)
    }
    users = sorted(user_values)
    data = frame[value_col].astype(float).to_numpy()
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(samples):
        sampled_users = rng.choice(users, size=len(users), replace=True)
        sampled_values = np.concatenate([user_values[str(user)] for user in sampled_users])
        estimates.append(float(np.mean(sampled_values)))
    return {
        "users": int(len(users)),
        "targets": int(len(data)),
        "rate": float(np.mean(data)),
        "ci_low": float(np.quantile(estimates, 0.025)),
        "ci_high": float(np.quantile(estimates, 0.975)),
    }


def analyze_traces(
    *,
    sid: pd.DataFrame,
    traces: pd.DataFrame,
    outcomes: pd.DataFrame,
    bootstrap_samples: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    active = {str(value) for value in sid["item_id"].dropna().astype(int)}
    labels = label_traces(sid=sid, traces=traces, active_item_ids=active)
    deterministic = deterministic_label_check(sid=sid, traces=traces, active_item_ids=active)
    merged = traces.merge(labels, on=["trace_id", "user_id", "rank"], how="left", validate="one_to_one")

    def canonical_resolution(value: Any) -> str:
        if value is None or pd.isna(value) or not str(value):
            return ""
        return ";".join(sorted(str(value).split(";"), key=lambda item: (not item.isdigit(), item)))

    exporter_resolution = merged["resolved_item_ids_exporter"].map(canonical_resolution)
    labeler_resolution = merged["resolved_item_ids"].map(canonical_resolution)
    resolution_match = bool((exporter_resolution == labeler_resolution).all())
    flag_families = sorted(
        {flag for value in labels["failure_flags"] for flag in str(value).split("|") if flag}
    )
    flag_rows: list[dict[str, Any]] = []
    for label_row in labels.itertuples(index=False):
        present = {flag for flag in str(label_row.failure_flags).split("|") if flag}
        flag_rows.append(
            {"trace_id": str(label_row.trace_id), **{family: int(family in present) for family in flag_families}}
        )
    trace_flags = pd.DataFrame(flag_rows).groupby("trace_id", as_index=False)[flag_families].max()
    target_analysis = outcomes.merge(trace_flags, on="trace_id", how="left")
    for column in trace_flags.columns:
        if column != "trace_id":
            target_analysis[column] = pd.to_numeric(target_analysis[column], errors="coerce").fillna(0).astype(int)
    family_rates: dict[str, dict[str, Any]] = {}
    for family in sorted(CONSTRAINED_SURVIVABLE - {"valid_hit"}):
        if family == "high_uncertainty" and not labels["max_prefix_entropy"].notna().any():
            family_rates[family] = {
                "available": False,
                "reason": "prefix_entropy_not_exported",
                "users": int(target_analysis["user_id"].nunique()),
                "targets": int(len(target_analysis)),
                "rate": None,
                "ci_low": None,
                "ci_high": None,
            }
            continue
        values = target_analysis[family] if family in target_analysis else pd.Series(np.zeros(len(target_analysis)))
        rate_frame = target_analysis[["user_id"]].copy()
        rate_frame[family] = values.to_numpy()
        family_rates[family] = bootstrap_user_rate(
            rate_frame, value_col=family, samples=bootstrap_samples, seed=seed + len(family_rates) * 97
        )
        if family == "high_uncertainty":
            family_rates[family]["available"] = True
    for outcome in ("target_missed", "target_ambiguous", "target_path_survived", "target_item_uniquely_hit"):
        family_rates[outcome] = bootstrap_user_rate(
            target_analysis[["user_id", outcome]],
            value_col=outcome,
            samples=bootstrap_samples,
            seed=seed + len(family_rates) * 97,
        )
    overlap_rows: list[dict[str, Any]] = []
    overlap_families = [family for family in flag_families if family != "valid_hit"]
    for left_index, left in enumerate(overlap_families):
        for right in overlap_families[left_index:]:
            both = target_analysis[left].astype(bool) & target_analysis[right].astype(bool)
            overlap_rows.append(
                {
                    "failure_left": left,
                    "failure_right": right,
                    "target_count": int(both.sum()),
                    "target_rate": float(both.mean()),
                }
            )
    overlap = pd.DataFrame(overlap_rows)
    strata_rows: list[dict[str, Any]] = []
    for family in overlap_families:
        for missed, group in target_analysis.groupby("target_missed", dropna=False):
            strata_rows.append(
                {
                    "failure_family": family,
                    "target_missed": bool(missed),
                    "targets": int(len(group)),
                    "family_target_count": int(group[family].sum()),
                    "family_target_rate": float(group[family].mean()),
                }
            )
    outcome_strata = pd.DataFrame(strata_rows)
    summary = summarize_trace_labels(labels)
    result = {
        "deterministic_label_check": bool(deterministic),
        "exporter_labeler_resolution_match": resolution_match,
        "trace_rows": int(len(traces)),
        "target_traces": int(traces["trace_id"].nunique()),
        "beam_widths": sorted(int(value) for value in traces["beam_width"].unique()),
        "decoding_modes": sorted(str(value) for value in traces["decoding_mode"].unique()),
        "invalid_path_rows": int((labels["primary_failure"] == "invalid_path").sum()),
        "unique_paths_per_trace": bool(not traces.duplicated(["trace_id", "sid_path"]).any()),
        "family_rates": family_rates,
        "primary_failure_counts": {
            str(row.primary_failure): int(row.rows) for row in summary.itertuples(index=False)
        },
        "failure_flag_target_counts": {
            family: int(target_analysis[family].sum()) for family in overlap_families
        },
        "bootstrap_unit": "user_cluster",
    }
    return merged, target_analysis, overlap, outcome_strata, result
