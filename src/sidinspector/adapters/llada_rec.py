"""LLaDA-Rec adaptive-unmasking trace contract.

This is an independent SIDScope interoperability layer. It does not vendor the
unlicensed upstream implementation, model weights, or tokenizer assets. The
pinned official inference route starts with an all-mask target and fills
still-masked positions in confidence-selected order. It does not remask an
already generated position, so this contract records remasking explicitly and
rejects it for that source revision.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


class LLaDARecContractError(ValueError):
    """A typed LLaDA-Rec fixture or trace-contract failure."""

    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


@dataclass(frozen=True)
class LLaDARecCatalogItem:
    """One source item and its position-specific parallel semantic ID."""

    source_item_id: str
    normalized_item_id: str
    semantic_codes: tuple[int, ...]
    model_vocabulary_tokens: tuple[int, ...]


def _codebook_offsets(codebook_sizes: Sequence[int]) -> tuple[int, ...]:
    sizes = tuple(int(value) for value in codebook_sizes)
    if not sizes or any(value <= 0 for value in sizes):
        raise LLaDARecContractError(
            "invalid_codebook_sizes", "codebook_sizes must contain positive integers"
        )
    offsets = [0]
    for size in sizes[:-1]:
        offsets.append(offsets[-1] + size)
    return tuple(offsets)


def model_vocabulary_tokens(
    semantic_codes: Sequence[int], codebook_sizes: Sequence[int]
) -> tuple[int, ...]:
    """Map parallel codes into the official position-disjoint vocabulary."""

    codes = tuple(int(value) for value in semantic_codes)
    sizes = tuple(int(value) for value in codebook_sizes)
    offsets = _codebook_offsets(sizes)
    if len(codes) != len(sizes):
        raise LLaDARecContractError(
            "wrong_semantic_code_count",
            f"expected {len(sizes)} semantic codes, observed {len(codes)}",
        )
    tokens: list[int] = []
    for position, (code, size, offset) in enumerate(zip(codes, sizes, offsets)):
        if code < 0 or code >= size:
            raise LLaDARecContractError(
                "code_out_of_range",
                f"semantic code {code} is outside [0, {size}) at position {position}",
            )
        tokens.append(offset + code + 1)
    return tuple(tokens)


def mask_token_id(codebook_sizes: Sequence[int]) -> int:
    """Return the pinned tokenizer's mask token (EOS is one token earlier)."""

    _codebook_offsets(codebook_sizes)
    return sum(int(value) for value in codebook_sizes) + 2


def build_catalog(
    rows: Sequence[Mapping[str, Any]], *, codebook_sizes: Sequence[int]
) -> list[LLaDARecCatalogItem]:
    """Build a validated catalog while retaining semantic-ID collisions."""

    items: list[LLaDARecCatalogItem] = []
    source_seen: set[str] = set()
    normalized_seen: set[str] = set()
    for row in rows:
        source_item_id = str(row["source_item_id"])
        normalized_item_id = str(row["normalized_item_id"])
        if source_item_id in source_seen:
            raise LLaDARecContractError(
                "duplicate_source_item", f"duplicate source item {source_item_id!r}"
            )
        if normalized_item_id in normalized_seen:
            raise LLaDARecContractError(
                "duplicate_normalized_item",
                f"duplicate normalized item {normalized_item_id!r}",
            )
        codes = tuple(int(value) for value in row["semantic_codes"])
        tokens = model_vocabulary_tokens(codes, codebook_sizes)
        items.append(
            LLaDARecCatalogItem(
                source_item_id=source_item_id,
                normalized_item_id=normalized_item_id,
                semantic_codes=codes,
                model_vocabulary_tokens=tokens,
            )
        )
        source_seen.add(source_item_id)
        normalized_seen.add(normalized_item_id)
    if not items:
        raise LLaDARecContractError("empty_catalog", "LLaDA-Rec catalog cannot be empty")
    return items


