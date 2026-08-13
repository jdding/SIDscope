"""Close V1 Gate 2 with a two-vertical candidate-exposure utility package."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sidinspector import metrics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate2_cross_dataset_utility"
DEFAULT_RUNS_DIR = PROJECT_ROOT / "experiments/v1_evidence_chain/runs"

RETURNED_RESID = (
    PROJECT_ROOT
    / "experiments/v1_evidence_chain/autodl/returned/sidinspector_v1_gate1/"
    "resid_gaoq_unbalanced_closure_20260607T023600Z/gate1_named_resid_gaoq"
)
RESID_HF = PROJECT_ROOT / "experiments/v1_evidence_chain/gate1_build/resid_hf"
GRID_MUSICAL = PROJECT_ROOT / "experiments/v1_evidence_chain/gate1_grid_existing/Musical_Instruments"
GRID_FAITHFUL_BEAUTY = (
    PROJECT_ROOT / "experiments/v1_evidence_chain/gate1_named_grid_rkmeans/beauty/20260610T014829Z"
)
CARD_RQVAE_BEAUTY = PROJECT_ROOT / "experiments/v1_evidence_chain/gate15_card_rqvae_intake"
RESOT_TEXT_INTAKE = PROJECT_ROOT / "experiments/v1_evidence_chain/gate17_resot_intake/normalized_text"
DIGER_RQVAE_BEAUTY = PROJECT_ROOT / "experiments/v1_evidence_chain/gate17_diger_intake/normalized_rqvae_beauty"
DIGER_RQVAE_YELP = (
    PROJECT_ROOT
    / "experiments/v1_evidence_chain/gate23_non_amazon_route_expansion/intake/normalized_rqvae_yelp"
)
G23_MATRIX_ADMISSION = (
    PROJECT_ROOT
    / "experiments/v1_evidence_chain/gate23_non_amazon_route_expansion/G23_MATRIX_ADMISSION.json"
)
DEFAULT_V0_PROVENANCE_ROOT = (
    PROJECT_ROOT.parent / "SIDInspector-v0-review/_local_provenance/sidinspector_gate0/_gate0_artifacts"
)
GATE0 = Path(os.environ.get("SIDINSPECTOR_V0_PROVENANCE_ROOT", str(DEFAULT_V0_PROVENANCE_ROOT)))
PRIMARY_ANALYSIS_ROLES = (
    "primary_musical",
    "second_vertical_video",
    "faithful_grid_refresh",
    "paper_named_card_refresh",
    "paper_named_resot_refresh",
    "paper_named_diger_refresh",
    "paper_named_diger_yelp_refresh",
)


@dataclass(frozen=True)
class ManifestRow:
    label: str
    method: str
    dataset: str
    sid_assignments: Path
    item_metadata: Path
    interactions: Path
    row_family: str
    gate2_role: str


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matrix_admission_valid(admission_path: Path, normalized_root: Path) -> bool:
    try:
        admission = json.loads(admission_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if (
        admission.get("schema") != "sidscope.g23_matrix_admission.v1"
        or admission.get("route_id") != "diger_yelp"
        or admission.get("status") != "PASS_AUTHORIZED"
        or admission.get("matrix_change_authorized") is not True
    ):
        return False
    expected = admission.get("normalized_input_sha256")
    if not isinstance(expected, dict):
        return False
    paths = {
        "sid_assignments": normalized_root / "sid_assignments.parquet",
        "item_metadata": normalized_root / "item_metadata.parquet",
        "interactions": normalized_root / "interactions.parquet",
    }
    return all(
        path.is_file() and expected.get(name) == _sha256(path)
        for name, path in paths.items()
    )


def default_manifest_rows() -> list[ManifestRow]:
    """Return the current G1-backed rows used for the G2 utility gate."""

    musical_resid = RETURNED_RESID / "Musical_Instruments/pilot/Musical_Instruments/normalized"
    video_resid = RETURNED_RESID / "Video_Games/pilot/Video_Games/normalized"
    letter = GATE0 / "artifact_refresh_20260527/letter_instruments_official_normalized"
    lcrec = GATE0 / "lcrec_official_instruments_normalized"

    rows = [
        ManifestRow(
            label="letter_official_instruments",
            method="letter_official_rqvae",
            dataset="LETTER_Instruments",
            sid_assignments=letter / "sid_assignments.parquet",
            item_metadata=letter / "item_metadata.parquet",
            interactions=letter / "interactions.parquet",
            row_family="LETTER",
            gate2_role="supporting_official_upstream",
        ),
        ManifestRow(
            label="lcrec_official_instruments",
            method="lcrec_official_index",
            dataset="LCRec_Instruments",
            sid_assignments=lcrec / "sid_assignments.parquet",
            item_metadata=lcrec / "item_metadata.parquet",
            interactions=lcrec / "interactions.parquet",
            row_family="LC-Rec",
            gate2_role="supporting_official_upstream",
        ),
        ManifestRow(
            label="resid_gaoq_musical_pilot",
            method="resid_gaoq_official_code_pilot",
            dataset="Musical_Instruments",
            sid_assignments=musical_resid / "sid_assignments.parquet",
            item_metadata=musical_resid / "item_metadata.parquet",
            interactions=musical_resid / "interactions.parquet",
            row_family="ReSID_GAOQ",
            gate2_role="primary_musical",
        ),
        ManifestRow(
            label="grid_existing_musical",
            method="grid_official_rqkmeans_resid_feature_text",
            dataset="Musical_Instruments",
            sid_assignments=GRID_MUSICAL / "normalized/sid_assignments.parquet",
            item_metadata=musical_resid / "item_metadata.parquet",
            interactions=musical_resid / "interactions.parquet",
            row_family="GRID",
            gate2_role="primary_musical",
        ),
        ManifestRow(
            label="resid_hf_category_musical",
            method="resid_hf_category_control",
            dataset="Musical_Instruments",
            sid_assignments=RESID_HF / "Musical_Instruments/sid_assignments.parquet",
            item_metadata=RESID_HF / "Musical_Instruments/item_metadata.parquet",
            interactions=RESID_HF / "Musical_Instruments/interactions.parquet",
            row_family="deterministic_control",
            gate2_role="primary_musical",
        ),
        ManifestRow(
            label="local_rqkmeans_musical",
            method="local_rqkmeans_resid_hf_features",
            dataset="Musical_Instruments",
            sid_assignments=RESID_HF / "Musical_Instruments/sid_assignments.parquet",
            item_metadata=RESID_HF / "Musical_Instruments/item_metadata.parquet",
            interactions=RESID_HF / "Musical_Instruments/interactions.parquet",
            row_family="local_RQ_reference",
            gate2_role="primary_musical",
        ),
        ManifestRow(
            label="resid_gaoq_video_pilot",
            method="resid_gaoq_official_code_pilot",
            dataset="Video_Games",
            sid_assignments=video_resid / "sid_assignments.parquet",
            item_metadata=video_resid / "item_metadata.parquet",
            interactions=video_resid / "interactions.parquet",
            row_family="ReSID_GAOQ",
            gate2_role="second_vertical_video",
        ),
        ManifestRow(
            label="resid_hf_category_video",
            method="resid_hf_category_control",
            dataset="Video_Games",
            sid_assignments=RESID_HF / "Video_Games/sid_assignments.parquet",
            item_metadata=RESID_HF / "Video_Games/item_metadata.parquet",
            interactions=RESID_HF / "Video_Games/interactions.parquet",
            row_family="deterministic_control",
            gate2_role="second_vertical_video",
        ),
        ManifestRow(
            label="local_rqkmeans_video",
            method="local_rqkmeans_resid_hf_features",
            dataset="Video_Games",
            sid_assignments=RESID_HF / "Video_Games/sid_assignments.parquet",
            item_metadata=RESID_HF / "Video_Games/item_metadata.parquet",
            interactions=RESID_HF / "Video_Games/interactions.parquet",
            row_family="local_RQ_reference",
            gate2_role="second_vertical_video",
        ),
    ]
    faithful_grid = ManifestRow(
        label="grid_faithful_p5_beauty",
        method="grid_rkmeans_official_code",
        dataset="beauty",
        sid_assignments=GRID_FAITHFUL_BEAUTY / "R126_normalized/sid_assignments.parquet",
        item_metadata=GRID_FAITHFUL_BEAUTY / "R151_context/item_metadata.parquet",
        interactions=GRID_FAITHFUL_BEAUTY / "R151_context/interactions.parquet",
        row_family="GRID_faithful",
        gate2_role="faithful_grid_refresh",
    )
    if all(
        path.exists()
        for path in (faithful_grid.sid_assignments, faithful_grid.item_metadata, faithful_grid.interactions)
    ):
        rows.append(faithful_grid)
    card_rqvae = ManifestRow(
        label="card_rqvae_p5_beauty",
        method="card_rqvae_official_code_p5_text",
        dataset="beauty",
        sid_assignments=CARD_RQVAE_BEAUTY / "normalized/sid_assignments.parquet",
        item_metadata=CARD_RQVAE_BEAUTY / "context/item_metadata.parquet",
        interactions=CARD_RQVAE_BEAUTY / "context/interactions.parquet",
        row_family="CARD_RQVAE",
        gate2_role="paper_named_card_refresh",
    )
    if all(path.exists() for path in (card_rqvae.sid_assignments, card_rqvae.item_metadata, card_rqvae.interactions)):
        rows.append(card_rqvae)
    resot_text = ManifestRow(
        label="resot_text_index_instruments",
        method="resot_text_index_official_code_derived",
        dataset="Instruments",
        sid_assignments=RESOT_TEXT_INTAKE / "sid_assignments.parquet",
        item_metadata=RESOT_TEXT_INTAKE / "item_metadata.parquet",
        interactions=RESOT_TEXT_INTAKE / "interactions.parquet",
        row_family="ReSOT",
        gate2_role="paper_named_resot_refresh",
    )
    if all(path.exists() for path in (resot_text.sid_assignments, resot_text.item_metadata, resot_text.interactions)):
        rows.append(resot_text)
    diger_rqvae = ManifestRow(
        label="diger_rqvae_beauty",
        method="diger_rqvae_official_code_derived",
        dataset="beauty",
        sid_assignments=DIGER_RQVAE_BEAUTY / "sid_assignments.parquet",
        item_metadata=DIGER_RQVAE_BEAUTY / "item_metadata.parquet",
        interactions=DIGER_RQVAE_BEAUTY / "interactions.parquet",
        row_family="DIGER",
        gate2_role="paper_named_diger_refresh",
    )
    if all(path.exists() for path in (diger_rqvae.sid_assignments, diger_rqvae.item_metadata, diger_rqvae.interactions)):
        rows.append(diger_rqvae)
    diger_yelp = ManifestRow(
        label="diger_rqvae_yelp",
        method="diger_rqvae_official_code_derived",
        dataset="yelp",
        sid_assignments=DIGER_RQVAE_YELP / "sid_assignments.parquet",
        item_metadata=DIGER_RQVAE_YELP / "item_metadata.parquet",
        interactions=DIGER_RQVAE_YELP / "interactions.parquet",
        row_family="DIGER",
        gate2_role="paper_named_diger_yelp_refresh",
    )
    if _matrix_admission_valid(G23_MATRIX_ADMISSION, DIGER_RQVAE_YELP):
        rows.append(diger_yelp)
    return rows


def _sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def _write_manifest(rows: list[ManifestRow], path: Path) -> pd.DataFrame:
    records = []
    missing = []
    for row in rows:
        for attr in ("sid_assignments", "item_metadata", "interactions"):
            file_path = getattr(row, attr)
            if not file_path.exists():
                missing.append(str(file_path))
        records.append(
            {
                "label": row.label,
                "method": row.method,
                "dataset": row.dataset,
                "sid_assignments": str(row.sid_assignments),
                "item_metadata": str(row.item_metadata),
                "interactions": str(row.interactions),
                "row_family": row.row_family,
                "gate2_role": row.gate2_role,
            }
        )
    if missing:
        raise FileNotFoundError("Missing Gate2 manifest inputs:\n" + "\n".join(missing))
    frame = pd.DataFrame(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def _filter_row_data(row: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sid = pd.read_parquet(row["sid_assignments"])
    metadata = pd.read_parquet(row["item_metadata"])
    interactions = pd.read_parquet(row["interactions"])
    if "method" in sid.columns:
        sid = sid[sid["method"].astype(str) == str(row["method"])].copy()
    if "dataset" in sid.columns:
        sid = sid[sid["dataset"].astype(str) == str(row["dataset"])].copy()
    if "dataset" in metadata.columns:
        metadata = metadata[metadata["dataset"].astype(str) == str(row["dataset"])].copy()
    if "dataset" in interactions.columns:
        interactions = interactions[interactions["dataset"].astype(str) == str(row["dataset"])].copy()
    if sid.empty:
        raise ValueError(f"Manifest row selects no SID rows: {row['label']}")
    return sid, metadata, interactions


def _level_cols(frame: pd.DataFrame) -> list[str]:
    return sorted(
        [col for col in frame.columns if col.startswith("sid_level_") and not frame[col].isna().all()],
        key=lambda col: int(col.rsplit("_", 1)[1]),
    )


def _split_train_eval(interactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = interactions.copy()
    frame["item_id"] = frame["item_id"].astype(int)
    if "split" in frame.columns and (frame["split"].astype(str) == "train").any():
        train = frame[frame["split"].astype(str) == "train"].copy()
        eval_events = frame[frame["split"].astype(str) != "train"].copy()
        return train, eval_events

    order_cols = ["user_id"]
    if "timestamp" in frame.columns:
        order_cols.append("timestamp")
    elif "position" in frame.columns:
        order_cols.append("position")
    frame = frame.sort_values(order_cols, kind="stable").copy()
    frame["_rank"] = frame.groupby("user_id").cumcount()
    frame["_count"] = frame.groupby("user_id")["item_id"].transform("size")
    eligible = frame["_count"] >= 2
    eval_events = frame[eligible & (frame["_rank"] == frame["_count"] - 1)].copy()
    train = frame[eligible & (frame["_rank"] < frame["_count"] - 1)].copy()
    return train.drop(columns=["_rank", "_count"]), eval_events.drop(columns=["_rank", "_count"])


def _prefix_maps(sid: pd.DataFrame, depth: int) -> tuple[dict[int, tuple[Any, ...]], dict[tuple[Any, ...], int]]:
    level_cols = _level_cols(sid)
    if depth < 1 or depth > len(level_cols):
        raise ValueError(f"Invalid prefix depth {depth}; SID has {len(level_cols)} levels")
    item_prefix: dict[int, tuple[Any, ...]] = {}
    prefix_sizes: dict[tuple[Any, ...], int] = {}
    for row in sid[["item_id", *level_cols[:depth]]].itertuples(index=False):
        item_id = int(row.item_id)
        prefix = tuple(getattr(row, col) for col in level_cols[:depth])
        item_prefix[item_id] = prefix
        prefix_sizes[prefix] = prefix_sizes.get(prefix, 0) + 1
    return item_prefix, prefix_sizes


def _stable_shard(value: Any, shards: int) -> int:
    if shards <= 0:
        raise ValueError("shards must be positive")
    digest = hashlib.blake2b(str(value).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False) % shards


def run_prefix_exposure(
    manifest: pd.DataFrame,
    output_dir: Path,
    depths: list[int],
    max_users: int,
    max_user_items: int,
    shards: int,
) -> dict[str, Any]:
    """Compute fast train-only prefix sibling exposure for G2.

    This is intentionally narrower than ``downstream_probe``: G2 asks whether
    mapping diagnostics predict candidate exposure before ranking/generation.
    Ranking and final Recall/NDCG are left to G3.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    user_rows = []
    summary_rows = []
    for row_idx, row in manifest.iterrows():
        sid, _, interactions = _filter_row_data(row)
        item_ids = set(sid["item_id"].astype(int))
        train, eval_events = _split_train_eval(interactions)
        train = train[train["item_id"].astype(int).isin(item_ids)].copy()
        eval_events = eval_events[eval_events["item_id"].astype(int).isin(item_ids)].copy()
        train_sizes = train[["user_id", "item_id"]].drop_duplicates().groupby("user_id").size()
        eligible_users = train_sizes[(train_sizes >= 1) & (train_sizes <= max_user_items)].index
        users = sorted(set(eligible_users).intersection(set(eval_events["user_id"])))
        if max_users > 0:
            users = users[:max_users]
        train = train[train["user_id"].isin(users)]
        eval_events = eval_events[eval_events["user_id"].isin(users)]
        train_by_user = {
            user: [int(item) for item in group["item_id"].drop_duplicates()]
            for user, group in train.groupby("user_id", sort=False)
        }
        eval_by_user = {
            user: [int(item) for item in group["item_id"]]
            for user, group in eval_events.groupby("user_id", sort=False)
        }

        for depth in depths:
            item_prefix, prefix_sizes = _prefix_maps(sid, depth=depth)
            for user in sorted(set(train_by_user).intersection(eval_by_user)):
                history = [item for item in train_by_user[user] if item in item_prefix]
                targets = [item for item in eval_by_user[user] if item in item_prefix]
                if not history or not targets:
                    continue
                history_prefixes = {item_prefix[item] for item in history}
                history_by_prefix: dict[tuple[Any, ...], int] = {}
                for item in history:
                    prefix = item_prefix[item]
                    history_by_prefix[prefix] = history_by_prefix.get(prefix, 0) + 1
                candidate_count = sum(prefix_sizes[prefix] - history_by_prefix.get(prefix, 0) for prefix in history_prefixes)
                candidate_hits = sum(1 for target in targets if item_prefix[target] in history_prefixes and target not in history)
                user_rows.append(
                    {
                        "dataset": row["dataset"],
                        "label": row["label"],
                        "method": row["method"],
                        "manifest_row": int(row_idx),
                        "prefix_depth": depth,
                        "ranker": "prefix_candidate_exposure",
                        "rec_k": 0,
                        "user_id": user,
                        "shard": _stable_shard(user, shards),
                        "targets": len(targets),
                        "candidate_count": int(candidate_count),
                        "candidate_hits": int(candidate_hits),
                        "candidate_recall": float(candidate_hits / len(targets)),
                    }
                )

    user_metrics = pd.DataFrame(user_rows)
    if not user_metrics.empty:
        grouped = user_metrics.groupby(
            ["dataset", "label", "method", "manifest_row", "prefix_depth", "ranker", "rec_k", "shard"],
            dropna=False,
        )
        for key, group in grouped:
            dataset, label, method, manifest_row, prefix_depth, ranker, rec_k, shard = key
            summary_rows.append(
                {
                    "dataset": dataset,
                    "label": label,
                    "method": method,
                    "manifest_row": int(manifest_row),
                    "prefix_depth": int(prefix_depth),
                    "ranker": ranker,
                    "rec_k": int(rec_k),
                    "shard": int(shard),
                    "users_with_eval_targets": int(len(group)),
                    "targets_evaluated": int(group["targets"].sum()),
                    "mean_candidate_count": float(group["candidate_count"].mean()),
                    "median_candidate_count": float(group["candidate_count"].median()),
                    "candidate_recall": float(np.average(group["candidate_recall"], weights=group["targets"])),
                    "candidate_recall_ci_low": float(group["candidate_recall"].quantile(0.025)),
                    "candidate_recall_ci_high": float(group["candidate_recall"].quantile(0.975)),
                    "recall_at_k": math.nan,
                    "ndcg_at_k": math.nan,
                }
            )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "prefix_exposure_summary.csv", index=False)
    user_metrics.to_csv(output_dir / "prefix_exposure_user_metrics.csv", index=False)
    manifest.to_csv(output_dir / "prefix_exposure_manifest_resolved.csv", index=False)
    metadata = {
        "probe": "prefix_candidate_exposure",
        "depths": depths,
        "max_users": max_users,
        "max_user_items": max_user_items,
        "shards": shards,
        "summary_rows": int(len(summary)),
        "user_rows": int(len(user_metrics)),
    }
    (output_dir / "prefix_exposure_run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _diagnostics_for_row(
    row: pd.Series,
    metrics_root: Path,
    d3_top_k: int,
    max_pair_events: int,
    max_user_items: int,
) -> pd.DataFrame:
    sid, metadata, interactions = _filter_row_data(row)
    out_dir = metrics_root / _sanitize(str(row["label"]))
    out_dir.mkdir(parents=True, exist_ok=True)

    d1 = metrics.utilization(sid).rename(
        columns={"entropy": "d1_entropy", "gini": "d1_gini", "unique_codes": "d1_unique_codes"}
    )
    d1["prefix_depth"] = d1["level"].astype(str).str.rsplit("_", n=1).str[-1].astype(int) + 1
    d1 = d1.drop(columns=["level", "items", "max_code"], errors="ignore")

    d2 = metrics.collision(sid, interactions).rename(
        columns={
            "full_collision_rate": "d2_full_collision_rate",
            "prefix_collision_rate": "d2_prefix_collision_rate",
            "prefix_collision_items": "d2_prefix_collision_items",
        }
    )
    d2 = d2[
        [
            "dataset",
            "method",
            "prefix_depth",
            "d2_full_collision_rate",
            "d2_prefix_collision_rate",
            "d2_prefix_collision_items",
        ]
    ]

    d3 = metrics.alignment(
        sid,
        metadata,
        interactions,
        top_k=d3_top_k,
        max_pair_events=max_pair_events,
        max_user_items=max_user_items,
    ).rename(
        columns={
            "mean_collab_prefix_recall": "d3_mean_collab_prefix_recall",
            "weighted_collab_prefix_recall": "d3_weighted_collab_prefix_recall",
            "collab_edges_same_prefix_rate": "d3_edges_same_prefix_rate",
        }
    )
    d3 = d3[
        [
            "dataset",
            "method",
            "prefix_depth",
            "d3_mean_collab_prefix_recall",
            "d3_weighted_collab_prefix_recall",
            "d3_edges_same_prefix_rate",
            "level0_category_purity_mean",
        ]
    ].rename(columns={"level0_category_purity_mean": "d3_level0_category_purity_mean"})

    d4 = metrics.head_tail_capacity(sid, interactions)
    d4_pivot = d4.pivot_table(
        index=["dataset", "method"], columns="bucket", values="sid_unique_ratio", aggfunc="mean"
    ).reset_index()
    for bucket in ("head", "mid", "tail"):
        if bucket not in d4_pivot.columns:
            d4_pivot[bucket] = np.nan
    d4_pivot = d4_pivot.rename(
        columns={
            "head": "d4_head_sid_unique_ratio",
            "mid": "d4_mid_sid_unique_ratio",
            "tail": "d4_tail_sid_unique_ratio",
        }
    )
    d4_pivot["d4_head_tail_unique_ratio_gap"] = (
        d4_pivot["d4_head_sid_unique_ratio"] - d4_pivot["d4_tail_sid_unique_ratio"]
    )

    d5 = metrics.deployment_cost(sid).rename(columns={"duplicate_sid_rate": "d5_duplicate_sid_rate"})
    d5 = d5[["dataset", "method", "sid_length", "unique_sid", "d5_duplicate_sid_rate", "prefix_counts"]]

    merged = d1.merge(d2, on=["dataset", "method", "prefix_depth"], how="outer")
    merged = merged.merge(d3, on=["dataset", "method", "prefix_depth"], how="outer")
    merged = merged.merge(d4_pivot, on=["dataset", "method"], how="left")
    merged = merged.merge(d5, on=["dataset", "method"], how="left")
    merged["label"] = row["label"]
    merged["row_family"] = row["row_family"]
    merged["gate2_role"] = row["gate2_role"]

    d1.to_csv(out_dir / "d1_utilization.csv", index=False)
    d2.to_csv(out_dir / "d2_collision.csv", index=False)
    d3.to_csv(out_dir / "d3_alignment.csv", index=False)
    d4.to_csv(out_dir / "d4_head_tail.csv", index=False)
    d5.to_csv(out_dir / "d5a_deployment_cost.csv", index=False)
    merged.to_csv(out_dir / "d1_d5_merged.csv", index=False)
    return merged


