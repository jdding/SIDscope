"""Normalize DACT artifacts and validate its autoregressive trace contract.

The DACT release uses a TIGER/T5-style autoregressive generator. SIDScope
keeps this ordered-prefix contract separate from parallel and diffusion
adapters: every transition names its parent beam, appends exactly one
position-valid vocabulary token, and retains the resulting prefix.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from sidinspector.interface import validate_columns


class DACTContractError(ValueError):
    """A typed DACT fixture or trace-contract failure."""

    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


@dataclass(frozen=True)
class DACTCatalogItem:
    """One source item and its model-facing DACT semantic identifier."""

    source_item_id: str
    normalized_item_id: str
    semantic_codes: tuple[int, ...]
    model_vocabulary_tokens: tuple[int, ...]


def model_vocabulary_tokens(
    semantic_codes: Sequence[int], *, codebook_size: int = 256
) -> tuple[int, ...]:
    """Apply the released TIGER position-disjoint vocabulary offsets."""

    codes = tuple(int(value) for value in semantic_codes)
    if not codes:
        raise DACTContractError("empty_semantic_id", "semantic_codes cannot be empty")
    if codebook_size <= 0:
        raise DACTContractError("invalid_codebook_size", "codebook_size must be positive")
    tokens: list[int] = []
    for position, code in enumerate(codes):
        if code < 0 or code >= codebook_size:
            raise DACTContractError(
                "code_out_of_range",
                f"semantic code {code} is outside [0, {codebook_size}) at position {position}",
            )
        tokens.append(code + position * codebook_size + 1)
    return tuple(tokens)


def build_catalog(
    rows: Sequence[Mapping[str, Any]], *, codebook_size: int = 256
) -> list[DACTCatalogItem]:
    """Build a source-to-model catalog while retaining full-SID collisions."""

    catalog: list[DACTCatalogItem] = []
    source_seen: set[str] = set()
    normalized_seen: set[str] = set()
    for row in rows:
        source_item_id = str(row["source_item_id"])
        normalized_item_id = str(row["normalized_item_id"])
        if source_item_id in source_seen:
            raise DACTContractError(
                "duplicate_source_item", f"duplicate source item {source_item_id!r}"
            )
        if normalized_item_id in normalized_seen:
            raise DACTContractError(
                "duplicate_normalized_item",
                f"duplicate normalized item {normalized_item_id!r}",
            )
        codes = tuple(int(value) for value in row["semantic_codes"])
        catalog.append(
            DACTCatalogItem(
                source_item_id=source_item_id,
                normalized_item_id=normalized_item_id,
                semantic_codes=codes,
                model_vocabulary_tokens=model_vocabulary_tokens(
                    codes, codebook_size=codebook_size
                ),
            )
        )
        source_seen.add(source_item_id)
        normalized_seen.add(normalized_item_id)
    if not catalog:
        raise DACTContractError("empty_catalog", "DACT catalog cannot be empty")
    depths = {len(item.semantic_codes) for item in catalog}
    if len(depths) != 1:
        raise DACTContractError("mixed_sid_depth", "all catalog SIDs must have one depth")
    return catalog


def resolve_model_tokens(
    tokens: Sequence[int], catalog: Sequence[DACTCatalogItem]
) -> dict[str, Any]:
    """Resolve a complete generated path without discarding ambiguity."""

    values = tuple(int(value) for value in tokens)
    matches = sorted(
        (item for item in catalog if item.model_vocabulary_tokens == values),
        key=lambda item: item.normalized_item_id,
    )
    return {
        "model_vocabulary_tokens": list(values),
        "resolved_item_ids": [item.normalized_item_id for item in matches],
        "resolved_source_item_ids": [item.source_item_id for item in matches],
        "resolution_status": (
            "unresolved_semantic_id"
            if not matches
            else "unique_item"
            if len(matches) == 1
            else "ambiguous_semantic_id"
        ),
        "ambiguity_count": max(len(matches) - 1, 0),
    }


def _validate_position_token(token: int, position: int, codebook_size: int) -> None:
    lower = position * codebook_size + 1
    upper = (position + 1) * codebook_size
    if token < lower or token > upper:
        raise DACTContractError(
            "token_outside_position_vocabulary",
            f"token {token} is outside [{lower}, {upper}] for position {position}",
        )


def run_deterministic_autoregressive_fixture(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and export a deterministic ordered-prefix beam trace."""

    config = manifest["configuration"]
    codebook_size = int(config["codebook_size"])
    sid_depth = int(config["sid_depth"])
    beam_width = int(config["beam_width"])
    if sid_depth <= 0 or beam_width <= 0:
        raise DACTContractError(
            "invalid_decoding_configuration", "sid_depth and beam_width must be positive"
        )
    catalog = build_catalog(manifest["catalog"], codebook_size=codebook_size)
    if {len(item.semantic_codes) for item in catalog} != {sid_depth}:
        raise DACTContractError(
            "catalog_depth_mismatch", "catalog SID depth differs from configuration"
        )

    target_item_id = str(manifest["target_normalized_item_id"])
    by_normalized = {item.normalized_item_id: item for item in catalog}
    if target_item_id not in by_normalized:
        raise DACTContractError("unknown_target_item", f"unknown target {target_item_id!r}")

    active: dict[str, tuple[int, ...]] = {"root": ()}
    active_scores: dict[str, float] = {"root": 0.0}
    exported_steps: list[dict[str, Any]] = []
    steps = manifest["steps"]
    if len(steps) != sid_depth:
        raise DACTContractError(
            "wrong_decode_step_count",
            f"expected {sid_depth} decode steps, observed {len(steps)}",
        )
    for expected_depth, step in enumerate(steps, start=1):
        if int(step["prefix_depth"]) != expected_depth:
            raise DACTContractError(
                "noncontiguous_prefix_depth", "prefix depths must be contiguous from one"
            )
        transitions = step["transitions"]
        if not transitions or len(transitions) > beam_width:
            raise DACTContractError(
                "invalid_active_beam_count",
                f"depth {expected_depth} has {len(transitions)} active beams for width {beam_width}",
            )
        next_active: dict[str, tuple[int, ...]] = {}
        next_scores: dict[str, float] = {}
        exported_transitions: list[dict[str, Any]] = []
        for transition in transitions:
            beam_id = str(transition["beam_id"])
            parent_beam_id = str(transition["parent_beam_id"])
            if beam_id in next_active:
                raise DACTContractError("duplicate_beam_id", f"duplicate beam {beam_id!r}")
            if parent_beam_id not in active:
                raise DACTContractError(
                    "unknown_parent_beam", f"unknown parent beam {parent_beam_id!r}"
                )
            token = int(transition["appended_token"])
            _validate_position_token(token, expected_depth - 1, codebook_size)
            prefix = tuple(int(value) for value in transition["prefix_tokens"])
            expected_prefix = active[parent_beam_id] + (token,)
            if prefix != expected_prefix:
                raise DACTContractError(
                    "prefix_parent_mismatch",
                    f"beam {beam_id!r} prefix is not its parent prefix plus the declared token",
                )
            token_log_probability = float(transition["token_log_probability"])
            cumulative_score = float(transition["cumulative_score"])
            if not math.isfinite(token_log_probability) or not math.isfinite(cumulative_score):
                raise DACTContractError("nonfinite_score", "beam scores must be finite")
            expected_score = active_scores[parent_beam_id] + token_log_probability
            if not math.isclose(cumulative_score, expected_score, abs_tol=1e-9):
                raise DACTContractError(
                    "cumulative_score_mismatch",
                    f"beam {beam_id!r} cumulative score does not equal its transition sum",
                )
            next_active[beam_id] = prefix
            next_scores[beam_id] = cumulative_score
            exported_transitions.append(
                {
                    "beam_id": beam_id,
                    "parent_beam_id": parent_beam_id,
                    "prefix_tokens": list(prefix),
                    "appended_token": token,
                    "token_log_probability": token_log_probability,
                    "cumulative_score": cumulative_score,
                }
            )
        active = next_active
        active_scores = next_scores
        exported_steps.append(
            {"prefix_depth": expected_depth, "transitions": exported_transitions}
        )

    candidates = []
    for beam_id, tokens in active.items():
        resolution = resolve_model_tokens(tokens, catalog)
        candidates.append(
            {
                "beam_id": beam_id,
                "model_vocabulary_tokens": list(tokens),
                "sequence_score_log_probability": active_scores[beam_id],
                **{key: value for key, value in resolution.items() if key != "model_vocabulary_tokens"},
            }
        )
    candidates.sort(
        key=lambda row: (
            -float(row["sequence_score_log_probability"]),
            row["model_vocabulary_tokens"],
            row["beam_id"],
        )
    )
    ranked_items: list[dict[str, Any]] = []
    for candidate_rank, candidate in enumerate(candidates, start=1):
        for normalized_item_id, source_item_id in zip(
            candidate["resolved_item_ids"], candidate["resolved_source_item_ids"]
        ):
            ranked_items.append(
                {
                    "ranked_item_row": len(ranked_items) + 1,
                    "candidate_rank": candidate_rank,
                    "normalized_item_id": normalized_item_id,
                    "source_item_id": source_item_id,
                    "beam_id": candidate["beam_id"],
                    "score_log_probability": candidate["sequence_score_log_probability"],
                    "resolution_status": candidate["resolution_status"],
                }
            )
    target_candidate_rank = next(
        (
            rank
            for rank, candidate in enumerate(candidates, start=1)
            if target_item_id in candidate["resolved_item_ids"]
        ),
        None,
    )
    collision_count = sum(
        1
        for tokens in {item.model_vocabulary_tokens for item in catalog}
        if sum(item.model_vocabulary_tokens == tokens for item in catalog) > 1
    )
    return {
        "schema": "sidscope.dact_tiger_autoregressive_trace.v1",
        "route_id": str(manifest["route_id"]),
        "trace_id": str(manifest["trace_id"]),
        "decode_state_kind": "ordered_autoregressive_prefix_beam",
        "source": dict(manifest["source"]),
        "configuration": dict(config),
        "split_identity": dict(manifest["split_identity"]),
        "target_normalized_item_id": target_item_id,
        "steps": exported_steps,
        "candidates": candidates,
        "ranked_items": ranked_items,
        "validity_policy": {
            "valid": "full generated token path resolves to one or more catalog items",
            "unresolved_failure_label": "invalid_path",
            "ambiguous_failure_label": "ambiguous_path",
        },
        "ambiguity": {
            "catalog_collision_count": collision_count,
            "ambiguous_candidate_count": sum(
                candidate["resolution_status"] == "ambiguous_semantic_id"
                for candidate in candidates
            ),
        },
        "target_outcome": {
            "target_candidate_rank": target_candidate_rank,
            "target_path_survived": target_candidate_rank is not None,
            "target_item_uniquely_hit": bool(
                target_candidate_rank is not None
                and candidates[target_candidate_rank - 1]["resolution_status"] == "unique_item"
            ),
        },
    }


