"""Validate Item-Supported Decoding as a decoder overlay.

ISD does not replace the base semantic-ID generator.  It builds a ranked
item shortlist once from target-free history, maps each shortlist item to all
of its SID prefixes, and combines native candidate rank with the best
supporting item rank through reciprocal-rank fusion (RRF).  The same fusion is
applied after generation, but only to items whose complete SID was generated.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


class ISDContractError(ValueError):
    """A typed ISD fixture or decoder-overlay contract failure."""

    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


@dataclass(frozen=True)
class ISDCatalogItem:
    """One source item and its complete model-facing semantic token path."""

    source_item_id: str
    normalized_item_id: str
    model_vocabulary_tokens: tuple[int, ...]


def build_catalog(rows: Sequence[Mapping[str, Any]]) -> list[ISDCatalogItem]:
    """Build a collision-preserving item catalog for the overlay."""

    catalog: list[ISDCatalogItem] = []
    source_seen: set[str] = set()
    normalized_seen: set[str] = set()
    for row in rows:
        source_item_id = str(row["source_item_id"])
        normalized_item_id = str(row["normalized_item_id"])
        tokens = tuple(int(value) for value in row["model_vocabulary_tokens"])
        if source_item_id in source_seen:
            raise ISDContractError(
                "duplicate_source_item", f"duplicate source item {source_item_id!r}"
            )
        if normalized_item_id in normalized_seen:
            raise ISDContractError(
                "duplicate_normalized_item",
                f"duplicate normalized item {normalized_item_id!r}",
            )
        if not tokens:
            raise ISDContractError("empty_semantic_id", "semantic token path is empty")
        catalog.append(ISDCatalogItem(source_item_id, normalized_item_id, tokens))
        source_seen.add(source_item_id)
        normalized_seen.add(normalized_item_id)
    if not catalog:
        raise ISDContractError("empty_catalog", "ISD catalog cannot be empty")
    if len({len(item.model_vocabulary_tokens) for item in catalog}) != 1:
        raise ISDContractError("mixed_sid_depth", "catalog SIDs must have one depth")
    return catalog


def support_maps(
    provider_ranking_item_ids: Sequence[str],
    catalog: Sequence[ISDCatalogItem],
) -> dict[int, dict[tuple[int, ...], int]]:
    """Return the best provider rank supporting each model-token prefix."""

    by_item = {item.normalized_item_id: item for item in catalog}
    depth = len(catalog[0].model_vocabulary_tokens)
    output: dict[int, dict[tuple[int, ...], int]] = {
        position: {} for position in range(1, depth + 1)
    }
    seen: set[str] = set()
    for rank, raw_item_id in enumerate(provider_ranking_item_ids, start=1):
        item_id = str(raw_item_id)
        if item_id in seen:
            raise ISDContractError(
                "duplicate_provider_item", f"duplicate provider item {item_id!r}"
            )
        seen.add(item_id)
        item = by_item.get(item_id)
        if item is None:
            raise ISDContractError(
                "unknown_provider_item", f"provider item {item_id!r} is not in catalog"
            )
        for position in range(1, depth + 1):
            prefix = item.model_vocabulary_tokens[:position]
            output[position].setdefault(prefix, rank)
    return output


def reciprocal_rank_fusion(
    native_rank: int,
    support_rank: int | None,
    *,
    rrf_constant: int = 60,
) -> float:
    """Compute the equal-weight RRF score used by the audited ISD route."""

    if native_rank <= 0 or (support_rank is not None and support_rank <= 0):
        raise ISDContractError("invalid_rank", "RRF ranks must be positive")
    if rrf_constant < 0:
        raise ISDContractError(
            "invalid_rrf_constant", "RRF constant cannot be negative"
        )
    score = 1.0 / (rrf_constant + native_rank)
    if support_rank is not None:
        score += 1.0 / (rrf_constant + support_rank)
    return score


def _dense_native_rank(scores: Sequence[float], value: float) -> int:
    return sum(score > value for score in scores) + 1


def _resolve_tokens(
    tokens: tuple[int, ...], catalog: Sequence[ISDCatalogItem]
) -> dict[str, Any]:
    matches = sorted(
        (item for item in catalog if item.model_vocabulary_tokens == tokens),
        key=lambda item: item.normalized_item_id,
    )
    return {
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


def run_deterministic_overlay_fixture(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Replay a bounded base-beam trace with ISD prefix and item reranking."""

    config = manifest["configuration"]
    sid_depth = int(config["sid_depth"])
    beam_width = int(config["beam_width"])
    shortlist_size = int(config["provider_shortlist_size"])
    rrf_constant = int(config["rrf_constant"])
    if sid_depth <= 0 or beam_width <= 0 or shortlist_size <= 0:
        raise ISDContractError(
            "invalid_overlay_configuration",
            "SID depth, beam width, and shortlist size must be positive",
        )
    catalog = build_catalog(manifest["catalog"])
    if {len(item.model_vocabulary_tokens) for item in catalog} != {sid_depth}:
        raise ISDContractError(
            "catalog_depth_mismatch", "catalog SID depth differs from configuration"
        )
    provider_ranking = [str(value) for value in manifest["provider_ranking_item_ids"]]
    if len(provider_ranking) != shortlist_size:
        raise ISDContractError(
            "shortlist_size_mismatch", "provider shortlist length differs from config"
        )
    supports = support_maps(provider_ranking, catalog)

    active: dict[str, tuple[int, ...]] = {"root": ()}
    exported_steps: list[dict[str, Any]] = []
    steps = manifest["base_decoder_steps"]
    if len(steps) != sid_depth:
        raise ISDContractError(
            "wrong_decode_step_count",
            f"expected {sid_depth} base decode steps, observed {len(steps)}",
        )
    for expected_depth, step in enumerate(steps, start=1):
        if int(step["prefix_depth"]) != expected_depth:
            raise ISDContractError(
                "noncontiguous_prefix_depth", "prefix depths must be contiguous"
            )
        raw_candidates = step["base_candidates"]
        if not raw_candidates:
            raise ISDContractError("empty_candidate_pool", "base candidate pool is empty")
        ids = [str(row["candidate_id"]) for row in raw_candidates]
        if len(ids) != len(set(ids)):
            raise ISDContractError(
                "duplicate_candidate_id", "candidate IDs must be unique per step"
            )
        scores = [float(row["native_cumulative_score"]) for row in raw_candidates]
        if any(not math.isfinite(value) for value in scores):
            raise ISDContractError("nonfinite_score", "native scores must be finite")
        ranked: list[dict[str, Any]] = []
        for row, native_score in zip(raw_candidates, scores):
            candidate_id = str(row["candidate_id"])
            parent_candidate_id = str(row["parent_candidate_id"])
            if parent_candidate_id not in active:
                raise ISDContractError(
                    "unknown_parent_candidate",
                    f"unknown surviving parent {parent_candidate_id!r}",
                )
            prefix = tuple(int(value) for value in row["prefix_tokens"])
            if len(prefix) != expected_depth or prefix[:-1] != active[parent_candidate_id]:
                raise ISDContractError(
                    "prefix_parent_mismatch",
                    f"candidate {candidate_id!r} does not extend its surviving parent",
                )
            native_rank = _dense_native_rank(scores, native_score)
            support_rank = supports[expected_depth].get(prefix)
            fusion_score = reciprocal_rank_fusion(
                native_rank, support_rank, rrf_constant=rrf_constant
            )
            ranked.append(
                {
                    "candidate_id": candidate_id,
                    "parent_candidate_id": parent_candidate_id,
                    "prefix_tokens": list(prefix),
                    "native_cumulative_score": native_score,
                    "native_rank": native_rank,
                    "best_supporting_item_rank": support_rank,
                    "support_status": "supported" if support_rank is not None else "unsupported",
                    "rrf_score": fusion_score,
                }
            )
        ranked.sort(
            key=lambda row: (
                -float(row["rrf_score"]),
                int(row["native_rank"]),
                row["best_supporting_item_rank"]
                if row["best_supporting_item_rank"] is not None
                else 10**9,
                row["prefix_tokens"],
                row["candidate_id"],
            )
        )
        survivors = ranked[:beam_width]
        survivor_ids = [str(row["candidate_id"]) for row in survivors]
        if survivor_ids != [str(value) for value in step["expected_survivor_ids"]]:
            raise ISDContractError(
                "survival_mismatch",
                f"step {expected_depth} expected survivors do not match RRF ordering",
            )
        survivor_set = set(survivor_ids)
        for overlay_rank, row in enumerate(ranked, start=1):
            row["overlay_rank"] = overlay_rank
            row["survived"] = row["candidate_id"] in survivor_set
            row["failure_label"] = None if row["survived"] else "pruned_by_overlay"
        active = {
            str(row["candidate_id"]): tuple(int(value) for value in row["prefix_tokens"])
            for row in survivors
        }
        exported_steps.append(
            {
                "prefix_depth": expected_depth,
                "base_candidates": ranked,
                "survivor_ids": survivor_ids,
            }
        )

    generated_candidates: list[dict[str, Any]] = []
    for base_rank, row in enumerate(exported_steps[-1]["base_candidates"], start=1):
        if not row["survived"]:
            continue
        tokens = tuple(int(value) for value in row["prefix_tokens"])
        generated_candidates.append(
            {
                "candidate_id": row["candidate_id"],
                "model_vocabulary_tokens": list(tokens),
                "base_sid_rank": base_rank,
                "native_cumulative_score": row["native_cumulative_score"],
                **_resolve_tokens(tokens, catalog),
            }
        )

    provider_rank = {item_id: rank for rank, item_id in enumerate(provider_ranking, 1)}
    ranked_items: list[dict[str, Any]] = []
    for candidate in generated_candidates:
        for normalized_item_id, source_item_id in zip(
            candidate["resolved_item_ids"], candidate["resolved_source_item_ids"]
        ):
            item_support_rank = provider_rank.get(normalized_item_id)
            ranked_items.append(
                {
                    "normalized_item_id": normalized_item_id,
                    "source_item_id": source_item_id,
                    "candidate_id": candidate["candidate_id"],
                    "model_vocabulary_tokens": candidate["model_vocabulary_tokens"],
                    "base_sid_rank": candidate["base_sid_rank"],
                    "provider_item_rank": item_support_rank,
                    "final_rrf_score": reciprocal_rank_fusion(
                        int(candidate["base_sid_rank"]),
                        item_support_rank,
                        rrf_constant=rrf_constant,
                    ),
                    "resolution_status": candidate["resolution_status"],
                }
            )
    ranked_items.sort(
        key=lambda row: (
            -float(row["final_rrf_score"]),
            int(row["base_sid_rank"]),
            row["provider_item_rank"] if row["provider_item_rank"] is not None else 10**9,
            row["normalized_item_id"],
        )
    )
    for rank, row in enumerate(ranked_items, start=1):
        row["final_rank"] = rank

    generated_item_ids = {row["normalized_item_id"] for row in ranked_items}
    declared_final = [str(value) for value in manifest["declared_final_item_ids"]]
    if set(declared_final) != generated_item_ids or len(declared_final) != len(
        generated_item_ids
    ):
        inserted = sorted(set(declared_final).difference(generated_item_ids))
        if inserted:
            raise ISDContractError(
                "provider_only_item_insertion",
                f"final rerank includes items without generated SIDs: {inserted}",
            )
        raise ISDContractError(
            "generated_item_omission", "final rerank omits one or more generated items"
        )

    collision_count = sum(
        1
        for tokens in {item.model_vocabulary_tokens for item in catalog}
        if sum(item.model_vocabulary_tokens == tokens for item in catalog) > 1
    )
    return {
        "schema": "sidscope.isd_decoder_overlay_trace.v1",
        "route_id": str(manifest["route_id"]),
        "trace_id": str(manifest["trace_id"]),
        "decode_state_kind": "autoregressive_base_beam_with_item_support_overlay",
        "overlay_scope": "candidate_survival_and_generated_item_reranking_only",
        "source": dict(manifest["source"]),
        "configuration": dict(config),
        "split_identity": dict(manifest["split_identity"]),
        "provider_context": dict(manifest["provider_context"]),
        "provider_ranking_item_ids": provider_ranking,
        "support_maps": {
            str(depth): [
                {"prefix_tokens": list(prefix), "best_supporting_item_rank": rank}
                for prefix, rank in sorted(values.items())
            ]
            for depth, values in supports.items()
        },
        "base_decoder_steps": exported_steps,
        "generated_candidates": generated_candidates,
        "ranked_items": ranked_items,
        "validity_policy": {
            "valid": "complete generated SID resolves to at least one catalog item",
            "unresolved_failure_label": "unresolved_semantic_id",
            "ambiguity_label": "ambiguous_semantic_id",
            "provider_only_item_failure_label": "provider_only_item_insertion",
        },
        "ambiguity": {
            "catalog_collision_count": collision_count,
            "ambiguous_generated_candidate_count": sum(
                row["resolution_status"] == "ambiguous_semantic_id"
                for row in generated_candidates
            ),
            "unresolved_generated_candidate_count": sum(
                row["resolution_status"] == "unresolved_semantic_id"
                for row in generated_candidates
            ),
        },
        "invariants": {
            "provider_scores_catalog_once_before_generation": True,
            "support_uses_best_shortlist_item_rank": True,
            "base_decoder_scores_preserved": True,
            "provider_only_items_inserted": False,
            "semantic_ids_modified": False,
        },
    }


__all__ = [
    "ISDCatalogItem",
    "ISDContractError",
    "build_catalog",
    "reciprocal_rank_fusion",
    "run_deterministic_overlay_fixture",
    "support_maps",
]
