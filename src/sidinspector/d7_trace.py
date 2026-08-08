"""D7 generator-trace diagnostics over normalized SID mappings."""

from __future__ import annotations

import ast
import math
from collections import defaultdict
from typing import Any, Iterable

import pandas as pd


FAILURE_PRECEDENCE = [
    "invalid_path",
    "ambiguous_path",
    "stale_or_ooc",
    "duplicate_item",
    "duplicate_path",
    "prefix_loop",
    "high_uncertainty",
    "valid_hit",
]

CONSTRAINED_SURVIVABLE = {
    "ambiguous_path",
    "stale_or_ooc",
    "duplicate_item",
    "duplicate_path",
    "prefix_loop",
    "high_uncertainty",
    "valid_hit",
}


def level_cols(frame: pd.DataFrame) -> list[str]:
    return sorted(
        [col for col in frame.columns if col.startswith("sid_level_") and not frame[col].isna().all()],
        key=lambda col: int(col.rsplit("_", 1)[1]),
    )


def normalize_sid_path(value: Any) -> tuple[str, ...]:
    """Normalize a generated SID path into a string-token tuple."""

    if isinstance(value, (list, tuple)):
        return tuple(str(part) for part in value)
    if pd.isna(value):
        raise ValueError("sid_path is missing")
    text = str(value).strip()
    if not text:
        raise ValueError("sid_path is empty")
    if text.startswith("[") and text.endswith("]"):
        parsed = ast.literal_eval(text)
        if not isinstance(parsed, (list, tuple)):
            raise ValueError(f"sid_path literal is not a list/tuple: {text}")
        return tuple(str(part) for part in parsed)
    delimiter = "-" if "-" in text else "/" if "/" in text else ","
    return tuple(part.strip() for part in text.split(delimiter) if part.strip())


def build_reverse_lookup(sid: pd.DataFrame) -> tuple[dict[tuple[str, ...], list[str]], set[tuple[str, ...]]]:
    cols = level_cols(sid)
    if not cols:
        raise ValueError("sid_assignments must contain sid_level_* columns")
    lookup: dict[tuple[str, ...], list[str]] = defaultdict(list)
    valid_prefixes: set[tuple[str, ...]] = set()
    for row in sid[["item_id", *cols]].itertuples(index=False):
        path = tuple(str(getattr(row, col)) for col in cols)
        lookup[path].append(str(row.item_id))
        for depth in range(1, len(path) + 1):
            valid_prefixes.add(path[:depth])
    return dict(lookup), valid_prefixes


