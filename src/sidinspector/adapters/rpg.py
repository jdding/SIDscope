"""RPG parallel-generator contract helpers.

This module is an independent SIDScope interoperability layer.  It does not
vendor RPG source code or model weights.  The contract mirrors the observable
public RPG interfaces that matter for auditing: codebook-disjoint vocabulary
tokens, unordered token-set identity, per-item graph nodes, parallel token
scores, and iterative graph-valid item resolution.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


class RPGContractError(ValueError):
    """A typed RPG fixture or trace-contract failure."""

    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


@dataclass(frozen=True)
class RPGCatalogItem:
    """One item node in an RPG decoding graph."""

    source_item_id: str
    normalized_item_id: str
    semantic_codes: tuple[int, ...]
    model_vocabulary_tokens: tuple[int, ...]


def model_vocabulary_tokens(semantic_codes: Sequence[int], codebook_size: int) -> tuple[int, ...]:
    """Map per-codebook values to RPG's disjoint model-vocabulary ranges."""

    if codebook_size <= 0:
        raise RPGContractError("invalid_codebook_size", "codebook_size must be positive")
    tokens: list[int] = []
    for codebook, raw_code in enumerate(semantic_codes):
        code = int(raw_code)
        if code < 0 or code >= codebook_size:
            raise RPGContractError(
                "code_out_of_range",
                f"semantic code {code} is outside [0, {codebook_size}) for codebook {codebook}",
            )
        tokens.append(codebook * codebook_size + code + 1)
    if not tokens:
        raise RPGContractError("empty_token_set", "an RPG semantic ID must contain at least one token")
    return tuple(tokens)