def normalize_dact_codes(
    codes_path: Path,
    method: str,
    dataset: str,
    item_ids: np.ndarray | None = None,
    item_id_offset: int = 1,
) -> pd.DataFrame:
    codes = np.load(codes_path, allow_pickle=False)
    if codes.ndim != 2:
        raise ValueError(f"Expected DACT codes to be 2D, got shape {codes.shape}")
    codes = codes.astype(np.int64)
    if item_ids is None:
        item_ids = np.arange(codes.shape[0], dtype=np.int64) + item_id_offset
    if len(item_ids) != codes.shape[0]:
        raise ValueError(f"item_ids length {len(item_ids)} does not match code rows {codes.shape[0]}")

    out = pd.DataFrame({"item_id": item_ids.astype(int), "method": method, "dataset": dataset})
    for level in range(codes.shape[1]):
        out[f"sid_level_{level}"] = codes[:, level].astype(int)
    level_cols = [f"sid_level_{level}" for level in range(codes.shape[1])]
    out["sid"] = out[level_cols].astype(str).agg("-".join, axis=1)
    validate_columns("sid_assignments", out.columns)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize public DACT SID code arrays.")
    parser.add_argument("--codes-path", type=Path, required=True)
    parser.add_argument("--item-ids", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-name", default="Tools")
    parser.add_argument("--method", default="dact")
    parser.add_argument("--item-id-offset", type=int, default=1)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    item_ids = np.load(args.item_ids, allow_pickle=False) if args.item_ids else None
    sid = normalize_dact_codes(
        codes_path=args.codes_path,
        method=args.method,
        dataset=args.dataset_name,
        item_ids=item_ids,
        item_id_offset=args.item_id_offset,
    )
    sid.to_parquet(args.output_dir / "sid_assignments.parquet", index=False)


if __name__ == "__main__":
    main()