def resolve_model_tokens(
    tokens: Sequence[int], catalog: Sequence[LLaDARecCatalogItem]
) -> dict[str, Any]:
    """Resolve a full positional token tuple without hiding ambiguity."""

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


def _validate_position_token(token: int, position: int, codebook_sizes: Sequence[int]) -> None:
    offsets = _codebook_offsets(codebook_sizes)
    lower = offsets[position] + 1
    upper = lower + int(codebook_sizes[position]) - 1
    if token < lower or token > upper:
        raise LLaDARecContractError(
            "token_outside_position_vocabulary",
            f"token {token} is outside [{lower}, {upper}] for position {position}",
        )


def run_deterministic_diffusion_fixture(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and export a deterministic adaptive-unmasking beam trace."""

    config = manifest["configuration"]
    codebook_sizes = tuple(int(value) for value in config["codebook_sizes"])
    n_digit = len(codebook_sizes)
    gen_steps = int(config["gen_steps"])
    beam_size = int(config["beam_size"])
    top_k = int(config["top_k"])
    if gen_steps <= 0 or beam_size <= 0 or top_k <= 0:
        raise LLaDARecContractError(
            "invalid_decoding_configuration", "gen_steps, beam_size, and top_k must be positive"
        )
    if gen_steps != n_digit:
        raise LLaDARecContractError(
            "unsupported_transfer_schedule",
            "the bounded fixture requires the pinned default one-position-per-step schedule",
        )
    if top_k > beam_size:
        raise LLaDARecContractError(
            "invalid_decoding_configuration", "top_k cannot exceed beam_size"
        )

    catalog = build_catalog(manifest["catalog"], codebook_sizes=codebook_sizes)
    by_normalized = {item.normalized_item_id: item for item in catalog}
    target_item_id = str(manifest["target_normalized_item_id"])
    if target_item_id not in by_normalized:
        raise LLaDARecContractError(
            "unknown_target_item", f"unknown target item {target_item_id!r}"
        )

    mask = mask_token_id(codebook_sizes)
    initial_tokens = tuple([mask] * n_digit)
    active: dict[str, tuple[int, ...]] = {"root": initial_tokens}
    generation_orders: dict[str, list[int]] = {"root": []}
    exported_steps: list[dict[str, Any]] = []
    observed_remasks = 0

    raw_steps = manifest["steps"]
    if len(raw_steps) != gen_steps:
        raise LLaDARecContractError(
            "wrong_refinement_step_count",
            f"expected {gen_steps} refinement steps, observed {len(raw_steps)}",
        )

    for expected_step, raw_step in enumerate(raw_steps, start=1):
        if int(raw_step["refinement_step"]) != expected_step:
            raise LLaDARecContractError(
                "noncontiguous_refinement_step", "refinement steps must be contiguous from one"
            )
        transitions = raw_step["transitions"]
        if len(transitions) != beam_size:
            raise LLaDARecContractError(
                "wrong_beam_count",
                f"step {expected_step} expected {beam_size} beams, observed {len(transitions)}",
            )
        next_active: dict[str, tuple[int, ...]] = {}
        next_orders: dict[str, list[int]] = {}
        exported_transitions: list[dict[str, Any]] = []
        for transition in transitions:
            beam_id = str(transition["beam_id"])
            parent_beam_id = str(transition["parent_beam_id"])
            if beam_id in next_active:
                raise LLaDARecContractError("duplicate_beam_id", f"duplicate beam {beam_id!r}")
            if parent_beam_id not in active:
                raise LLaDARecContractError(
                    "unknown_parent_beam", f"unknown parent beam {parent_beam_id!r}"
                )
            parent_tokens = active[parent_beam_id]
            pre_tokens = tuple(int(value) for value in transition["pre_tokens"])
            post_tokens = tuple(int(value) for value in transition["post_tokens"])
            if len(pre_tokens) != n_digit or len(post_tokens) != n_digit:
                raise LLaDARecContractError(
                    "wrong_state_width", f"beam {beam_id!r} state width must be {n_digit}"
                )
            if pre_tokens != parent_tokens:
                raise LLaDARecContractError(
                    "parent_state_mismatch", f"beam {beam_id!r} does not start from its parent state"
                )

            remasked_positions = [int(value) for value in transition.get("remasked_positions", [])]
            if remasked_positions:
                raise LLaDARecContractError(
                    "unsupported_remasking_transition",
                    "the pinned official inference route never remasks a filled position",
                )
            observed_remasks += len(remasked_positions)

            positions = [int(value) for value in transition["selected_positions"]]
            predicted = [int(value) for value in transition["predicted_tokens"]]
            confidences = [float(value) for value in transition["confidences"]]
            if not positions or len(set(positions)) != len(positions):
                raise LLaDARecContractError(
                    "invalid_selected_positions", "selected positions must be non-empty and unique"
                )
            if len(positions) != len(predicted) or len(positions) != len(confidences):
                raise LLaDARecContractError(
                    "transition_field_length_mismatch",
                    "selected positions, predictions, and confidences must have equal length",
                )
            expected_post = list(pre_tokens)
            for position, token, confidence in zip(positions, predicted, confidences):
                if position < 0 or position >= n_digit:
                    raise LLaDARecContractError(
                        "position_out_of_range", f"position {position} is outside [0, {n_digit})"
                    )
                if pre_tokens[position] != mask:
                    raise LLaDARecContractError(
                        "selected_position_not_masked",
                        f"position {position} was already filled before step {expected_step}",
                    )
                _validate_position_token(token, position, codebook_sizes)
                if not math.isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
                    raise LLaDARecContractError(
                        "invalid_confidence", f"confidence {confidence} is outside [0, 1]"
                    )
                expected_post[position] = token
            if tuple(expected_post) != post_tokens:
                raise LLaDARecContractError(
                    "state_transition_mismatch",
                    f"beam {beam_id!r} post-state differs from its declared unmask action",
                )
            score = float(transition["beam_score_log_probability"])
            if not math.isfinite(score):
                raise LLaDARecContractError("invalid_beam_score", "beam score must be finite")

            pre_masked = [index for index, token in enumerate(pre_tokens) if token == mask]
            post_masked = [index for index, token in enumerate(post_tokens) if token == mask]
            next_active[beam_id] = post_tokens
            next_orders[beam_id] = generation_orders[parent_beam_id] + positions
            exported_transitions.append(
                {
                    "beam_id": beam_id,
                    "parent_beam_id": parent_beam_id,
                    "pre_tokens": list(pre_tokens),
                    "pre_masked_positions": pre_masked,
                    "selected_positions": positions,
                    "predicted_tokens": predicted,
                    "confidences": confidences,
                    "remasked_positions": [],
                    "post_tokens": list(post_tokens),
                    "post_masked_positions": post_masked,
                    "beam_score_log_probability": score,
                    "position_action": "adaptive_unmask",
                }
            )
        active = next_active
        generation_orders = next_orders
        exported_steps.append(
            {"refinement_step": expected_step, "transitions": exported_transitions}
        )

    final_scores = {
        str(transition["beam_id"]): float(transition["beam_score_log_probability"])
        for transition in raw_steps[-1]["transitions"]
    }
    if any(mask in tokens for tokens in active.values()):
        raise LLaDARecContractError(
            "incomplete_final_state", "all target positions must be unmasked after the final step"
        )

    candidates: dict[tuple[int, ...], dict[str, Any]] = {}
    for beam_id, tokens in active.items():
        score = final_scores[beam_id]
        current = candidates.get(tokens)
        if current is None:
            candidates[tokens] = {
                "score_log_probability": score,
                "representative_beam_id": beam_id,
                "supporting_beam_ids": [beam_id],
            }
        else:
            current["supporting_beam_ids"].append(beam_id)
            if score > current["score_log_probability"]:
                current["score_log_probability"] = score
                current["representative_beam_id"] = beam_id

    ranked_groups: list[dict[str, Any]] = []
    for tokens, candidate in candidates.items():
        resolution = resolve_model_tokens(tokens, catalog)
        ranked_groups.append(
            {
                **candidate,
                **resolution,
                "generation_order": generation_orders[candidate["representative_beam_id"]],
            }
        )
    ranked_groups.sort(
        key=lambda row: (-float(row["score_log_probability"]), row["model_vocabulary_tokens"])
    )
    ranked_groups = ranked_groups[:top_k]
    ranked_items: list[dict[str, Any]] = []
    for group_rank, group in enumerate(ranked_groups, start=1):
        group["candidate_group_rank"] = group_rank
        if group["resolution_status"] != "unique_item":
            continue
        ranked_items.append(
            {
                "rank": len(ranked_items) + 1,
                "source_item_id": group["resolved_source_item_ids"][0],
                "normalized_item_id": group["resolved_item_ids"][0],
                "model_vocabulary_tokens": group["model_vocabulary_tokens"],
                "score_log_probability": group["score_log_probability"],
                "generation_order": group["generation_order"],
                "supporting_beam_ids": group["supporting_beam_ids"],
            }
        )

    collisions: list[dict[str, Any]] = []
    catalog_tokens = sorted({item.model_vocabulary_tokens for item in catalog})
    for tokens in catalog_tokens:
        resolution = resolve_model_tokens(tokens, catalog)
        if resolution["resolution_status"] == "ambiguous_semantic_id":
            collisions.append(resolution)

    target = by_normalized[target_item_id]
    return {
        "schema": "sidscope.llada_rec_diffusion_trace.v1",
        "route_id": str(manifest["route_id"]),
        "trace_id": str(manifest["trace_id"]),
        "adapter_kind": "diffusion_generator",
        "decode_state_kind": "masked_parallel_adaptive_unmasking",
        "split_id": str(config["split_id"]),
        "target_universe": str(config["target_universe"]),
        "target_source_item_id": target.source_item_id,
        "target_normalized_item_id": target.normalized_item_id,
        "mask_token_id": mask,
        "initial_mask_state": list(initial_tokens),
        "generation_policy": {
            "position_selection": "highest_argmax_softmax_confidence_among_masked_positions",
            "beam_expansion": "position_valid_vocabulary",
            "filled_position_policy": "monotone_keep",
            "remasking_supported_by_pinned_source": False,
        },
        "steps": exported_steps,
        "final_candidate_groups": ranked_groups,
        "ranked_items": ranked_items,
        "validity": {
            "complete_final_beams": len(active),
            "unresolved_final_candidate_groups": sum(
                group["resolution_status"] == "unresolved_semantic_id" for group in ranked_groups
            ),
            "ambiguous_final_candidate_groups": sum(
                group["resolution_status"] == "ambiguous_semantic_id" for group in ranked_groups
            ),
        },
        "ambiguity": {
            "catalog_collision_count": len(collisions),
            "collisions": collisions,
            "policy": "retain all item identities; ambiguous semantic IDs are not silently ranked as one item",
        },
        "remasking": {
            "observed_transition_count": observed_remasks,
            "policy": "explicitly recorded but forbidden by the pinned monotone inference implementation",
        },
        "failure_labels": [],
        "fixture_boundary": "deidentified deterministic CPU trace contract; no checkpoint, training, or recommendation claim",
    }


__all__ = [
    "LLaDARecCatalogItem",
    "LLaDARecContractError",
    "build_catalog",
    "mask_token_id",
    "model_vocabulary_tokens",
    "resolve_model_tokens",
    "run_deterministic_diffusion_fixture",
]