def canonical_unordered_token_set(
    tokens: Iterable[int], *, n_codebooks: int, codebook_size: int
) -> tuple[int, ...]:
    """Validate and canonicalize one token from every disjoint codebook.

    Sorting is a serialization choice only.  It does not introduce a decoding
    order or prefix semantics.
    """

    values = tuple(int(token) for token in tokens)
    if len(values) != n_codebooks:
        raise RPGContractError(
            "wrong_token_count",
            f"expected {n_codebooks} tokens, observed {len(values)}",
        )
    if len(set(values)) != len(values):
        raise RPGContractError("duplicate_token", "an unordered RPG token set cannot repeat a token")

    partitions: list[int] = []
    max_token = n_codebooks * codebook_size
    for token in values:
        if token < 1 or token > max_token:
            raise RPGContractError(
                "token_out_of_vocabulary",
                f"token {token} is outside the RPG item vocabulary [1, {max_token}]",
            )
        partitions.append((token - 1) // codebook_size)
    expected = set(range(n_codebooks))
    observed = set(partitions)
    if len(partitions) != len(observed):
        raise RPGContractError(
            "duplicate_codebook_partition",
            "an RPG token set must contain exactly one token from each codebook",
        )
    if observed != expected:
        raise RPGContractError(
            "missing_codebook_partition",
            f"expected one token from each codebook {sorted(expected)}, observed {sorted(observed)}",
        )
    return tuple(sorted(values))


def build_catalog(
    rows: Sequence[Mapping[str, Any]], *, n_codebooks: int, codebook_size: int
) -> list[RPGCatalogItem]:
    """Build a validated item-node catalog from source-shaped fixture rows."""

    items: list[RPGCatalogItem] = []
    seen_normalized: set[str] = set()
    seen_source: set[str] = set()
    for row in rows:
        source_item_id = str(row["source_item_id"])
        normalized_item_id = str(row["normalized_item_id"])
        if source_item_id in seen_source:
            raise RPGContractError("duplicate_source_item", f"duplicate source item {source_item_id!r}")
        if normalized_item_id in seen_normalized:
            raise RPGContractError(
                "duplicate_normalized_item", f"duplicate normalized item {normalized_item_id!r}"
            )
        semantic_codes = tuple(int(value) for value in row["semantic_codes"])
        if len(semantic_codes) != n_codebooks:
            raise RPGContractError(
                "wrong_semantic_code_count",
                f"item {source_item_id!r} has {len(semantic_codes)} codes; expected {n_codebooks}",
            )
        vocabulary = model_vocabulary_tokens(semantic_codes, codebook_size)
        canonical_unordered_token_set(
            vocabulary, n_codebooks=n_codebooks, codebook_size=codebook_size
        )
        items.append(
            RPGCatalogItem(
                source_item_id=source_item_id,
                normalized_item_id=normalized_item_id,
                semantic_codes=semantic_codes,
                model_vocabulary_tokens=vocabulary,
            )
        )
        seen_source.add(source_item_id)
        seen_normalized.add(normalized_item_id)
    if not items:
        raise RPGContractError("empty_catalog", "RPG catalog cannot be empty")
    return items


def token_set_resolution(
    tokens: Iterable[int],
    catalog: Sequence[RPGCatalogItem],
    *,
    n_codebooks: int,
    codebook_size: int,
) -> dict[str, Any]:
    """Resolve an unordered token set without hiding item-level ambiguity."""

    canonical = canonical_unordered_token_set(
        tokens, n_codebooks=n_codebooks, codebook_size=codebook_size
    )
    matches = sorted(
        item.normalized_item_id
        for item in catalog
        if canonical_unordered_token_set(
            item.model_vocabulary_tokens,
            n_codebooks=n_codebooks,
            codebook_size=codebook_size,
        )
        == canonical
    )
    return {
        "unordered_token_set": list(canonical),
        "resolved_item_ids": matches,
        "resolution_status": (
            "unresolved_token_set"
            if not matches
            else "unique_item"
            if len(matches) == 1
            else "ambiguous_item_nodes"
        ),
        "ambiguity_count": max(len(matches) - 1, 0),
    }


def _rank_key(record: Mapping[str, Any]) -> tuple[float, str]:
    return (-float(record["score_sum_log_probability"]), str(record["normalized_item_id"]))


def run_deterministic_graph_fixture(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Run a deterministic CPU fixture over explicit initial item nodes.

    The official implementation samples the initial beam.  A conformance
    fixture supplies those item nodes explicitly so its output is stable while
    preserving the method's parallel graph-propagation state.
    """

    config = manifest["configuration"]
    n_codebooks = int(config["n_codebooks"])
    codebook_size = int(config["codebook_size"])
    beam_size = int(config["beam_size"])
    propagation_steps = int(config["propagation_steps"])
    top_k = int(config["top_k"])
    if beam_size <= 0 or propagation_steps <= 0 or top_k <= 0 or top_k > beam_size:
        raise RPGContractError(
            "invalid_decoding_configuration",
            "beam_size and propagation_steps must be positive and top_k must be in [1, beam_size]",
        )

    catalog = build_catalog(
        manifest["catalog"], n_codebooks=n_codebooks, codebook_size=codebook_size
    )
    by_id = {item.normalized_item_id: item for item in catalog}
    graph = {str(item_id): [str(value) for value in neighbors] for item_id, neighbors in manifest["graph"].items()}
    if set(graph) != set(by_id):
        raise RPGContractError("graph_catalog_mismatch", "graph nodes must exactly match catalog items")
    for item_id, neighbors in graph.items():
        unknown = sorted(set(neighbors) - set(by_id))
        if unknown:
            raise RPGContractError("unknown_graph_neighbor", f"graph node {item_id!r} has unknown neighbors {unknown}")
        if item_id not in neighbors:
            raise RPGContractError("missing_self_edge", f"graph node {item_id!r} must retain a self edge")

    raw_scores = {int(token): float(score) for token, score in manifest["parallel_token_log_probabilities"].items()}
    required_tokens = {token for item in catalog for token in item.model_vocabulary_tokens}
    missing_scores = sorted(required_tokens - set(raw_scores))
    if missing_scores:
        raise RPGContractError("missing_token_score", f"missing log probabilities for tokens {missing_scores}")

    resolution_by_set: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for item in catalog:
        canonical = canonical_unordered_token_set(
            item.model_vocabulary_tokens,
            n_codebooks=n_codebooks,
            codebook_size=codebook_size,
        )
        resolution_by_set[canonical].append(item.normalized_item_id)

    def record(item_id: str) -> dict[str, Any]:
        item = by_id[item_id]
        canonical = canonical_unordered_token_set(
            item.model_vocabulary_tokens,
            n_codebooks=n_codebooks,
            codebook_size=codebook_size,
        )
        token_scores = [raw_scores[token] for token in canonical]
        resolved = sorted(resolution_by_set[canonical])
        return {
            "source_item_id": item.source_item_id,
            "normalized_item_id": item.normalized_item_id,
            "semantic_codes": list(item.semantic_codes),
            "unordered_token_set": list(canonical),
            "model_vocabulary_tokens": list(item.model_vocabulary_tokens),
            "score_sum_log_probability": round(sum(token_scores), 12),
            "score_mean_log_probability": round(sum(token_scores) / len(token_scores), 12),
            "graph_valid": True,
            "resolved_item_ids": resolved,
            "resolution_status": "unique_item" if len(resolved) == 1 else "ambiguous_item_nodes",
            "ambiguity_count": max(len(resolved) - 1, 0),
        }

    frontier = [str(value) for value in manifest["initial_item_ids"]]
    if len(frontier) != beam_size or len(set(frontier)) != len(frontier):
        raise RPGContractError("invalid_initial_frontier", "initial_item_ids must contain beam_size distinct nodes")
    unknown_initial = sorted(set(frontier) - set(by_id))
    if unknown_initial:
        raise RPGContractError("unknown_initial_item", f"unknown initial items {unknown_initial}")

    visited = set(frontier)
    steps: list[dict[str, Any]] = []
    for step_index in range(propagation_steps):
        candidate_ids = sorted({neighbor for item_id in frontier for neighbor in graph[item_id]})
        visited.update(candidate_ids)
        candidates = sorted((record(item_id) for item_id in candidate_ids), key=_rank_key)
        selected = [entry["normalized_item_id"] for entry in candidates[:beam_size]]
        steps.append(
            {
                "propagation_step": step_index + 1,
                "frontier_item_ids": list(frontier),
                "candidate_item_ids": candidate_ids,
                "candidates": candidates,
                "selected_item_ids": selected,
            }
        )
        frontier = selected

    ranked = sorted((record(item_id) for item_id in frontier), key=_rank_key)[:top_k]
    ranked_items = [dict(entry, rank=index + 1) for index, entry in enumerate(ranked)]
    collisions = [
        {"unordered_token_set": list(token_set), "item_ids": sorted(item_ids)}
        for token_set, item_ids in sorted(resolution_by_set.items())
        if len(item_ids) > 1
    ]
    target = str(manifest["target_normalized_item_id"])
    if target not in by_id:
        raise RPGContractError("unknown_target_item", f"unknown target item {target!r}")

    return {
        "schema": "sidscope.rpg_parallel_trace.v1",
        "route_id": str(manifest["route_id"]),
        "trace_id": str(manifest["trace_id"]),
        "adapter_kind": "parallel_generator",
        "decode_state_kind": "unordered_token_set_graph_propagation",
        "split_id": str(config["split_id"]),
        "target_universe": str(config["target_universe"]),
        "target_source_item_id": by_id[target].source_item_id,
        "target_normalized_item_id": target,
        "initial_item_ids": list(manifest["initial_item_ids"]),
        "parallel_token_log_probabilities": {str(key): raw_scores[key] for key in sorted(raw_scores)},
        "steps": steps,
        "ranked_items": ranked_items,
        "visited_item_ids": sorted(visited),
        "validity": {
            "all_ranked_items_graph_valid": all(item["graph_valid"] for item in ranked_items),
            "invalid_item_count": 0,
        },
        "ambiguity": {
            "token_set_collision_count": len(collisions),
            "collisions": collisions,
            "policy": "keep per-item graph nodes; never collapse identical token sets to one item",
        },
        "failure_labels": [],
        "fixture_boundary": "deterministic source-shaped CPU contract; not an official checkpoint smoke",
    }


__all__ = [
    "RPGCatalogItem",
    "RPGContractError",
    "build_catalog",
    "canonical_unordered_token_set",
    "model_vocabulary_tokens",
    "run_deterministic_graph_fixture",
    "token_set_resolution",
]
