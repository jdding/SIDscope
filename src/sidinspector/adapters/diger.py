"""Normalize DIGER official-code-derived RQ-VAE SID artifacts.

DIGER's public route exposes processed item embeddings, an ``emb_map`` sidecar,
interaction JSONL files, and an RQ-VAE checkpoint. This adapter normalizes the
exported RQ-VAE indices into SIDScope tables. It uses the embedding row index as
SIDScope's numeric ``item_id`` and keeps the DIGER source id (for example,
``item_0``) plus the upstream token id for provenance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from sidinspector.interface import validate_columns


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_diger_emb_map(emb_map_path: Path) -> pd.DataFrame:
    """Read DIGER's source-item to embedding-token map.

    The upstream map reserves token ``0`` for ``[PAD]``. The embedding array is
    ordered by real items, so SIDScope uses ``token_id - 1`` as ``item_id``.
    """

    mapping = _read_json(emb_map_path)
    if not isinstance(mapping, dict):
        raise ValueError(f"Expected JSON object in {emb_map_path}")

    rows: list[dict[str, Any]] = []
    for source_item_id, raw_token_id in mapping.items():
        token_id = int(raw_token_id)
        if source_item_id == "[PAD]":
            if token_id != 0:
                raise ValueError("DIGER [PAD] token id must be 0")
            continue
        if token_id <= 0:
            raise ValueError(f"Unexpected non-positive DIGER token id for {source_item_id!r}: {token_id}")
        rows.append(
            {
                "item_id": token_id - 1,
                "source_item_id": str(source_item_id),
                "diger_token_id": token_id,
            }
        )

    out = pd.DataFrame(rows).sort_values("item_id", kind="stable").reset_index(drop=True)
    if out.empty:
        raise ValueError(f"{emb_map_path} contains no non-PAD item ids")
    if out["item_id"].duplicated().any():
        raise ValueError("DIGER emb_map contains duplicate SIDScope item_id values")
    if out["source_item_id"].duplicated().any():
        raise ValueError("DIGER emb_map contains duplicate source item ids")
    expected = list(range(len(out)))
    observed = out["item_id"].astype(int).tolist()
    if observed != expected:
        raise ValueError("DIGER item ids are not contiguous after excluding [PAD]")
    return out


def normalize_diger_codes(codes: np.ndarray, emb_map_path: Path, method: str, dataset: str) -> pd.DataFrame:
    """Normalize an exported ``n_items x depth`` DIGER code array."""

    if codes.ndim != 2:
        raise ValueError(f"Expected 2D DIGER code array, got shape={codes.shape}")
    item_map = read_diger_emb_map(emb_map_path)
    if len(item_map) != codes.shape[0]:
        raise ValueError(f"Code rows ({codes.shape[0]}) do not match emb_map rows ({len(item_map)})")

    rows: list[dict[str, Any]] = []
    for row_idx, code_row in enumerate(codes):
        item = item_map.iloc[row_idx]
        row: dict[str, Any] = {
            "item_id": int(item["item_id"]),
            "source_item_id": str(item["source_item_id"]),
            "diger_token_id": int(item["diger_token_id"]),
            "method": method,
            "dataset": dataset,
        }
        levels = [int(value) for value in code_row.tolist()]
        for level, value in enumerate(levels):
            row[f"sid_level_{level}"] = value
        row["sid"] = "-".join(str(value) for value in levels)
        rows.append(row)

    out = pd.DataFrame(rows)
    validate_columns("sid_assignments", out.columns)
    return out


def normalize_diger_metadata(emb_map_path: Path, dataset: str) -> pd.DataFrame:
    """Build minimal item metadata from DIGER's emb_map sidecar."""

    item_map = read_diger_emb_map(emb_map_path)
    out = item_map[["item_id", "source_item_id", "diger_token_id"]].copy()
    out["dataset"] = dataset
    out["category"] = "unknown"
    validate_columns("item_metadata", out.columns)
    return out


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no} expected JSON object")
            yield value


def normalize_diger_interactions(jsonl_paths: list[Path], emb_map_path: Path, dataset: str) -> pd.DataFrame:
    """Reconstruct one sequence per user from DIGER next-item JSONL rows.

    DIGER stores training examples as prefix-plus-target rows. Expanding every
    prefix would duplicate the same early events many times, so this adapter
    keeps the longest observed ``inter_history + target_id`` sequence per user
    across train/valid/test files.
    """

    item_map = read_diger_emb_map(emb_map_path)
    source_to_item = dict(zip(item_map["source_item_id"], item_map["item_id"]))
    user_sequences: dict[int, list[str]] = {}

    for path in jsonl_paths:
        for value in _iter_jsonl(path):
            user_id = int(value["user_id"])
            history = value.get("inter_history") or []
            if not isinstance(history, list):
                raise ValueError(f"{path} user {user_id} has invalid inter_history")
            target = value.get("target_id")
            if target is None:
                raise ValueError(f"{path} user {user_id} missing target_id")
            sequence = [str(item) for item in history] + [str(target)]
            if len(sequence) > len(user_sequences.get(user_id, [])):
                user_sequences[user_id] = sequence

    rows: list[dict[str, Any]] = []
    for user_id, sequence in sorted(user_sequences.items()):
        for position, source_item_id in enumerate(sequence):
            if source_item_id not in source_to_item:
                continue
            rows.append(
                {
                    "user_id": user_id,
                    "item_id": int(source_to_item[source_item_id]),
                    "source_item_id": source_item_id,
                    "dataset": dataset,
                    "position": position,
                }
            )

    out = pd.DataFrame(rows)
    validate_columns("interactions", out.columns)
    return out
