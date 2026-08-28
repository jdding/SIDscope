#!/usr/bin/env python3
"""Fail-closed verification for a trained RPG trace bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SHA256 = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "sidscope.rpg_trained_trace_bundle.v1"
SCHEMA_V2 = "sidscope.rpg_trained_trace_bundle.v2"
SOURCE_REVISION = "7dcf95ce9e08601810efdd1c850ed6dada5f97c2"
FORBIDDEN_KEYS = {
    "source_item_id",
    "source_user_id",
    "raw_item_id",
    "raw_user_id",
    "asin",
    "user_id",
    "prefix",
    "prefix_depth",
    "beam_parent",
    "beam_parent_index",
    "parent_beam",
    "ancestry",
    "autoregressive_order",
    "generation_order",
}


class Failure(ValueError):
    pass


def fail(label: str, detail: str) -> None:
    raise Failure(f"{label}: {detail}")


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def walk_no_identity_leak(value: Any, location: str = "bundle") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS or "prefix" in lowered:
                fail("identity_or_method_leak", f"forbidden key {location}.{key}")
            walk_no_identity_leak(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_no_identity_leak(child, f"{location}[{index}]")
    elif isinstance(value, str) and value.startswith("/"):
        fail("private_path_leak", location)


def finite_number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail("invalid_score", location)
    result = float(value)
    if not math.isfinite(result):
        fail("nonfinite_score", location)
    return result


def _verify_v1(bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("schema") != SCHEMA:
        fail("invalid_schema", str(bundle.get("schema")))
    if bundle.get("method") != "RPG":
        fail("invalid_method", str(bundle.get("method")))
    if bundle.get("decode_state_kind") != "unordered_token_set_graph_propagation":
        fail("invalid_decode_state", str(bundle.get("decode_state_kind")))
    walk_no_identity_leak(bundle)

    source = bundle.get("source")
    if not isinstance(source, dict) or source.get("revision") != SOURCE_REVISION:
        fail("source_revision_mismatch", str(source))
    if source.get("license") != "CC-BY-NC-4.0":
        fail("source_license_mismatch", str(source.get("license")))
    config = bundle.get("configuration")
    expected_config = {
        "n_codebooks": 32,
        "codebook_size": 256,
        "num_beams": 20,
        "n_edges": 200,
        "propagation_steps": 3,
        "temperature": 0.03,
    }
    if not isinstance(config, dict) or any(config.get(k) != v for k, v in expected_config.items()):
        fail("configuration_mismatch", str(config))
    rank_cutoff = config.get("rank_cutoff")
    if not isinstance(rank_cutoff, int) or isinstance(rank_cutoff, bool) or not 1 <= rank_cutoff <= 20:
        fail("invalid_rank_cutoff", str(rank_cutoff))

    evidence = bundle.get("evidence")
    if not isinstance(evidence, dict):
        fail("missing_evidence", "evidence must be an object")
    for key in (
        "checkpoint_sha256",
        "training_manifest_sha256",
        "semantic_id_cache_sha256",
        "item_mapping_sha256",
        "interaction_sequences_sha256",
        "adjacency_int64_sha256",
        "source_model_sha256",
        "formal_training_runner_sha256",
        "reproduction_runner_sha256",
        "exporter_sha256",
        "verifier_sha256",
    ):
        if not isinstance(evidence.get(key), str) or not SHA256.fullmatch(evidence[key]):
            fail("invalid_evidence_hash", key)
    if evidence.get("split_id") != "AmazonReviews2014/Beauty:leave_one_out:test":
        fail("split_identity_mismatch", str(evidence.get("split_id")))

    target = bundle.get("target_universe")
    if not isinstance(target, dict) or target.get("schema") != "canonical_normalized_item_sid_rows.v1":
        fail("invalid_target_universe", str(target))
    rows = target.get("rows")
    if target.get("row_count") != 12101 or not isinstance(rows, list):
        fail("target_universe_cardinality", str(target.get("row_count")))
    visibility = target.get("visibility")
    if visibility not in {"external_complete", "bounded_rows_full_universe_hash_bound"}:
        fail("target_universe_visibility", str(visibility))
    universe_sha256 = target.get("sha256")
    if not isinstance(universe_sha256, str) or not SHA256.fullmatch(universe_sha256):
        fail("target_universe_hash", str(universe_sha256))
    if visibility == "external_complete":
        if len(rows) != 12101:
            fail("target_universe_complete_cardinality", str(len(rows)))
        if universe_sha256 != canonical_hash(rows):
            fail("target_universe_hash_mismatch", "canonical rows do not match")
    elif not 1 <= len(rows) <= 5120:
        fail("target_universe_bounded_cardinality", str(len(rows)))
    row_by_id: dict[int, dict[str, Any]] = {}
    token_set_to_ids: dict[tuple[int, ...], list[int]] = {}
    previous_id = -1
    for row in rows:
        item_id = row.get("normalized_item_id") if isinstance(row, dict) else None
        if (
            not isinstance(item_id, int)
            or isinstance(item_id, bool)
            or not 0 <= item_id < 12101
            or item_id <= previous_id
        ):
            fail("target_universe_order", str(item_id))
        previous_id = item_id
        codes = row.get("semantic_codes")
        tokens = row.get("unordered_model_vocabulary_tokens")
        if not isinstance(codes, list) or len(codes) != 32:
            fail("invalid_semantic_codes", str(item_id))
        expected_tokens = []
        for head, code in enumerate(codes):
            if not isinstance(code, int) or isinstance(code, bool) or not 0 <= code < 256:
                fail("semantic_code_out_of_range", f"{item_id}:{head}")
            expected_tokens.append(head * 256 + code + 1)
        if tokens != expected_tokens:
            fail("model_vocabulary_mismatch", str(item_id))
        row_by_id[item_id] = row
        token_set_to_ids.setdefault(tuple(tokens), []).append(item_id)

    episodes = bundle.get("episodes")
    if not isinstance(episodes, list) or not 1 <= len(episodes) <= 256:
        fail("invalid_episode_count", str(len(episodes) if isinstance(episodes, list) else None))
    seen_trace_ids: set[str] = set()
    hits = 0
    for episode_index, episode in enumerate(episodes):
        location = f"episode[{episode_index}]"
        if not isinstance(episode, dict):
            fail("invalid_episode", location)
        trace_id = episode.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id or trace_id in seen_trace_ids:
            fail("invalid_trace_id", location)
        seen_trace_ids.add(trace_id)
        if episode.get("split") != "test_leave_one_out":
            fail("episode_split_mismatch", trace_id)
        if episode.get("decode_state_kind") != bundle["decode_state_kind"]:
            fail("episode_decode_state_mismatch", trace_id)
        context = episode.get("context_normalized_item_ids")
        target_id = episode.get("target_normalized_item_id")
        if (
            not isinstance(context, list)
            or not context
            or any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 12101 for value in context)
        ):
            fail("invalid_context", trace_id)
        if not isinstance(target_id, int) or isinstance(target_id, bool) or not 0 <= target_id < 12101:
            fail("invalid_target", trace_id)

        parallel = episode.get("parallel_token_scores")
        if not isinstance(parallel, dict) or parallel.get("shape") != [32, 256]:
            fail("parallel_score_shape", trace_id)
        if not isinstance(parallel.get("float32_sha256"), str) or not SHA256.fullmatch(parallel["float32_sha256"]):
            fail("parallel_score_hash", trace_id)
        heads = parallel.get("per_codebook_topk")
        if not isinstance(heads, list) or len(heads) != 32:
            fail("parallel_head_count", trace_id)
        for head, head_row in enumerate(heads):
            if head_row.get("codebook") != head:
                fail("parallel_head_order", f"{trace_id}:{head}")
            top_tokens = head_row.get("top_tokens")
            if not isinstance(top_tokens, list) or not top_tokens:
                fail("empty_parallel_topk", f"{trace_id}:{head}")
            previous = math.inf
            for token_row in top_tokens:
                token = token_row.get("model_vocabulary_token")
                if not isinstance(token, int) or not head * 256 + 1 <= token <= (head + 1) * 256:
                    fail("parallel_token_partition", f"{trace_id}:{head}")
                score = finite_number(token_row.get("log_probability"), f"{trace_id}:{head}")
                if score > previous + 1e-9:
                    fail("parallel_topk_order", f"{trace_id}:{head}")
                previous = score

        initial = episode.get("initial_item_nodes")
        if (
            not isinstance(initial, list)
            or len(initial) != 20
            or any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 12101 for value in initial)
        ):
            fail("invalid_initial_frontier", trace_id)
        if episode.get("initial_item_node_duplicates") != 20 - len(set(initial)):
            fail("initial_duplicate_count", trace_id)
        visited = set(initial)
        steps = episode.get("propagation")
        if not isinstance(steps, list) or len(steps) != 3:
            fail("propagation_step_count", trace_id)
        final_frontier: list[int] = []
        final_scores: dict[int, float] = {}
        for expected_step, step in enumerate(steps, start=1):
            if step.get("step") != expected_step:
                fail("propagation_step_order", trace_id)
            candidates = step.get("candidates")
            if not isinstance(candidates, list) or step.get("candidate_count") != len(candidates):
                fail("candidate_count_mismatch", f"{trace_id}:{expected_step}")
            candidate_scores: dict[int, float] = {}
            for candidate in candidates:
                item_id = candidate.get("normalized_item_id")
                if (
                    not isinstance(item_id, int)
                    or isinstance(item_id, bool)
                    or not 0 <= item_id < 12101
                    or item_id in candidate_scores
                ):
                    fail("invalid_or_duplicate_candidate", f"{trace_id}:{expected_step}")
                candidate_scores[item_id] = finite_number(
                    candidate.get("mean_log_probability"), f"{trace_id}:{expected_step}:{item_id}"
                )
            frontier = step.get("frontier")
            if not isinstance(frontier, list) or len(frontier) != 20 or len(set(frontier)) != 20:
                fail("invalid_propagation_frontier", f"{trace_id}:{expected_step}")
            if any(item_id not in candidate_scores for item_id in frontier):
                fail("frontier_not_candidate", f"{trace_id}:{expected_step}")
            frontier_scores = [candidate_scores[item_id] for item_id in frontier]
            if any(left < right - 1e-8 for left, right in zip(frontier_scores, frontier_scores[1:])):
                fail("frontier_score_order", f"{trace_id}:{expected_step}")
            visited.update(candidate_scores)
            final_frontier = frontier
            final_scores = candidate_scores
        if episode.get("visited_item_node_count") != len(visited):
            fail("visited_count_mismatch", trace_id)

        ranked = episode.get("ranked_items")
        if not isinstance(ranked, list) or len(ranked) != rank_cutoff:
            fail("ranked_item_count", trace_id)
        for expected_rank, ranked_row in enumerate(ranked, start=1):
            item_id = ranked_row.get("normalized_item_id")
            if ranked_row.get("rank") != expected_rank or item_id != final_frontier[expected_rank - 1]:
                fail("ranked_frontier_mismatch", f"{trace_id}:{expected_rank}")
            if item_id not in row_by_id:
                fail("ranked_target_row_missing", f"{trace_id}:{expected_rank}")
            universe_row = row_by_id[item_id]
            if ranked_row.get("semantic_codes") != universe_row["semantic_codes"]:
                fail("ranked_semantic_code_mismatch", f"{trace_id}:{expected_rank}")
            tokens = ranked_row.get("unordered_model_vocabulary_tokens")
            if tokens != universe_row["unordered_model_vocabulary_tokens"]:
                fail("ranked_token_mismatch", f"{trace_id}:{expected_rank}")
            per_codebook = ranked_row.get("codebook_log_probabilities")
            if not isinstance(per_codebook, list) or len(per_codebook) != 32:
                fail("ranked_codebook_score_count", f"{trace_id}:{expected_rank}")
            score_values = [finite_number(value, f"{trace_id}:{expected_rank}") for value in per_codebook]
            mean_score = finite_number(ranked_row.get("mean_log_probability"), trace_id)
            sum_score = finite_number(ranked_row.get("sum_log_probability"), trace_id)
            # The official path reduces the 32 values in float32, while the
            # exported per-codebook values are decimal JSON numbers.  Bound
            # their expected float32 reduction drift without accepting a
            # material score mismatch.
            if abs(sum(score_values) - sum_score) > 3e-5 or abs(sum_score / 32 - mean_score) > 2e-8:
                fail("ranked_score_accounting", f"{trace_id}:{expected_rank}")
            if abs(final_scores[item_id] - mean_score) > 1e-8:
                fail("ranked_candidate_score_mismatch", f"{trace_id}:{expected_rank}")
            resolved = ranked_row.get("resolved_normalized_item_ids")
            if not isinstance(resolved, list) or not resolved:
                fail("ranked_resolution_missing", f"{trace_id}:{expected_rank}")
            if any(resolved_id not in row_by_id for resolved_id in resolved):
                fail("ranked_resolution_row_missing", f"{trace_id}:{expected_rank}")
            bounded_resolution = token_set_to_ids[tuple(tokens)]
            if bounded_resolution != resolved:
                fail("ranked_resolution_rows_mismatch", f"{trace_id}:{expected_rank}")
            expected_resolution = "unique_item_node" if len(resolved) == 1 else "ambiguous_item_nodes"
            if ranked_row.get("resolution_status") != expected_resolution or ranked_row.get(
                "resolved_normalized_item_ids"
            ) != resolved:
                fail("ranked_resolution_mismatch", f"{trace_id}:{expected_rank}")
            if ranked_row.get("graph_valid") is not True:
                fail("ranked_graph_validity", f"{trace_id}:{expected_rank}")
        target_rank = next(
            (row["rank"] for row in ranked if row["normalized_item_id"] == target_id), None
        )
        if episode.get("target_rank") != target_rank:
            fail("target_rank_mismatch", trace_id)
        if target_rank is not None:
            hits += 1
        if episode.get("termination_reason") != "completed_configured_graph_propagation":
            fail("termination_reason", trace_id)

    summary = bundle.get("summary")
    if not isinstance(summary, dict) or summary.get("episode_count") != len(episodes):
        fail("summary_episode_count", str(summary))
    if summary.get("hit_at_rank_cutoff") != hits:
        fail("summary_hit_count", str(summary.get("hit_at_rank_cutoff")))
    recall = finite_number(summary.get("recall_at_rank_cutoff"), "summary.recall")
    if abs(recall - hits / len(episodes)) > 1e-12:
        fail("summary_recall", str(recall))
    return {
        "schema": "sidscope.rpg_trained_trace_verification.v1",
        "status": "pass",
        "bundle_id": bundle.get("bundle_id"),
        "episodes": len(episodes),
        "target_universe_rows": target["row_count"],
        "published_target_rows": len(rows),
        "target_universe_visibility": visibility,
        "hit_at_rank_cutoff": hits,
        "recall_at_rank_cutoff": recall,
        "checkpoint_sha256": evidence["checkpoint_sha256"],
        "target_universe_sha256": target["sha256"],
    }


def _verify_v2(
    bundle: dict[str, Any],
    prepared: Optional[dict[str, Any]],
    selection: Optional[dict[str, Any]],
) -> dict[str, Any]:
    from tools.rpg_non_ar_bridge import (
        BridgeFailure,
        build_downstream_handoff,
        canonical_hash as bridge_hash,
        validate_episode_selection,
        validate_prepared_dataset,
    )

    if prepared is None or selection is None:
        fail("missing_external_contract", "v2 requires prepared dataset and episode selection manifests")
    try:
        validate_prepared_dataset(prepared)
        validate_episode_selection(selection, prepared)
    except BridgeFailure as exc:
        raise Failure(str(exc)) from exc
    if prepared["training"].get("status", "complete") != "complete":
        fail("training_binding_incomplete", str(prepared["training"].get("status")))
    if bundle.get("schema") != SCHEMA_V2:
        fail("invalid_schema", str(bundle.get("schema")))
    if bundle.get("method") != "RPG" or bundle.get("decode_state_kind") != (
        "unordered_token_set_graph_propagation"
    ):
        fail("invalid_method_or_decode_state", str(bundle.get("method")))
    walk_no_identity_leak(bundle)
    if bundle.get("dataset") != prepared["dataset"]:
        fail("dataset_identity_mismatch", str(bundle.get("dataset")))
    source = bundle.get("source")
    if source != prepared["source"]:
        fail("source_binding_mismatch", str(source))

    config = bundle.get("configuration")
    if config != prepared["configuration"]:
        fail("configuration_mismatch", str(config))
    n_codebooks = config["n_codebooks"]
    codebook_size = config["codebook_size"]
    num_beams = config["num_beams"]
    propagation_steps = config["propagation_steps"]
    rank_cutoff = config["rank_cutoff"]
    catalog_rows = prepared["catalog"]["row_count"]

    evidence = bundle.get("evidence")
    if not isinstance(evidence, dict):
        fail("missing_evidence", "evidence")
    required_bindings = {
        "prepared_dataset_contract_sha256": bridge_hash(prepared),
        "episode_selection_manifest_sha256": bridge_hash(selection),
        "split_id": prepared["splits"]["test"]["split_id"],
        "split_sha256": prepared["splits"]["test"]["sha256"],
        "semantic_id_cache_sha256": prepared["artifacts"]["semantic_id_cache"]["sha256"],
        "item_mapping_sha256": prepared["artifacts"]["item_mapping"]["sha256"],
        "interaction_sequences_sha256": prepared["artifacts"]["interaction_sequences"]["sha256"],
        "checkpoint_sha256": prepared["training"]["checkpoint_sha256"],
        "training_manifest_sha256": prepared["training"]["training_manifest_sha256"],
    }
    for key, expected in required_bindings.items():
        if evidence.get(key) != expected:
            fail("evidence_binding_mismatch", key)
    for key in ("source_model_sha256", "exporter_sha256", "verifier_sha256", "adjacency_int64_sha256"):
        if not isinstance(evidence.get(key), str) or not SHA256.fullmatch(evidence[key]):
            fail("invalid_evidence_hash", key)

    target = bundle.get("target_universe")
    if not isinstance(target, dict) or target.get("schema") != "canonical_normalized_item_sid_rows.v1":
        fail("invalid_target_universe", str(target))
    if target.get("row_count") != catalog_rows or target.get("sha256") != prepared["catalog"][
        "target_universe_sha256"
    ]:
        fail("target_universe_binding_mismatch", str(target.get("row_count")))
    rows = target.get("rows")
    visibility = target.get("visibility")
    if visibility != "external_complete" or not isinstance(rows, list):
        fail("target_universe_visibility", str(visibility))
    if (
        len(rows) != catalog_rows or bridge_hash(rows) != target["sha256"]
    ):
        fail("target_universe_complete_mismatch", str(len(rows)))
    row_by_id: dict[int, dict[str, Any]] = {}
    token_set_to_ids: dict[tuple[int, ...], list[int]] = {}
    previous_id = -1
    for row in rows:
        item_id = row.get("normalized_item_id") if isinstance(row, dict) else None
        if (
            not isinstance(item_id, int)
            or isinstance(item_id, bool)
            or not 0 <= item_id < catalog_rows
            or item_id <= previous_id
        ):
            fail("target_universe_order", str(item_id))
        previous_id = item_id
        codes = row.get("semantic_codes")
        if not isinstance(codes, list) or len(codes) != n_codebooks:
            fail("invalid_semantic_codes", str(item_id))
        expected_tokens = []
        for head, code in enumerate(codes):
            if not isinstance(code, int) or isinstance(code, bool) or not 0 <= code < codebook_size:
                fail("semantic_code_out_of_range", f"{item_id}:{head}")
            expected_tokens.append(head * codebook_size + code + 1)
        if row.get("unordered_model_vocabulary_tokens") != expected_tokens:
            fail("model_vocabulary_mismatch", str(item_id))
        row_by_id[item_id] = row
        token_set_to_ids.setdefault(tuple(expected_tokens), []).append(item_id)

    episodes = bundle.get("episodes")
    selected_rows = selection["rows"]
    if not isinstance(episodes, list) or len(episodes) != len(selected_rows):
        fail("episode_selection_count_mismatch", str(len(episodes) if isinstance(episodes, list) else None))
    hits = 0
    seen_trace_ids: set[str] = set()
    for index, (episode, selected) in enumerate(zip(episodes, selected_rows)):
        location = f"episode[{index}]"
        if not isinstance(episode, dict):
            fail("invalid_episode", location)
        trace_id = episode.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id or trace_id in seen_trace_ids:
            fail("invalid_trace_id", location)
        seen_trace_ids.add(trace_id)
        if (
            episode.get("episode_id") != selected["episode_id"]
            or episode.get("selection_order") != selected["order"]
            or episode.get("split_row_index") != selected["split_row_index"]
            or episode.get("split_id") != prepared["splits"]["test"]["split_id"]
        ):
            fail("episode_selection_binding_mismatch", trace_id)
        if episode.get("decode_state_kind") != bundle["decode_state_kind"]:
            fail("episode_decode_state_mismatch", trace_id)
        context = episode.get("context_normalized_item_ids")
        target_id = episode.get("target_normalized_item_id")
        if (
            not isinstance(context, list)
            or not context
            or any(not isinstance(item, int) or isinstance(item, bool) or not 0 <= item < catalog_rows for item in context)
        ):
            fail("invalid_context", trace_id)
        if target_id != selected["expected_target_normalized_item_id"]:
            fail("episode_target_mismatch", trace_id)

        parallel = episode.get("parallel_token_scores")
        if not isinstance(parallel, dict) or parallel.get("shape") != [n_codebooks, codebook_size]:
            fail("parallel_score_shape", trace_id)
        if not isinstance(parallel.get("float32_sha256"), str) or not SHA256.fullmatch(parallel["float32_sha256"]):
            fail("parallel_score_hash", trace_id)
        heads = parallel.get("per_codebook_topk")
        if not isinstance(heads, list) or len(heads) != n_codebooks:
            fail("parallel_head_count", trace_id)
        for head, head_row in enumerate(heads):
            if head_row.get("codebook") != head:
                fail("parallel_head_order", f"{trace_id}:{head}")
            top_tokens = head_row.get("top_tokens")
            if not isinstance(top_tokens, list) or not top_tokens:
                fail("empty_parallel_topk", f"{trace_id}:{head}")
            previous = math.inf
            seen_tokens: set[int] = set()
            for token_row in top_tokens:
                token = token_row.get("model_vocabulary_token")
                if (
                    not isinstance(token, int)
                    or not head * codebook_size + 1 <= token <= (head + 1) * codebook_size
                    or token in seen_tokens
                ):
                    fail("parallel_token_partition", f"{trace_id}:{head}")
                seen_tokens.add(token)
                score = finite_number(token_row.get("log_probability"), f"{trace_id}:{head}")
                if score > previous + 1e-9:
                    fail("parallel_topk_order", f"{trace_id}:{head}")
                previous = score

        initial = episode.get("initial_item_nodes")
        if (
            not isinstance(initial, list)
            or len(initial) != num_beams
            or any(not isinstance(item, int) or isinstance(item, bool) or not 0 <= item < catalog_rows for item in initial)
        ):
            fail("invalid_initial_frontier", trace_id)
        if episode.get("initial_item_node_duplicates") != num_beams - len(set(initial)):
            fail("initial_duplicate_count", trace_id)
        visited = set(initial)
        steps = episode.get("propagation")
        if not isinstance(steps, list) or len(steps) != propagation_steps:
            fail("propagation_step_count", trace_id)
        final_frontier: list[int] = []
        final_scores: dict[int, float] = {}
        for expected_step, step in enumerate(steps, start=1):
            if step.get("step") != expected_step:
                fail("propagation_step_order", trace_id)
            candidates = step.get("candidates")
            if not isinstance(candidates, list) or step.get("candidate_count") != len(candidates):
                fail("candidate_count_mismatch", f"{trace_id}:{expected_step}")
            candidate_scores: dict[int, float] = {}
            for candidate in candidates:
                item_id = candidate.get("normalized_item_id")
                if (
                    not isinstance(item_id, int)
                    or isinstance(item_id, bool)
                    or not 0 <= item_id < catalog_rows
                    or item_id in candidate_scores
                ):
                    fail("invalid_or_duplicate_candidate", f"{trace_id}:{expected_step}")
                candidate_scores[item_id] = finite_number(candidate.get("mean_log_probability"), trace_id)
            frontier = step.get("frontier")
            if not isinstance(frontier, list) or len(frontier) != num_beams or len(set(frontier)) != num_beams:
                fail("invalid_propagation_frontier", f"{trace_id}:{expected_step}")
            if any(item not in candidate_scores for item in frontier):
                fail("frontier_not_candidate", f"{trace_id}:{expected_step}")
            scores = [candidate_scores[item] for item in frontier]
            if any(left < right - 1e-8 for left, right in zip(scores, scores[1:])):
                fail("frontier_score_order", f"{trace_id}:{expected_step}")
            visited.update(candidate_scores)
            final_frontier, final_scores = frontier, candidate_scores
        if episode.get("visited_item_node_count") != len(visited):
            fail("visited_count_mismatch", trace_id)

        ranked = episode.get("ranked_items")
        if not isinstance(ranked, list) or len(ranked) != rank_cutoff:
            fail("ranked_item_count", trace_id)
        for expected_rank, ranked_row in enumerate(ranked, start=1):
            item_id = ranked_row.get("normalized_item_id")
            if ranked_row.get("rank") != expected_rank or item_id != final_frontier[expected_rank - 1]:
                fail("ranked_frontier_mismatch", f"{trace_id}:{expected_rank}")
            universe_row = row_by_id.get(item_id)
            if universe_row is None:
                fail("ranked_target_row_missing", f"{trace_id}:{expected_rank}")
            if ranked_row.get("semantic_codes") != universe_row["semantic_codes"]:
                fail("ranked_semantic_code_mismatch", f"{trace_id}:{expected_rank}")
            tokens = ranked_row.get("unordered_model_vocabulary_tokens")
            if tokens != universe_row["unordered_model_vocabulary_tokens"]:
                fail("ranked_token_mismatch", f"{trace_id}:{expected_rank}")
            per_codebook = ranked_row.get("codebook_log_probabilities")
            if not isinstance(per_codebook, list) or len(per_codebook) != n_codebooks:
                fail("ranked_codebook_score_count", f"{trace_id}:{expected_rank}")
            values = [finite_number(value, trace_id) for value in per_codebook]
            sum_score = finite_number(ranked_row.get("sum_log_probability"), trace_id)
            mean_score = finite_number(ranked_row.get("mean_log_probability"), trace_id)
            if abs(sum(values) - sum_score) > 3e-5 or abs(sum_score / n_codebooks - mean_score) > 2e-8:
                fail("ranked_score_accounting", f"{trace_id}:{expected_rank}")
            if abs(final_scores[item_id] - mean_score) > 1e-8:
                fail("ranked_candidate_score_mismatch", f"{trace_id}:{expected_rank}")
            resolved = ranked_row.get("resolved_normalized_item_ids")
            if not isinstance(resolved, list) or not resolved or any(item not in row_by_id for item in resolved):
                fail("ranked_resolution_row_missing", f"{trace_id}:{expected_rank}")
            expected_resolved = token_set_to_ids.get(tuple(tokens), [])
            if resolved != expected_resolved:
                fail("ranked_resolution_rows_mismatch", f"{trace_id}:{expected_rank}")
            expected_status = "unique_item_node" if len(resolved) == 1 else "ambiguous_item_nodes"
            if ranked_row.get("resolution_status") != expected_status or ranked_row.get("graph_valid") is not True:
                fail("ranked_resolution_or_graph_validity", f"{trace_id}:{expected_rank}")
        target_rank = next((row["rank"] for row in ranked if row["normalized_item_id"] == target_id), None)
        if episode.get("target_rank") != target_rank:
            fail("target_rank_mismatch", trace_id)
        hits += int(target_rank is not None)
        if episode.get("termination_reason") != "completed_configured_graph_propagation":
            fail("termination_reason", trace_id)

    summary = bundle.get("summary")
    if not isinstance(summary, dict) or summary.get("episode_count") != len(episodes):
        fail("summary_episode_count", str(summary))
    if summary.get("hit_at_rank_cutoff") != hits:
        fail("summary_hit_count", str(summary.get("hit_at_rank_cutoff")))
    recall = finite_number(summary.get("recall_at_rank_cutoff"), "summary.recall")
    if abs(recall - hits / len(episodes)) > 1e-12:
        fail("summary_recall", str(recall))
    handoff = build_downstream_handoff(bundle, prepared, selection)
    return {
        "schema": "sidscope.rpg_trained_trace_verification.v2",
        "status": "pass",
        "bundle_id": bundle.get("bundle_id"),
        "episodes": len(episodes),
        "target_universe_rows": catalog_rows,
        "published_target_rows": len(rows),
        "target_universe_visibility": visibility,
        "hit_at_rank_cutoff": hits,
        "recall_at_rank_cutoff": recall,
        "checkpoint_sha256": evidence["checkpoint_sha256"],
        "target_universe_sha256": target["sha256"],
        "prepared_dataset_contract_sha256": evidence["prepared_dataset_contract_sha256"],
        "episode_selection_manifest_sha256": evidence["episode_selection_manifest_sha256"],
        "downstream_handoff": handoff,
    }


def verify(
    bundle: dict[str, Any],
    prepared: Optional[dict[str, Any]] = None,
    selection: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if bundle.get("schema") == SCHEMA:
        if prepared is not None or selection is not None:
            fail("unexpected_external_contract", "v1 Beauty bundle does not accept v2 manifests")
        return _verify_v1(bundle)
    if bundle.get("schema") == SCHEMA_V2:
        return _verify_v2(bundle, prepared, selection)
    fail("invalid_schema", str(bundle.get("schema")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--prepared-dataset", type=Path)
    parser.add_argument("--episode-selection", type=Path)
    parser.add_argument("--handoff-output", type=Path)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    try:
        value = json.loads(args.bundle.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            fail("invalid_json_root", "expected object")
        prepared = (
            json.loads(args.prepared_dataset.read_text(encoding="utf-8"))
            if args.prepared_dataset
            else None
        )
        selection = (
            json.loads(args.episode_selection.read_text(encoding="utf-8"))
            if args.episode_selection
            else None
        )
        result = verify(value, prepared, selection)
    except Exception as exc:
        result = {
            "schema": "sidscope.rpg_trained_trace_verification.v1",
            "status": "fail",
            "failure": f"{type(exc).__name__}: {exc}",
        }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(payload, end="")
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    if args.handoff_output and result.get("status") == "pass":
        handoff = result.get("downstream_handoff")
        if handoff is None:
            fail("handoff_requires_v2", str(value.get("schema")))
        args.handoff_output.parent.mkdir(parents=True, exist_ok=True)
        args.handoff_output.write_text(
            json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