def build_diagnostics(
    manifest: pd.DataFrame,
    metrics_root: Path,
    d3_top_k: int,
    max_pair_events: int,
    max_user_items: int,
) -> pd.DataFrame:
    frames = [
        _diagnostics_for_row(
            row,
            metrics_root,
            d3_top_k=d3_top_k,
            max_pair_events=max_pair_events,
            max_user_items=max_user_items,
        )
        for _, row in manifest.iterrows()
    ]
    diagnostics = pd.concat(frames, ignore_index=True)
    diagnostics.to_csv(metrics_root / "d1_d5_merged_all_rows.csv", index=False)
    return diagnostics


def _bootstrap_spearman(
    frame: pd.DataFrame,
    x: str,
    y: str,
    samples: int,
    seed: int,
) -> tuple[float, float, float]:
    data = frame[[x, y]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < 3 or data[x].nunique() < 2 or data[y].nunique() < 2:
        return math.nan, math.nan, math.nan
    point = float(data[x].corr(data[y], method="spearman"))
    if samples <= 0:
        return point, point, point
    rng = np.random.default_rng(seed)
    values = []
    index = np.arange(len(data))
    for _ in range(samples):
        sample = data.iloc[rng.choice(index, size=len(index), replace=True)]
        if sample[x].nunique() < 2 or sample[y].nunique() < 2:
            continue
        value = sample[x].corr(sample[y], method="spearman")
        if pd.notna(value):
            values.append(float(value))
    if not values:
        return point, math.nan, math.nan
    return point, float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def _analysis_scopes(joined: pd.DataFrame) -> dict[str, pd.DataFrame]:
    primary = joined[joined["gate2_role"].isin(PRIMARY_ANALYSIS_ROLES)].copy()
    return {
        "primary_refresh_scope": primary,
        "musical_primary": joined[joined["gate2_role"] == "primary_musical"].copy(),
        "video_second_vertical": joined[joined["gate2_role"] == "second_vertical_video"].copy(),
        "faithful_grid_refresh": joined[joined["gate2_role"] == "faithful_grid_refresh"].copy(),
        "paper_named_card_refresh": joined[joined["gate2_role"] == "paper_named_card_refresh"].copy(),
        "with_official_supporting_rows": joined.copy(),
    }


def analyze_utility(
    *,
    exposure_summary_path: Path,
    diagnostics: pd.DataFrame,
    manifest: pd.DataFrame,
    output_root: Path,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    summary = pd.read_csv(exposure_summary_path)
    joined = summary.merge(
        diagnostics,
        on=["dataset", "method", "prefix_depth"],
        how="left",
        suffixes=("", "_diagnostic"),
    )
    joined = joined.merge(
        manifest[["label", "method", "dataset", "row_family", "gate2_role"]],
        on=["label", "method", "dataset"],
        how="left",
        suffixes=("", "_manifest"),
    )
    for col in ("row_family", "gate2_role"):
        joined[col] = joined[col].combine_first(joined.get(f"{col}_manifest"))
    joined = joined.drop(columns=[c for c in joined.columns if c.endswith("_manifest")], errors="ignore")

    diagnostic_cols = [
        "d1_entropy",
        "d1_gini",
        "d1_unique_codes",
        "d2_full_collision_rate",
        "d2_prefix_collision_rate",
        "d3_weighted_collab_prefix_recall",
        "d3_edges_same_prefix_rate",
        "d4_head_tail_unique_ratio_gap",
        "d5_duplicate_sid_rate",
        "sid_length",
        "unique_sid",
    ]
    outcome_cols = ["candidate_recall", "mean_candidate_count"]
    rows = []
    for scope_name, scope_frame in _analysis_scopes(joined).items():
        for x in diagnostic_cols:
            if x not in scope_frame.columns:
                continue
            for y in outcome_cols:
                rho, lo, hi = _bootstrap_spearman(
                    scope_frame,
                    x=x,
                    y=y,
                    samples=bootstrap_samples,
                    seed=seed + len(rows) * 17,
                )
                rows.append(
                    {
                        "scope": scope_name,
                        "diagnostic": x,
                        "outcome": y,
                        "spearman": rho,
                        "ci_low": lo,
                        "ci_high": hi,
                        "rows": int(scope_frame[[x, y]].dropna().shape[0]),
                        "datasets": ";".join(sorted(scope_frame["dataset"].astype(str).unique())),
                        "methods": int(scope_frame[["dataset", "method"]].drop_duplicates().shape[0]),
                    }
                )
    association = pd.DataFrame(rows)
    analysis_dir = output_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    joined.to_csv(analysis_dir / "g2_probe_diagnostics_joined.csv", index=False)
    association.to_csv(analysis_dir / "g2_diagnostic_exposure_associations.csv", index=False)

    row_counts = (
        joined.groupby(["gate2_role", "dataset"], dropna=False)
        .agg(
            evaluated_rows=("candidate_recall", "size"),
            methods=("method", "nunique"),
            users_with_eval_targets=("users_with_eval_targets", "sum"),
            targets_evaluated=("targets_evaluated", "sum"),
        )
        .reset_index()
    )
    row_counts.to_csv(analysis_dir / "g2_row_counts.csv", index=False)

    primary_assoc = association[
        (association["scope"] == "primary_refresh_scope")
        & (association["outcome"].isin(["candidate_recall", "mean_candidate_count"]))
    ].copy()
    primary_assoc["abs_spearman"] = primary_assoc["spearman"].abs()
    primary_assoc = primary_assoc.sort_values(
        ["abs_spearman", "rows", "diagnostic"], ascending=[False, False, True], na_position="last"
    )
    best = primary_assoc.head(8).drop(columns=["abs_spearman"], errors="ignore")
    best.to_csv(analysis_dir / "g2_top_primary_associations.csv", index=False)

    musical_rows = int(row_counts.loc[row_counts["gate2_role"] == "primary_musical", "evaluated_rows"].sum())
    video_rows = int(row_counts.loc[row_counts["gate2_role"] == "second_vertical_video", "evaluated_rows"].sum())
    faithful_grid_rows = int(
        row_counts.loc[row_counts["gate2_role"] == "faithful_grid_refresh", "evaluated_rows"].sum()
    )
    card_refresh_rows = int(
        row_counts.loc[row_counts["gate2_role"] == "paper_named_card_refresh", "evaluated_rows"].sum()
    )
    resot_refresh_rows = int(
        row_counts.loc[row_counts["gate2_role"] == "paper_named_resot_refresh", "evaluated_rows"].sum()
    )
    diger_refresh_rows = int(
        row_counts.loc[row_counts["gate2_role"] == "paper_named_diger_refresh", "evaluated_rows"].sum()
    )
    diger_yelp_refresh_rows = int(
        row_counts.loc[
            row_counts["gate2_role"] == "paper_named_diger_yelp_refresh", "evaluated_rows"
        ].sum()
    )
    primary_rows = int(
        row_counts.loc[
            row_counts["gate2_role"].isin(PRIMARY_ANALYSIS_ROLES), "evaluated_rows"
        ].sum()
    )
    has_interpretable_signal = bool(
        (primary_assoc["rows"] >= 30).any()
        and (primary_assoc["spearman"].abs() >= 0.30).any()
    )
    built_pass = musical_rows >= 30 and video_rows >= 30 and has_interpretable_signal
    verdict = (
        "built_pass_two_vertical_candidate_exposure_utility"
        if built_pass
        else "built_partial_candidate_exposure_evaluated_but_utility_signal_weak"
    )
    result = {
        "schema": "sidinspector.v1.gate2.cross_dataset_utility.v1",
        "gate": "G2_CROSS_DATASET_UTILITY",
        "verdict": verdict,
        "built_pass_for_70_target": built_pass,
        "primary_rows": primary_rows,
        "musical_primary_rows": musical_rows,
        "video_second_vertical_rows": video_rows,
        "faithful_grid_refresh_rows": faithful_grid_rows,
        "card_refresh_rows": card_refresh_rows,
        "resot_refresh_rows": resot_refresh_rows,
        "diger_refresh_rows": diger_refresh_rows,
        "diger_yelp_refresh_rows": diger_yelp_refresh_rows,
        "manifest_rows": int(len(manifest)),
        "diagnostic_association_rows": int(len(association)),
        "top_primary_associations": best.to_dict(orient="records"),
        "row_counts": row_counts.to_dict(orient="records"),
        "artifacts": {
            "joined": str(analysis_dir / "g2_probe_diagnostics_joined.csv"),
            "associations": str(analysis_dir / "g2_diagnostic_exposure_associations.csv"),
            "row_counts": str(analysis_dir / "g2_row_counts.csv"),
            "top_primary_associations": str(analysis_dir / "g2_top_primary_associations.csv"),
        },
        "limitations": [
            "G2 measures fixed candidate exposure, not final trained generator quality.",
            "Official LETTER/LC-Rec rows are supporting upstream rows; the G2 two-vertical pass rests on Musical_Instruments plus Video_Games.",
            "Faithful GRID/P5 Beauty, CARD RQ-VAE/P5 Beauty, and DIGER RQ-VAE/Beauty are included as paper-named refresh rows, not as replacements for the existing two-vertical pass criterion.",
            "CARD RQ-VAE/P5 Beauty is official-code-derived with a local compatibility shim, not an author-released CARD mapping.",
            "ReSOT/Instruments is a released-archive text-index intake row; keep the no-license-detected reuse caveat visible.",
            "DIGER RQ-VAE/Beauty is official-code-derived from public embeddings and a public checkpoint, not an author-released item-to-SID table or full DIGER differentiable-assignment reproduction.",
            "DIGER RQ-VAE/Yelp is a non-Amazon contract-portability row from the same upstream family; Beauty-Yelp differences are descriptive because dataset, checkpoint, and checkpoint configuration all differ.",
            "G3 remains required for controlled popularity/depth/collision modeling.",
        ],
    }
    (analysis_dir / "g2_utility_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _write_run_records(
    *,
    runs_dir: Path,
    output_root: Path,
    manifest_path: Path,
    result: dict[str, Any],
    probe_metadata: dict[str, Any],
) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "run_id": "R201",
            "gate": "G2_CROSS_DATASET_UTILITY",
            "verdict": "manifest_built_pass",
            "artifact": str(manifest_path),
            "manifest_rows": result["manifest_rows"],
        },
        {
            "run_id": "R202",
            "gate": "G2_CROSS_DATASET_UTILITY",
            "verdict": "candidate_exposure_probe_built_pass",
            "artifact": str(output_root / "probe/prefix_exposure_summary.csv"),
            "probe_metadata": probe_metadata,
        },
        {
            "run_id": "R203",
            "gate": "G2_CROSS_DATASET_UTILITY",
            "verdict": "d1_d5_diagnostics_built_pass",
            "artifact": str(output_root / "metrics/d1_d5_merged_all_rows.csv"),
        },
        {
            "run_id": "R204",
            "gate": "G2_CROSS_DATASET_UTILITY",
            "verdict": "association_analysis_built_pass",
            "artifact": result["artifacts"]["associations"],
            "built_pass_for_70_target": result["built_pass_for_70_target"],
        },
        {
            "run_id": "R205",
            "gate": "G2_CROSS_DATASET_UTILITY",
            "verdict": result["verdict"],
            "built_pass_for_70_target": result["built_pass_for_70_target"],
            "artifact": str(output_root / "analysis/g2_utility_result.json"),
            "primary_rows": result["primary_rows"],
            "musical_primary_rows": result["musical_primary_rows"],
            "video_second_vertical_rows": result["video_second_vertical_rows"],
            "faithful_grid_refresh_rows": result["faithful_grid_refresh_rows"],
            "card_refresh_rows": result["card_refresh_rows"],
            "resot_refresh_rows": result["resot_refresh_rows"],
            "diger_refresh_rows": result["diger_refresh_rows"],
            "diger_yelp_refresh_rows": result["diger_yelp_refresh_rows"],
            "limitations": result["limitations"],
        },
    ]
    for record in records:
        payload = {
            "schema": "sidinspector.v1.run_record.v1",
            "date": "2026-06-07",
            **record,
        }
        path = runs_dir / f"{record['run_id']}_gate2_cross_dataset_utility.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_float(value: Any) -> str:
    if value is None or pd.isna(value):
        return "nan"
    return f"{float(value):.3f}"


