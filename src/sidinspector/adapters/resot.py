"""Normalize ReSOT released JSON semantic-ID artifacts.

ReSOT's released archive stores completed item-to-code JSON files keyed by
internal dense item ids and a sibling ``item2id`` file that maps source ASINs to
those ids. SIDScope's current metric stack expects numeric ``item_id`` values,
so this adapter uses the dense id as ``item_id`` and keeps the ASIN in
``source_item_id`` for provenance.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from sidinspector.interface import validate_columns


TOKEN_RE = re.compile(r"<[A-Za-z]+_(-?\d+)>")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_token(token: Any) -> int:
    if isinstance(token, int):
        return token
    text = str(token)
    match = TOKEN_RE.fullmatch(text)
    if match:
        return int(match.group(1))
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"Cannot parse ReSOT SID token: {token!r}") from exc


def read_resot_item2id(item2id_path: Path) -> pd.DataFrame:
    """Read a ReSOT ``item2id`` ASIN-to-internal-id sidecar."""

    rows: list[dict[str, Any]] = []
    with item2id_path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                raise ValueError(f"{item2id_path}:{line_no} expected '<source_item_id>\\t<internal_item_id>'")
            source_item_id, internal_item_id = parts
            rows.append({"source_item_id": source_item_id, "internal_item_id": int(internal_item_id)})

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError(f"{item2id_path} contains no item ids")
    if out["source_item_id"].duplicated().any():
        raise ValueError(f"{item2id_path} contains duplicate source item ids")
    if out["internal_item_id"].duplicated().any():
        raise ValueError(f"{item2id_path} contains duplicate internal item ids")
    return out.sort_values("internal_item_id").reset_index(drop=True)


def _item_id_lookup(item2id_path: Path) -> dict[int, str]:
    frame = read_resot_item2id(item2id_path)
    return {
        int(internal_item_id): str(source_item_id)
        for internal_item_id, source_item_id in zip(frame["internal_item_id"], frame["source_item_id"])
    }


def normalize_resot_index(index_path: Path, item2id_path: Path, method: str, dataset: str) -> pd.DataFrame:
    """Normalize a completed ReSOT ``index_*.json`` file into SIDScope format."""

    mapping = _read_json(index_path)
    if not isinstance(mapping, dict):
        raise ValueError(f"Expected JSON object in {index_path}")
    lookup = _item_id_lookup(item2id_path)

    rows: list[dict[str, Any]] = []
    expected_depth: int | None = None
    for raw_internal_id, raw_codes in sorted(mapping.items(), key=lambda kv: int(kv[0])):
        internal_item_id = int(raw_internal_id)
        if internal_item_id not in lookup:
            raise ValueError(f"Index row {internal_item_id} has no item2id entry")
        if not isinstance(raw_codes, list) or not raw_codes:
            raise ValueError(f"Item {raw_internal_id!r} has invalid SID code list")
        codes = [_parse_token(token) for token in raw_codes]
        if expected_depth is None:
            expected_depth = len(codes)
        elif len(codes) != expected_depth:
            raise ValueError(f"Inconsistent SID depth for item {raw_internal_id!r}")

        row: dict[str, Any] = {
            "item_id": internal_item_id,
            "source_item_id": lookup[internal_item_id],
            "internal_item_id": internal_item_id,
            "method": method,
            "dataset": dataset,
        }
        for level, code in enumerate(codes):
            row[f"sid_level_{level}"] = code
        row["sid"] = "-".join(str(code) for code in codes)
        rows.append(row)

    out = pd.DataFrame(rows)
    if out["item_id"].duplicated().any():
        raise ValueError("Normalized ReSOT index contains duplicate item ids")
    validate_columns("sid_assignments", out.columns)
    return out


def normalize_resot_metadata(item_path: Path, item2id_path: Path, dataset: str) -> pd.DataFrame:
    """Normalize ReSOT item metadata keyed by internal dense item ids."""

    mapping = _read_json(item_path)
    if not isinstance(mapping, dict):
        raise ValueError(f"Expected JSON object in {item_path}")
    lookup = _item_id_lookup(item2id_path)

    rows: list[dict[str, Any]] = []
    for raw_internal_id, value in sorted(mapping.items(), key=lambda kv: int(kv[0])):
        internal_item_id = int(raw_internal_id)
        if internal_item_id not in lookup:
            continue
        if not isinstance(value, dict):
            value = {"raw": value}
        row: dict[str, Any] = {
            "item_id": internal_item_id,
            "source_item_id": lookup[internal_item_id],
            "internal_item_id": internal_item_id,
            "dataset": dataset,
        }
        if "title" in value:
            row["title"] = value["title"]
        if "brand" in value:
            row["brand"] = value["brand"]
        categories = value.get("categories") or value.get("category")
        if categories:
            if isinstance(categories, list):
                row["category"] = " > ".join(str(part) for part in categories)
            else:
                row["category"] = str(categories)
        if "description" in value:
            description = value["description"]
            if isinstance(description, list):
                row["text"] = " ".join(str(part) for part in description)
            else:
                row["text"] = str(description)
        rows.append(row)

    out = pd.DataFrame(rows)
    if "category" not in out.columns:
        out["category"] = "unknown"
    else:
        out["category"] = out["category"].fillna("unknown")
    validate_columns("item_metadata", out.columns)
    return out


def normalize_resot_interactions(
    inter_path: Path,
    item2id_path: Path,
    dataset: str,
    split: str | None = None,
) -> pd.DataFrame:
    """Normalize ReSOT interaction sequences keyed by internal item ids."""

    mapping = _read_json(inter_path)
    if not isinstance(mapping, dict):
        raise ValueError(f"Expected JSON object in {inter_path}")
    lookup = _item_id_lookup(item2id_path)

    rows: list[dict[str, Any]] = []
    for raw_user_id, raw_items in sorted(mapping.items(), key=lambda kv: int(kv[0])):
        if not isinstance(raw_items, list):
            raise ValueError(f"User {raw_user_id!r} has invalid interaction list")
        for position, raw_internal_id in enumerate(raw_items):
            internal_item_id = int(raw_internal_id)
            if internal_item_id not in lookup:
                continue
            row: dict[str, Any] = {
                "user_id": int(raw_user_id),
                "item_id": internal_item_id,
                "source_item_id": lookup[internal_item_id],
                "internal_item_id": internal_item_id,
                "dataset": dataset,
                "position": position,
            }
            if split:
                row["split"] = split
            rows.append(row)

    out = pd.DataFrame(rows)
    validate_columns("interactions", out.columns)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize ReSOT JSON SID artifacts.")
    parser.add_argument("--index-json", type=Path, required=True)
    parser.add_argument("--item2id", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-name", default="unknown")
    parser.add_argument("--method", default="resot_text_index")
    parser.add_argument("--item-json", type=Path, default=None)
    parser.add_argument("--inter-json", type=Path, default=None)
    parser.add_argument("--interaction-split", default=None)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sid_assignments = normalize_resot_index(
        args.index_json,
        item2id_path=args.item2id,
        method=args.method,
        dataset=args.dataset_name,
    )
    sid_assignments.to_parquet(args.output_dir / "sid_assignments.parquet", index=False)

    if args.item_json:
        item_metadata = normalize_resot_metadata(args.item_json, item2id_path=args.item2id, dataset=args.dataset_name)
        item_metadata.to_parquet(args.output_dir / "item_metadata.parquet", index=False)
    if args.inter_json:
        interactions = normalize_resot_interactions(
            args.inter_json,
            item2id_path=args.item2id,
            dataset=args.dataset_name,
            split=args.interaction_split,
        )
        interactions.to_parquet(args.output_dir / "interactions.parquet", index=False)


if __name__ == "__main__":
    main()
