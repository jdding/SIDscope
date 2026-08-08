#!/usr/bin/env python3
"""Run SIDScope G10 independent-candidate utility-anchor checks.

G10 addresses the remaining reviewer risk after G9. G9 disjointed the users
used for D3 from the users used for fixed-reranker evaluation, but the bounded
reranker still consumed SID-prefix candidate buckets. G10 keeps the disjoint
user split and changes the downstream candidate pool: ranking is performed over
the artifact item catalog rather than over prefix-matched candidates. This
tests whether D3 remains associated with a downstream utility anchor after the
ranking candidate set no longer depends on SID prefix retrieval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from sidinspector.downstream_probe import (  # noqa: E402
    _build_prefix_index,
    _cooccurrence_counts,
    _dcg,
    _d3_weighted,
)
from tools.run_v1_gate2_cross_dataset_utility import (  # noqa: E402
    PRIMARY_ANALYSIS_ROLES,
    _filter_row_data,
    _split_train_eval,
)

DEFAULT_G2_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate2_cross_dataset_utility"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate10_independent_utility"
DEFAULT_RUNS_DIR = PROJECT_ROOT / "experiments/v1_evidence_chain/runs"
SUPPORTING_ROLES = ("supporting_official_upstream",)
CATALOG_PROTOCOLS = (
    "full_catalog_non_prefix",
    "popularity_sampled_non_prefix",
    "random_sampled_non_prefix",
)
MAIN_RANKER = "catalog_sid_prefix_affinity"
METADATA_RANKER = "catalog_metadata_category_affinity"


def stable_mod(value: Any, modulo: int) -> int:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % modulo


def stable_seed(*parts: Any) -> int:
    digest = hashlib.sha256("::".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**32)


def rank_corr(x: pd.Series, y: pd.Series) -> float:
    mask = x.notna() & y.notna()
    if int(mask.sum()) < 3 or x[mask].nunique() < 2 or y[mask].nunique() < 2:
        return math.nan
    value = x[mask].rank(method="average").corr(y[mask].rank(method="average"))
    return math.nan if pd.isna(value) else float(value)


def _artifact_cols() -> list[str]:
    return ["dataset", "label", "method", "manifest_row"]


def _quantile_bucket(value: float, low: float, high: float) -> str:
    if value <= low:
        return "tail"
    if value <= high:
        return "mid"
    return "head"


def _cooccurrence_adjacency(co_counts: dict[tuple[int, int], int]) -> dict[int, list[tuple[int, int]]]:
    neighbors: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for (left, right), count in co_counts.items():
        if count > 0:
            neighbors[int(left)].append((int(right), int(count)))
    return neighbors


def _metadata_category_tokens(item_metadata: pd.DataFrame) -> dict[int, tuple[str, ...]]:
    token_cols = [col for col in ["category", "category_l3", "category_l2", "category_l1", "brand"] if col in item_metadata.columns]
    if not token_cols:
        return {}
    tokens: dict[int, tuple[str, ...]] = {}
    for row in item_metadata[["item_id", *token_cols]].itertuples(index=False):
        item = int(getattr(row, "item_id"))
        values: list[str] = []
        for col in token_cols:
            raw = getattr(row, col)
            if pd.isna(raw):
                continue
            parts = [part.strip() for part in str(raw).replace(">", ",").split(",") if part.strip()]
            values.extend(f"{col}:{part}" for part in parts)
        if values:
            tokens[item] = tuple(dict.fromkeys(values))
    return tokens


def _top_catalog_by_popularity(
    *,
    sorted_catalog: list[int],
    history: set[int],
    rec_k: int,
) -> list[int]:
    top: list[int] = []
    for item in sorted_catalog:
        if item in history:
            continue
        top.append(item)
        if len(top) >= rec_k:
            break
    return top


def _top_catalog_by_cooccurrence(
    *,
    sorted_catalog: list[int],
    catalog_set: set[int],
    history: set[int],
    popularity: dict[int, int],
    adjacency: dict[int, list[tuple[int, int]]],
    rec_k: int,
) -> list[int]:
    scores: dict[int, int] = defaultdict(int)
    for hist in history:
        for item, count in adjacency.get(hist, []):
            if item in catalog_set and item not in history:
                scores[item] += count
    scored = sorted(scores, key=lambda item: (-scores[item], -popularity.get(item, 0), item))
    top: list[int] = scored[:rec_k]
    if len(top) >= rec_k:
        return top

    already = set(top)
    for item in sorted_catalog:
        if item in history or item in already:
            continue
        top.append(item)
        if len(top) >= rec_k:
            break
    return top


def _top_catalog_by_sid_prefix_affinity(
    *,
    candidate_items: list[int],
    history: set[int],
    item_prefix: dict[int, tuple[Any, ...]],
    popularity: dict[int, int],
    adjacency: dict[int, list[tuple[int, int]]],
    rec_k: int,
) -> list[int]:
    co_scores: dict[int, int] = defaultdict(int)
    for hist in history:
        for item, count in adjacency.get(hist, []):
            co_scores[item] += count

    history_prefix_counts = Counter(item_prefix[item] for item in history if item in item_prefix)
    ranked = sorted(
        candidate_items,
        key=lambda item: (
            -history_prefix_counts.get(item_prefix.get(item), 0),
            -co_scores.get(item, 0),
            -popularity.get(item, 0),
            item,
        ),
    )
    return ranked[:rec_k]


def _top_catalog_by_metadata_category_affinity(
    *,
    candidate_items: list[int],
    history: set[int],
    item_categories: dict[int, tuple[str, ...]],
    popularity: dict[int, int],
    adjacency: dict[int, list[tuple[int, int]]],
    rec_k: int,
) -> list[int]:
    co_scores: dict[int, int] = defaultdict(int)
    for hist in history:
        for item, count in adjacency.get(hist, []):
            co_scores[item] += count

    history_category_counts: Counter[str] = Counter()
    for item in history:
        history_category_counts.update(item_categories.get(item, ()))

    def category_score(item: int) -> int:
        return sum(history_category_counts[token] for token in item_categories.get(item, ()))

    ranked = sorted(
        candidate_items,
        key=lambda item: (
            -category_score(item),
            -co_scores.get(item, 0),
            -popularity.get(item, 0),
            item,
        ),
    )
    return ranked[:rec_k]


def _evaluate_fold(
    *,
    sid: pd.DataFrame,
    train: pd.DataFrame,
    eval_events: pd.DataFrame,
    item_ids: set[int],
    item_prefix: dict[int, tuple[Any, ...]],
    item_categories: dict[int, tuple[str, ...]],
    eligible_users: list[Any],
    row: pd.Series,
    manifest_row: int,
    depth: int,
    fold: int,
    folds: int,
    rec_k: int,
    d3_top_k: int,
    max_pair_events: int,
    max_user_items: int,
    ranking_max_users_per_fold: int,
    candidate_protocol: str,
    candidate_pool_size: int,
) -> list[dict[str, Any]]:
    diag_users = [user for user in eligible_users if stable_mod(user, folds) != fold]
    eval_users = [user for user in eligible_users if stable_mod(user, folds) == fold]
    if not diag_users or not eval_users:
        return []

    diag_train = train[train["user_id"].isin(diag_users)].copy()
    eval_train = train[train["user_id"].isin(eval_users)].copy()
    eval_holdout = eval_events[eval_events["user_id"].isin(eval_users)].copy()

    diag_popularity = diag_train.groupby("item_id").size().astype(int).to_dict()
    sorted_catalog = sorted(item_ids, key=lambda item: (-diag_popularity.get(item, 0), item))
    catalog_set = set(sorted_catalog)
    pop_values = np.asarray([float(diag_popularity.get(item, 0)) for item in item_ids], dtype=float)
    low, high = float(np.quantile(pop_values, 1 / 3)), float(np.quantile(pop_values, 2 / 3))

    co_counts = _cooccurrence_counts(
        diag_train,
        max_pair_events=max_pair_events,
        max_user_items=max_user_items,
    )
    adjacency = _cooccurrence_adjacency(co_counts)
    d3_weighted, d3_users, d3_pair_events = _d3_weighted(
        sid,
        diag_train,
        depth=depth,
        top_k=d3_top_k,
        max_pair_events=max_pair_events,
        max_user_items=max_user_items,
    )

    train_by_user = {
        user: set(int(item) for item in group["item_id"])
        for user, group in eval_train.groupby("user_id", sort=False)
    }
    eval_by_user = {
        user: [int(item) for item in group["item_id"]]
        for user, group in eval_holdout.groupby("user_id", sort=False)
    }

    ranking_users = set(eval_users)
    if ranking_max_users_per_fold >= 0:
        ranking_users = set(
            sorted(eval_users, key=lambda user: stable_mod(f"rank::{user}", 2**31 - 1))[
                :ranking_max_users_per_fold
            ]
        )

    user_rows: list[dict[str, Any]] = []
    for user in sorted(set(train_by_user).intersection(eval_by_user)):
        if user not in ranking_users:
            continue
        history = {item for item in train_by_user[user] if item in item_prefix}
        targets = [item for item in eval_by_user[user] if item in item_prefix]
        if not history or not targets:
            continue
        target_set = set(targets)
        if candidate_protocol == "full_catalog_non_prefix":
            candidate_sorted_catalog = [item for item in sorted_catalog if item not in history]
        elif candidate_protocol == "popularity_sampled_non_prefix":
            base_pool = [item for item in sorted_catalog if item not in history][:candidate_pool_size]
            candidate_sorted_catalog = sorted(
                set(base_pool).union(target_set).difference(history),
                key=lambda item: (-diag_popularity.get(item, 0), item),
            )
        elif candidate_protocol == "random_sampled_non_prefix":
            eligible_pool = [item for item in sorted_catalog if item not in history and item not in target_set]
            if len(eligible_pool) > candidate_pool_size:
                rng = np.random.default_rng(stable_seed("pool", manifest_row, fold, user))
                positions = rng.choice(len(eligible_pool), size=candidate_pool_size, replace=False)
                base_pool = [eligible_pool[int(pos)] for pos in positions]
            else:
                base_pool = eligible_pool
            candidate_sorted_catalog = sorted(
                set(base_pool).union(target_set).difference(history),
                key=lambda item: (-diag_popularity.get(item, 0), item),
            )
        else:
            raise ValueError(f"Unknown candidate protocol: {candidate_protocol}")
        catalog_candidates = set(candidate_sorted_catalog)
        candidate_hits = target_set.intersection(catalog_candidates)
        if not catalog_candidates:
            continue

        target_popularity = [float(diag_popularity.get(target, 0)) for target in targets]
        target_buckets = [_quantile_bucket(pop, low, high) for pop in target_popularity]
        dominant_bucket = max(set(target_buckets), key=target_buckets.count)

        ranked_by_co = _top_catalog_by_cooccurrence(
            sorted_catalog=candidate_sorted_catalog,
            catalog_set=catalog_candidates,
            history=history,
            popularity=diag_popularity,
            adjacency=adjacency,
            rec_k=rec_k,
        )
        ranked_by_pop = _top_catalog_by_popularity(
            sorted_catalog=candidate_sorted_catalog,
            history=history,
            rec_k=rec_k,
        )
        ranked_by_sid = _top_catalog_by_sid_prefix_affinity(
            candidate_items=candidate_sorted_catalog,
            history=history,
            item_prefix=item_prefix,
            popularity=diag_popularity,
            adjacency=adjacency,
            rec_k=rec_k,
        )
        ranked_by_metadata = _top_catalog_by_metadata_category_affinity(
            candidate_items=candidate_sorted_catalog,
            history=history,
            item_categories=item_categories,
            popularity=diag_popularity,
            adjacency=adjacency,
            rec_k=rec_k,
        )
        for ranker, ranked in (
            (MAIN_RANKER, ranked_by_sid),
            (METADATA_RANKER, ranked_by_metadata),
            ("catalog_cooccurrence_popularity", ranked_by_co),
            ("catalog_popularity", ranked_by_pop),
        ):
            top_pos = {item: pos + 1 for pos, item in enumerate(ranked)}
            hit_ranks = [top_pos[target] for target in targets if target in top_pos]
            ideal_hits = min(len(targets), rec_k)
            ideal_dcg = _dcg(list(range(1, ideal_hits + 1))) if ideal_hits else 0.0
            user_rows.append(
                {
                    "dataset": row["dataset"],
                    "label": row["label"],
                    "method": row["method"],
                    "manifest_row": int(manifest_row),
                    "row_family": row["row_family"],
                    "gate2_role": row["gate2_role"],
                    "prefix_depth": int(depth),
                    "fold": int(fold),
                    "folds": int(folds),
                    "candidate_protocol": candidate_protocol,
                    "candidate_pool_size": int(len(catalog_candidates)),
                    "base_candidate_pool_size": int(candidate_pool_size),
                    "ranker": ranker,
                    "rec_k": int(rec_k),
                    "user_id": user,
                    "targets": int(len(targets)),
                    "candidate_count": int(len(catalog_candidates)),
                    "candidate_hits": int(len(candidate_hits)),
                    "candidate_recall": float(len(candidate_hits) / len(targets)),
                    "recall_at_k": float(len(hit_ranks) / len(targets)),
                    "ndcg_at_k": float(_dcg(hit_ranks) / ideal_dcg) if ideal_dcg else 0.0,
                    "mrr_at_k": float(1.0 / min(hit_ranks)) if hit_ranks else 0.0,
                    "mean_log_target_popularity_diag": float(np.mean(np.log1p(target_popularity))),
                    "dominant_popularity_bucket_diag": dominant_bucket,
                    "d3_weighted_disjoint": float(d3_weighted),
                    "d3_users": int(d3_users),
                    "d3_pair_events": int(d3_pair_events),
                    "diagnostic_users": int(len(diag_users)),
                    "ranking_users": int(len(ranking_users)),
                }
            )
    return user_rows


def _role_scope(include_supporting: bool) -> tuple[str, ...]:
    if include_supporting:
        return (*PRIMARY_ANALYSIS_ROLES, *SUPPORTING_ROLES)
    return PRIMARY_ANALYSIS_ROLES


def build_independent_rows(
    *,
    manifest: pd.DataFrame,
    depths: list[int],
    folds: int,
    rec_k: int,
    d3_top_k: int,
    max_pair_events: int,
    max_user_items: int,
    max_users: int,
    ranking_max_users_per_fold: int,
    include_supporting: bool,
    candidate_protocol: str,
    candidate_pool_size: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_user_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    roles = set(_role_scope(include_supporting))
    for row_idx, row in manifest.iterrows():
        if row.get("gate2_role") not in roles:
            continue
        sid, item_metadata, interactions = _filter_row_data(row)
        item_ids = set(sid["item_id"].astype(int))
        item_categories = _metadata_category_tokens(item_metadata)
        train, eval_events = _split_train_eval(interactions)
        train = train[train["item_id"].astype(int).isin(item_ids)].copy()
        eval_events = eval_events[eval_events["item_id"].astype(int).isin(item_ids)].copy()
        train_sizes = train[["user_id", "item_id"]].drop_duplicates().groupby("user_id").size()
        eligible = train_sizes[(train_sizes >= 1) & (train_sizes <= max_user_items)].index
        eligible_users = sorted(
            set(eligible).intersection(set(eval_events["user_id"])),
            key=lambda user: stable_mod(user, 2**31 - 1),
        )
        if max_users > 0:
            eligible_users = eligible_users[:max_users]
        level_count = len([col for col in sid.columns if col.startswith("sid_level_") and not sid[col].isna().all()])
        for depth in [depth for depth in depths if depth <= level_count]:
            item_prefix, _ = _build_prefix_index(sid, depth=depth)
            for fold in range(folds):
                fold_rows = _evaluate_fold(
                    sid=sid,
                    train=train,
                    eval_events=eval_events,
                    item_ids=item_ids,
                    item_prefix=item_prefix,
                    item_categories=item_categories,
                    eligible_users=eligible_users,
                    row=row,
                    manifest_row=row_idx,
                    depth=depth,
                    fold=fold,
                    folds=folds,
                    rec_k=rec_k,
                    d3_top_k=d3_top_k,
                    max_pair_events=max_pair_events,
                    max_user_items=max_user_items,
                    ranking_max_users_per_fold=ranking_max_users_per_fold,
                    candidate_protocol=candidate_protocol,
                    candidate_pool_size=candidate_pool_size,
                )
                all_user_rows.extend(fold_rows)
    user_metrics = pd.DataFrame(all_user_rows)
    if user_metrics.empty:
        return user_metrics, pd.DataFrame()

    group_cols = [
        "dataset",
        "label",
        "method",
        "manifest_row",
        "row_family",
        "gate2_role",
        "prefix_depth",
        "fold",
        "folds",
        "candidate_protocol",
        "base_candidate_pool_size",
        "ranker",
        "rec_k",
    ]
    for key, group in user_metrics.groupby(group_cols, dropna=False):
        base = dict(zip(group_cols, key))
        weights = group["targets"].astype(float).to_numpy()
        summary_rows.append(
            {
                **base,
                "users_with_eval_targets": int(group["user_id"].nunique()),
                "targets_evaluated": int(group["targets"].sum()),
                "mean_candidate_count": float(group["candidate_count"].mean()),
                "candidate_recall": float(np.average(group["candidate_recall"], weights=weights)),
                "recall_at_k": float(np.average(group["recall_at_k"], weights=weights)),
                "ndcg_at_k": float(np.average(group["ndcg_at_k"], weights=weights)),
                "mrr_at_k": float(np.average(group["mrr_at_k"], weights=weights)),
                "mean_log_target_popularity_diag": float(group["mean_log_target_popularity_diag"].mean()),
                "d3_weighted_disjoint": float(group["d3_weighted_disjoint"].iloc[0]),
                "d3_users": int(group["d3_users"].iloc[0]),
                "d3_pair_events": int(group["d3_pair_events"].iloc[0]),
                "diagnostic_users": int(group["diagnostic_users"].iloc[0]),
                "ranking_users": int(group["ranking_users"].iloc[0]),
            }
        )
    return user_metrics, pd.DataFrame(summary_rows)


def _summarize_metric(
    frame: pd.DataFrame,
    *,
    signal: str,
    outcome: str,
    unit_cols: list[str],
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    cols = [*unit_cols, signal, outcome]
    data = frame[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    collapsed = data.groupby(unit_cols, dropna=False)[[signal, outcome]].mean().reset_index()
    point = rank_corr(collapsed[signal], collapsed[outcome])
    if len(collapsed) < 4 or pd.isna(point) or bootstrap_samples <= 0:
        return {
            "signal": signal,
            "outcome": outcome,
            "unit": "+".join(unit_cols),
            "effective_n": int(len(collapsed)),
            "spearman": point,
            "ci_low": math.nan,
            "ci_high": math.nan,
            "bootstrap_samples": 0,
        }
    rng = np.random.default_rng(seed)
    values: list[float] = []
    indices = np.arange(len(collapsed))
    for _ in range(bootstrap_samples):
        sample = collapsed.iloc[rng.choice(indices, size=len(indices), replace=True)]
        value = rank_corr(sample[signal], sample[outcome])
        if not pd.isna(value):
            values.append(float(value))
    return {
        "signal": signal,
        "outcome": outcome,
        "unit": "+".join(unit_cols),
        "effective_n": int(len(collapsed)),
        "spearman": point,
        "ci_low": float(np.quantile(values, 0.025)) if values else math.nan,
        "ci_high": float(np.quantile(values, 0.975)) if values else math.nan,
        "bootstrap_samples": int(len(values)),
    }


def _leave_one_artifact(
    frame: pd.DataFrame,
    *,
    signal: str,
    outcome: str,
    unit_cols: list[str],
) -> dict[str, Any]:
    cols = list(dict.fromkeys([*_artifact_cols(), *unit_cols, signal, outcome]))
    data = frame[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    artifact_key = data[_artifact_cols()].astype(str).agg("::".join, axis=1)
    artifacts = sorted(set(artifact_key.tolist()))
    values: list[float] = []
    for artifact in artifacts:
        kept = data[artifact_key != artifact].copy()
        collapsed = kept.groupby(unit_cols, dropna=False)[[signal, outcome]].mean().reset_index()
        value = rank_corr(collapsed[signal], collapsed[outcome])
        if not pd.isna(value):
            values.append(float(value))
    return {
        "signal": signal,
        "outcome": outcome,
        "unit": "+".join(unit_cols),
        "artifacts": int(len(artifacts)),
        "loo_min_spearman": float(min(values)) if values else math.nan,
        "loo_max_spearman": float(max(values)) if values else math.nan,
        "loo_positive": int(sum(value > 0 for value in values)),
        "loo_runs": int(len(values)),
    }


def analyze_gate10(summary: pd.DataFrame, *, bootstrap_samples: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    primary = summary[summary["gate2_role"].isin(PRIMARY_ANALYSIS_ROLES)].copy()
    rows = []
    for ranker, scope in [
        (MAIN_RANKER, "primary_sid_prefix_affinity"),
        (METADATA_RANKER, "primary_metadata_category_control"),
        ("catalog_cooccurrence_popularity", "primary_cooccurrence_control"),
        ("catalog_popularity", "primary_popularity_control"),
    ]:
        frame = primary[primary["ranker"] == ranker].copy()
        for outcome in ["recall_at_k", "ndcg_at_k", "mrr_at_k"]:
            for unit_cols in [
                _artifact_cols(),
                [*_artifact_cols(), "prefix_depth"],
                [*_artifact_cols(), "prefix_depth", "fold"],
            ]:
                rows.append(
                    {
                        **_summarize_metric(
                            frame,
                            signal="d3_weighted_disjoint",
                            outcome=outcome,
                            unit_cols=unit_cols,
                            bootstrap_samples=bootstrap_samples,
                            seed=seed + len(rows) * 37,
                        ),
                        "scope": scope,
                    }
                )

    all_roles = summary.copy()
    co_ranker_all = all_roles[all_roles["ranker"] == MAIN_RANKER].copy()
    for outcome in ["recall_at_k", "ndcg_at_k", "mrr_at_k"]:
        rows.append(
            {
                **_summarize_metric(
                    co_ranker_all,
                    signal="d3_weighted_disjoint",
                    outcome=outcome,
                    unit_cols=[*_artifact_cols(), "prefix_depth"],
                    bootstrap_samples=bootstrap_samples,
                    seed=seed + len(rows) * 37,
                ),
                "scope": "all_included_roles",
            }
        )
    association = pd.DataFrame(rows)
    if "scope" not in association.columns:
        association["scope"] = "primary_roles"
    association["scope"] = association["scope"].fillna("primary_roles")

    loo_rows = []
    main_ranker = primary[primary["ranker"] == MAIN_RANKER].copy()
    for outcome in ["recall_at_k", "ndcg_at_k", "mrr_at_k"]:
        loo_rows.append(
            _leave_one_artifact(
                main_ranker,
                signal="d3_weighted_disjoint",
                outcome=outcome,
                unit_cols=[*_artifact_cols(), "prefix_depth"],
            )
        )
    loo = pd.DataFrame(loo_rows)
    return association, loo


def _pick_summary_row(
    table: pd.DataFrame,
    outcome: str,
    unit: str,
    scope: str = "primary_sid_prefix_affinity",
) -> dict[str, Any] | None:
    rows = table[(table["outcome"] == outcome) & (table["unit"] == unit) & (table["scope"] == scope)]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


def _fmt(value: Any) -> str:
    if value is None or pd.isna(value):
        return "nan"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_report(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Gate 10 Independent-Candidate Downstream Anchor Result",
        "",
        f"- gate: `{result['gate']}`",
        f"- verdict: `{result['verdict']}`",
        f"- built_pass_for_75_target: `{result['built_pass_for_75_target']}`",
        f"- independent_downstream_directional: `{result['independent_downstream_directional']}`",
        f"- independent_downstream_strong: `{result['independent_downstream_strong']}`",
        f"- primary_summary_rows: `{result['primary_summary_rows']}`",
        f"- primary_user_rows: `{result['primary_user_rows']}`",
        f"- effective_artifact_depth_n: `{result['effective_artifact_depth_n']}`",
        f"- candidate_protocol: `{result['candidate_protocol']}`",
        f"- main_ranker: `{result['main_ranker']}`",
        "",
        "## Primary Artifact-Depth Readout",
        "",
        "| Outcome | Spearman | 95% CI | Effective n |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, row in [
        ("recall_at_k", result["recall_artifact_depth"]),
        ("ndcg_at_k", result["ndcg_artifact_depth"]),
        ("mrr_at_k", result["mrr_artifact_depth"]),
    ]:
        lines.append(
            f"| `{label}` | {_fmt(row.get('spearman'))} | "
            f"[{_fmt(row.get('ci_low'))}, {_fmt(row.get('ci_high'))}] | "
            f"{_fmt(row.get('effective_n'))} |"
        )
    lines.extend(
        [
            "",
            "## Leave-One-Artifact Sensitivity",
            "",
            "| Outcome | LOO Spearman range | Positive runs |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in result["leave_one_artifact"]:
        lines.append(
            f"| `{row['outcome']}` | [{_fmt(row['loo_min_spearman'])}, {_fmt(row['loo_max_spearman'])}] | "
            f"{row['loo_positive']}/{row['loo_runs']} |"
        )
    lines.extend(["", "## Claim Update", "", result["claim_update"], "", "## Limitations"])
    lines.extend([f"- {item}" for item in result["limitations"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def close_gate10(
    *,
    g2_root: Path,
    output_root: Path,
    runs_dir: Path,
    depths: list[int],
    folds: int,
    rec_k: int,
    d3_top_k: int,
    max_pair_events: int,
    max_user_items: int,
    max_users: int,
    ranking_max_users_per_fold: int,
    bootstrap_samples: int,
    seed: int,
    include_supporting: bool,
    candidate_protocol: str,
    candidate_pool_size: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(g2_root / "g2_manifest.csv")
    user_metrics, summary = build_independent_rows(
        manifest=manifest,
        depths=depths,
        folds=folds,
        rec_k=rec_k,
        d3_top_k=d3_top_k,
        max_pair_events=max_pair_events,
        max_user_items=max_user_items,
        max_users=max_users,
        ranking_max_users_per_fold=ranking_max_users_per_fold,
        include_supporting=include_supporting,
        candidate_protocol=candidate_protocol,
        candidate_pool_size=candidate_pool_size,
    )
    user_metrics.to_csv(output_root / "g10_independent_user_metrics.csv", index=False)
    summary.to_csv(output_root / "g10_independent_fold_summary.csv", index=False)

    association, loo = analyze_gate10(summary, bootstrap_samples=bootstrap_samples, seed=seed)
    association.to_csv(output_root / "g10_independent_associations.csv", index=False)
    loo.to_csv(output_root / "g10_leave_one_artifact.csv", index=False)

    artifact_depth_unit = "dataset+label+method+manifest_row+prefix_depth"
    recall = _pick_summary_row(association, "recall_at_k", artifact_depth_unit) or {}
    ndcg = _pick_summary_row(association, "ndcg_at_k", artifact_depth_unit) or {}
    mrr = _pick_summary_row(association, "mrr_at_k", artifact_depth_unit) or {}
    independent_directional = (
        recall.get("effective_n", 0) >= 20
        and ndcg.get("effective_n", 0) >= 20
        and float(recall.get("spearman", math.nan)) > 0
        and float(ndcg.get("spearman", math.nan)) > 0
    )
    independent_strong = (
        independent_directional
        and float(recall.get("spearman", math.nan)) >= 0.30
        and float(ndcg.get("spearman", math.nan)) >= 0.30
    )
    built_pass = bool(independent_strong and float(ndcg.get("ci_low", -math.inf)) > 0)
    if built_pass:
        verdict = "built_pass_independent_candidate_downstream_anchor"
    elif independent_strong:
        verdict = "built_partial_independent_candidate_anchor_directional_ci_weak"
    elif independent_directional:
        verdict = "built_partial_independent_candidate_anchor_directional"
    else:
        verdict = "built_fail_independent_candidate_anchor_not_supported"

    result = {
        "schema": "sidinspector.v1.gate10.independent_utility.v1",
        "gate": "G10_INDEPENDENT_CANDIDATE_DOWNSTREAM_ANCHOR",
        "verdict": verdict,
        "built_pass_for_75_target": built_pass,
        "independent_downstream_directional": bool(independent_directional),
        "independent_downstream_strong": bool(independent_strong),
        "primary_summary_rows": int(len(summary[summary["gate2_role"].isin(PRIMARY_ANALYSIS_ROLES)])),
        "primary_user_rows": int(len(user_metrics[user_metrics["gate2_role"].isin(PRIMARY_ANALYSIS_ROLES)])),
        "all_summary_rows": int(len(summary)),
        "all_user_rows": int(len(user_metrics)),
        "effective_artifact_depth_n": int(recall.get("effective_n", 0) or 0),
        "folds": folds,
        "rec_k": rec_k,
        "max_users": max_users,
        "ranking_max_users_per_fold": ranking_max_users_per_fold,
        "candidate_protocol": candidate_protocol,
        "candidate_pool_size": int(candidate_pool_size),
        "main_ranker": MAIN_RANKER,
        "include_supporting": include_supporting,
        "recall_artifact_depth": recall,
        "ndcg_artifact_depth": ndcg,
        "mrr_artifact_depth": mrr,
        "leave_one_artifact": loo.to_dict(orient="records"),
        "artifacts": {
            "user_metrics": str(output_root / "g10_independent_user_metrics.csv"),
            "fold_summary": str(output_root / "g10_independent_fold_summary.csv"),
            "associations": str(output_root / "g10_independent_associations.csv"),
            "leave_one_artifact": str(output_root / "g10_leave_one_artifact.csv"),
            "report": str(output_root / "GATE10_RESULT.md"),
        },
        "claim_update": (
            "G10 tests whether D3 remains associated with fixed-reranker utility when "
            "the downstream candidate pool is independent of SID prefix retrieval. It "
            "is a stronger utility-anchor check than G9, but remains below trained "
            "generative-recommender evidence."
        ),
        "limitations": [
            "The ranker is fixed and train-only; G10 is not a trained generator or final recommender-quality result.",
            "The non-prefix candidate pool removes SID-prefix retrieval from the ranking step but still depends on artifact item coverage and the sampled/catalog pool definition.",
            "Primary inference remains artifact-level with modest independent artifact count; sensitivity rows should not be overread as new named-method breadth.",
        ],
    }
    (output_root / "g10_independent_utility_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (runs_dir / "R703_gate10_independent_utility.json").write_text(
        json.dumps({"run_id": "R703", **result}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(result, output_root / "GATE10_RESULT.md")
    return result


def _parse_int_list(text: str) -> list[int]:
    return [int(part) for part in text.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g2-root", type=Path, default=DEFAULT_G2_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--depths", default="1,2,3,4")
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--rec-k", type=int, default=20)
    parser.add_argument("--d3-top-k", type=int, default=20)
    parser.add_argument("--max-pair-events", type=int, default=2_000_000)
    parser.add_argument("--max-user-items", type=int, default=200)
    parser.add_argument("--max-users", type=int, default=5000)
    parser.add_argument(
        "--ranking-max-users-per-fold",
        type=int,
        default=100,
        help="Maximum held-out users per artifact/depth/fold for fixed-reranker metrics; -1 ranks all.",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260619)
    parser.add_argument(
        "--include-supporting",
        action="store_true",
        help="Include supporting official upstream rows in addition to primary roles for sensitivity.",
    )
    parser.add_argument(
        "--candidate-protocol",
        choices=CATALOG_PROTOCOLS,
        default="random_sampled_non_prefix",
        help="Non-prefix candidate-pool protocol for G10 ranking.",
    )
    parser.add_argument(
        "--candidate-pool-size",
        type=int,
        default=1000,
        help="Base popularity-pool size for popularity_sampled_non_prefix; targets are added before ranking.",
    )
    args = parser.parse_args()
    result = close_gate10(
        g2_root=args.g2_root,
        output_root=args.output_root,
        runs_dir=args.runs_dir,
        depths=_parse_int_list(args.depths),
        folds=args.folds,
        rec_k=args.rec_k,
        d3_top_k=args.d3_top_k,
        max_pair_events=args.max_pair_events,
        max_user_items=args.max_user_items,
        max_users=args.max_users,
        ranking_max_users_per_fold=args.ranking_max_users_per_fold,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
        include_supporting=args.include_supporting,
        candidate_protocol=args.candidate_protocol,
        candidate_pool_size=args.candidate_pool_size,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