def mean_step_logprob(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        values = [float(item) for item in value]
    else:
        if pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.startswith("[") and text.endswith("]"):
            values = [float(item) for item in ast.literal_eval(text)]
        else:
            values = [float(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        return None
    return float(sum(values) / len(values))


def max_prefix_entropy(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    if isinstance(value, (list, tuple)):
        values = [float(item) for item in value]
    else:
        if pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.startswith("[") and text.endswith("]"):
            values = [float(item) for item in ast.literal_eval(text)]
        else:
            values = [float(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        return None
    return float(max(values))


def _primary_failure(flags: Iterable[str]) -> str:
    flag_set = set(flags)
    for label in FAILURE_PRECEDENCE:
        if label in flag_set:
            return label
    return "valid_hit"


def _normalize_item_id(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _failure_family(primary_failure: str) -> str:
    if primary_failure == "invalid_path":
        return "unconstrained_only"
    if primary_failure in CONSTRAINED_SURVIVABLE:
        return "constrained_survivable"
    return "trace_dynamic"


def label_traces(
    sid: pd.DataFrame,
    traces: pd.DataFrame,
    active_item_ids: set[str] | None = None,
    entropy_threshold: float | None = 2.0,
) -> pd.DataFrame:
    """Label generator traces with deterministic D7 failure categories."""

    required = {"trace_id", "user_id", "rank", "sid_path"}
    missing = sorted(required - set(traces.columns))
    if missing:
        raise ValueError(f"generator_traces missing required columns: {missing}")
    lookup, valid_prefixes = build_reverse_lookup(sid)
    active = {str(item) for item in active_item_ids} if active_item_ids is not None else None
    frame = traces.copy()
    frame["rank"] = frame["rank"].astype(int)
    frame = frame.sort_values(["trace_id", "rank"], kind="stable").reset_index(drop=True)

    seen_paths: dict[str, set[str]] = defaultdict(set)
    seen_items: dict[str, set[str]] = defaultdict(set)
    rows = []
    for row in frame.itertuples(index=False):
        trace_id = str(row.trace_id)
        path = normalize_sid_path(row.sid_path)
        sid_path_norm = "-".join(path)
        item_ids = lookup.get(path, [])
        flags: list[str] = []
        if not item_ids:
            flags.append("invalid_path")
        elif len(item_ids) > 1:
            flags.append("ambiguous_path")
        else:
            item_id = item_ids[0]
            if active is not None and item_id not in active:
                flags.append("stale_or_ooc")
            if item_id in seen_items[trace_id]:
                flags.append("duplicate_item")
        if sid_path_norm in seen_paths[trace_id]:
            flags.append("duplicate_path")
        if _has_prefix_loop(path):
            flags.append("prefix_loop")
        entropy = max_prefix_entropy(getattr(row, "prefix_entropy", None))
        if entropy_threshold is not None and entropy is not None and entropy >= entropy_threshold:
            flags.append("high_uncertainty")
        if not flags:
            flags.append("valid_hit")

        resolved_item_id = item_ids[0] if len(item_ids) == 1 else None
        target_item_id = _normalize_item_id(getattr(row, "target_item_id", None))
        target_hit = bool(resolved_item_id is not None and target_item_id is not None and target_item_id == resolved_item_id)
        primary = _primary_failure(flags)
        seen_paths[trace_id].add(sid_path_norm)
        if resolved_item_id is not None:
            seen_items[trace_id].add(resolved_item_id)
        rows.append(
            {
                "trace_id": trace_id,
                "user_id": str(row.user_id),
                "rank": int(row.rank),
                "sid_path_norm": sid_path_norm,
                "resolved_item_id": resolved_item_id,
                "resolved_item_ids": ";".join(item_ids),
                "primary_failure": primary,
                "failure_flags": "|".join(label for label in FAILURE_PRECEDENCE if label in set(flags)),
                "failure_family": _failure_family(primary),
                "target_hit": target_hit,
                "path_prefix_len": len(path),
                "mean_step_logprob": mean_step_logprob(getattr(row, "step_logprob", None)),
                "max_prefix_entropy": entropy,
                "has_valid_prefix": any(path[:depth] in valid_prefixes for depth in range(1, len(path) + 1)),
            }
        )
    return pd.DataFrame(rows)


def _has_prefix_loop(path: tuple[str, ...]) -> bool:
    if len(path) < 4:
        return False
    midpoint = len(path) // 2
    return len(path) % 2 == 0 and path[:midpoint] == path[midpoint:]


def summarize_trace_labels(labels: pd.DataFrame) -> pd.DataFrame:
    if labels.empty:
        return pd.DataFrame(columns=["primary_failure", "failure_family", "rows", "target_hits"])
    return (
        labels.groupby(["primary_failure", "failure_family"], dropna=False)
        .agg(rows=("trace_id", "size"), target_hits=("target_hit", "sum"))
        .reset_index()
        .sort_values(["failure_family", "primary_failure"], kind="stable")
    )


def deterministic_label_check(sid: pd.DataFrame, traces: pd.DataFrame, active_item_ids: set[str] | None = None) -> bool:
    first = label_traces(sid, traces, active_item_ids=active_item_ids)
    shuffled = traces.iloc[::-1].reset_index(drop=True)
    second = label_traces(sid, shuffled, active_item_ids=active_item_ids)
    cols = ["trace_id", "rank", "sid_path_norm", "primary_failure", "failure_flags", "resolved_item_id"]
    return first[cols].reset_index(drop=True).equals(second[cols].reset_index(drop=True))