def _write_report(output_root: Path, result: dict[str, Any]) -> None:
    top = result["top_primary_associations"][:6]
    lines = [
        "# Gate 2 Cross-Dataset Utility Result",
        "",
        "STATUS: " + ("BUILT_PASS_FOR_70_TARGET" if result["built_pass_for_70_target"] else "PARTIAL_PASS"),
        f"VERDICT: {result['verdict']}",
        "",
        "## Scope",
        "",
        "- Primary vertical: `Musical_Instruments`.",
        "- Second vertical: `Video_Games`.",
        "- Faithful GRID refresh vertical: `beauty`.",
        "- CARD RQ-VAE paper-named refresh vertical: `beauty`.",
        "- DIGER RQ-VAE paper-named refresh vertical: `beauty`.",
        "- DIGER RQ-VAE non-Amazon refresh vertical: `yelp`.",
        "- ReSOT text-index paper-named refresh vertical: `Instruments`.",
        "- Supporting upstream rows: `LETTER_Instruments`, `LCRec_Instruments`.",
        "- Outcome: fixed train-only candidate exposure, not final downstream quality.",
        "",
        "## Row Counts",
        "",
        f"- Primary refresh-scope evaluated rows: {result['primary_rows']}.",
        f"- Musical primary evaluated rows: {result['musical_primary_rows']}.",
        f"- Video second-vertical evaluated rows: {result['video_second_vertical_rows']}.",
        f"- Faithful GRID refresh evaluated rows: {result['faithful_grid_refresh_rows']}.",
        f"- CARD RQ-VAE refresh evaluated rows: {result['card_refresh_rows']}.",
        f"- DIGER RQ-VAE refresh evaluated rows: {result['diger_refresh_rows']}.",
        f"- DIGER RQ-VAE/Yelp refresh evaluated rows: {result['diger_yelp_refresh_rows']}.",
        f"- ReSOT text-index refresh evaluated rows: {result['resot_refresh_rows']}.",
        f"- Manifest rows: {result['manifest_rows']}.",
        "",
        "## Strongest Primary Associations",
        "",
        "| Diagnostic | Outcome | Spearman | 95% bootstrap CI | Rows |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in top:
        lines.append(
            "| {diagnostic} | {outcome} | {rho} | [{lo}, {hi}] | {rows} |".format(
                diagnostic=row["diagnostic"],
                outcome=row["outcome"],
                rho=_format_float(row["spearman"]),
                lo=_format_float(row["ci_low"]),
                hi=_format_float(row["ci_high"]),
                rows=row["rows"],
            )
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in result["limitations"]],
            "",
            "## Artifacts",
            "",
            *[f"- `{key}`: `{value}`" for key, value in result["artifacts"].items()],
            "",
        ]
    )
    (output_root / "GATE2_RESULT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run V1 Gate 2 cross-dataset utility closure.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--depths", default="1,2,3")
    parser.add_argument("--d3-top-k", type=int, default=20)
    parser.add_argument("--max-users", type=int, default=1000)
    parser.add_argument("--max-pair-events", type=int, default=50_000)
    parser.add_argument("--max-user-items", type=int, default=50)
    parser.add_argument("--shards", type=int, default=10)
    parser.add_argument("--bootstrap-samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / "g2_manifest.csv"
    manifest = _write_manifest(default_manifest_rows(), manifest_path)

    probe_dir = args.output_root / "probe"
    probe_metadata = run_prefix_exposure(
        manifest=manifest,
        output_dir=probe_dir,
        depths=[int(part) for part in args.depths.split(",") if part.strip()],
        max_users=args.max_users,
        max_user_items=args.max_user_items,
        shards=args.shards,
    )
    diagnostics = build_diagnostics(
        manifest=manifest,
        metrics_root=args.output_root / "metrics",
        d3_top_k=args.d3_top_k,
        max_pair_events=args.max_pair_events,
        max_user_items=args.max_user_items,
    )
    result = analyze_utility(
        exposure_summary_path=probe_dir / "prefix_exposure_summary.csv",
        diagnostics=diagnostics,
        manifest=manifest,
        output_root=args.output_root,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    _write_run_records(
        runs_dir=args.runs_dir,
        output_root=args.output_root,
        manifest_path=manifest_path,
        result=result,
        probe_metadata=probe_metadata,
    )
    _write_report(args.output_root, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["built_pass_for_70_target"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
