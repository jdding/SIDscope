"""Latte/PSID cache and autoregressive trace interoperability helpers.

The upstream Latte repository stores conflict-free semantic IDs as a JSON
object from source item identifiers to zero-based per-codebook values.  This
module validates that cache together with the upstream ``id_mapping.json`` and
normalizes it without importing the upstream training stack.

The code is an independent SIDScope adapter contract.  It does not vendor a
Latte checkpoint, Amazon data, sentence embeddings, or generated caches.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from sidinspector.interface import validate_columns


class LatteCacheContractError(ValueError):
    """A typed Latte/PSID cache, mapping, or trace failure."""

    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LATTE_SOURCE_URL = "https://github.com/hyp1231/Latte"
_LATTE_SOURCE_REVISION = "05e4e6d983225bcb7172f148a076890e80c524d1"
_FORBIDDEN_TRAINED_TRACE_KEYS = {
    "user_id",
    "source_user_id",
    "source_item_id",
    "target_item_id",
    "label",
    "labels",
    "checkpoint_path",
    "sid_path",
}


def _trained_trace_failure(label: str, detail: str) -> None:
    raise LatteCacheContractError(label, detail)


def _require_sha256(value: Any, field: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _trained_trace_failure("invalid_evidence_hash", f"{field} must be a lowercase SHA-256")


def _reject_private_trace_fields(value: Any, location: str = "bundle") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _FORBIDDEN_TRAINED_TRACE_KEYS:
                _trained_trace_failure("identity_leak", f"{location}.{key} is forbidden")
            _reject_private_trace_fields(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_trace_fields(child, f"{location}[{index}]")
    elif isinstance(value, str) and (value.startswith("/") or ":\\" in value):
        _trained_trace_failure("private_path_leak", f"{location} contains an absolute path")


def validate_latte_psid_trained_trace_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a bounded, deidentified trained PSID/Latte trace bundle.

    The contract deliberately requires final-beam ancestry and per-step
    log-probabilities. Aggregate metrics or confidence-only episode summaries
    cannot pass G2/G4/G5 through this interface.
    """

    _reject_private_trace_fields(bundle)
    if bundle.get("schema") != "sidscope.latte_psid_trained_trace_bundle.v1":
        _trained_trace_failure("invalid_trace_schema", "unexpected trained-trace schema")
    if not isinstance(bundle.get("bundle_id"), str) or not bundle["bundle_id"]:
        _trained_trace_failure("missing_bundle_id", "bundle_id is required")
    method = bundle.get("method")
    if method not in {"PSID", "Latte"}:
        _trained_trace_failure("invalid_method", "method must be PSID or Latte")
    expected_state = {
        "PSID": "ordered_sid_prefix_beam",
        "Latte": "latent_token_then_ordered_sid_prefix",
    }[method]
    if bundle.get("decode_state_kind") != expected_state:
        _trained_trace_failure("decode_state_mismatch", f"{method} requires {expected_state}")
    expected_aggregation = {"PSID": "none", "Latte": {"agg_max", "agg_sum"}}[method]
    aggregation = bundle.get("aggregation_method")
    if isinstance(expected_aggregation, set):
        if aggregation not in expected_aggregation:
            _trained_trace_failure("invalid_aggregation_method", str(aggregation))
    elif aggregation != expected_aggregation:
        _trained_trace_failure("invalid_aggregation_method", str(aggregation))

    evidence = bundle.get("evidence")
    if not isinstance(evidence, Mapping):
        _trained_trace_failure("missing_evidence_binding", "evidence object is required")
    if evidence.get("source_url") != _LATTE_SOURCE_URL:
        _trained_trace_failure("source_url_mismatch", "trained trace must bind the official Latte source")
    if evidence.get("source_revision") != _LATTE_SOURCE_REVISION:
        _trained_trace_failure("source_revision_mismatch", "trained trace must bind the audited Latte revision")
    if evidence.get("source_license") != "MIT":
        _trained_trace_failure("source_license_mismatch", "trained trace must retain the MIT code boundary")
    for field in (
        "dataset_manifest_sha256",
        "split_sha256",
        "sid_cache_sha256",
        "checkpoint_sha256",
        "training_config_sha256",
        "command_sha256",
        "log_summary_sha256",
    ):
        _require_sha256(evidence.get(field), f"evidence.{field}")
    if not isinstance(evidence.get("split_id"), str) or not evidence["split_id"]:
        _trained_trace_failure("missing_split_identity", "evidence.split_id is required")
    if not isinstance(evidence.get("training_boundary"), str) or not evidence["training_boundary"]:
        _trained_trace_failure("missing_training_boundary", "evidence.training_boundary is required")

    episodes = bundle.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        _trained_trace_failure("empty_trained_trace", "episodes must be non-empty")
    if len(episodes) > 256:
        _trained_trace_failure("unbounded_smoke", "trained smoke may contain at most 256 episodes")
    trace_ids: set[str] = set()
    ranked_rows = 0
    beam_rows = 0
    retries = 0
    for episode_index, episode in enumerate(episodes):
        if not isinstance(episode, Mapping):
            _trained_trace_failure("invalid_episode", f"episode {episode_index} is not an object")
        trace_id = episode.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id or trace_id in trace_ids:
            _trained_trace_failure("invalid_trace_id", f"episode {episode_index} trace_id is absent or duplicate")
        trace_ids.add(trace_id)
        if episode.get("target_free") is not True:
            _trained_trace_failure("target_leakage_boundary", f"episode {trace_id} is not target-free")
        if episode.get("split_id") != evidence["split_id"]:
            _trained_trace_failure("split_identity_mismatch", f"episode {trace_id} split differs from evidence")
        _require_sha256(episode.get("target_universe_sha256"), f"episode {trace_id}.target_universe_sha256")

        attempts = episode.get("attempts")
        if not isinstance(attempts, list) or not attempts:
            _trained_trace_failure("missing_decode_attempt", f"episode {trace_id} has no attempts")
        if episode.get("retry_performed") is not (len(attempts) > 1):
            _trained_trace_failure("retry_state_mismatch", f"episode {trace_id} retry flag disagrees with attempts")
        if method == "PSID" and len(attempts) != 1:
            _trained_trace_failure("unexpected_retry", f"PSID episode {trace_id} must have one attempt")
        if len(attempts) > 1:
            retries += 1
        for attempt_index, attempt in enumerate(attempts):
            if not isinstance(attempt, Mapping) or attempt.get("attempt_index") != attempt_index:
                _trained_trace_failure("attempt_index_mismatch", f"episode {trace_id} attempt order is invalid")
            for field in ("num_beams", "generated_steps", "vocabulary_size", "logits_scored"):
                if not isinstance(attempt.get(field), int) or attempt[field] <= 0:
                    _trained_trace_failure("invalid_compute_accounting", f"episode {trace_id} attempt {field} is invalid")
            if attempt["logits_scored"] != attempt["num_beams"] * attempt["generated_steps"] * attempt["vocabulary_size"]:
                _trained_trace_failure("compute_accounting_mismatch", f"episode {trace_id} logits_scored mismatch")
            beams = attempt.get("final_beams")
            if not isinstance(beams, list) or len(beams) != attempt["num_beams"]:
                _trained_trace_failure("beam_count_mismatch", f"episode {trace_id} final beam count mismatch")
            beam_ids: set[str] = set()
            for beam in beams:
                if not isinstance(beam, Mapping):
                    _trained_trace_failure("invalid_beam", f"episode {trace_id} contains a non-object beam")
                beam_id = beam.get("beam_id")
                if not isinstance(beam_id, str) or not beam_id or beam_id in beam_ids:
                    _trained_trace_failure("invalid_beam_id", f"episode {trace_id} beam_id is absent or duplicate")
                beam_ids.add(beam_id)
                ancestry = beam.get("beam_ancestry")
                step_scores = beam.get("step_log_probabilities")
                if not isinstance(ancestry, list) or len(ancestry) != attempt["generated_steps"]:
                    _trained_trace_failure("missing_beam_ancestry", f"episode {trace_id} beam {beam_id}")
                if not all(
                    isinstance(parent, int) and 0 <= parent < attempt["num_beams"] for parent in ancestry
                ):
                    _trained_trace_failure("invalid_beam_ancestry", f"episode {trace_id} beam {beam_id}")
                if not isinstance(step_scores, list) or len(step_scores) != attempt["generated_steps"]:
                    _trained_trace_failure("missing_step_logprob", f"episode {trace_id} beam {beam_id}")
                if not all(isinstance(score, (int, float)) for score in step_scores):
                    _trained_trace_failure("invalid_step_logprob", f"episode {trace_id} beam {beam_id}")
                codes = beam.get("ordered_semantic_codes")
                tokens = beam.get("ordered_model_vocabulary_tokens")
                if not isinstance(codes, list) or not codes or not all(
                    isinstance(code, int) and code >= 0 for code in codes
                ):
                    _trained_trace_failure("invalid_semantic_codes", f"episode {trace_id} beam {beam_id}")
                if not isinstance(tokens, list) or len(tokens) != len(codes) or not all(
                    isinstance(token, int) and token > 0 for token in tokens
                ):
                    _trained_trace_failure("model_vocabulary_mismatch", f"episode {trace_id} beam {beam_id}")
                if method == "Latte" and not isinstance(beam.get("latent_token"), int):
                    _trained_trace_failure("missing_latent_token", f"episode {trace_id} beam {beam_id}")
                if method == "PSID" and beam.get("latent_token") is not None:
                    _trained_trace_failure("unexpected_latent_token", f"episode {trace_id} beam {beam_id}")
                valid = beam.get("valid")
                failures = beam.get("failure_labels")
                if not isinstance(valid, bool) or not isinstance(failures, list):
                    _trained_trace_failure("invalid_resolution_state", f"episode {trace_id} beam {beam_id}")
                if valid and failures:
                    _trained_trace_failure("validity_label_conflict", f"episode {trace_id} beam {beam_id}")
                if not valid and not failures:
                    _trained_trace_failure("missing_failure_label", f"episode {trace_id} beam {beam_id}")
                resolved = beam.get("normalized_item_id")
                if valid and not isinstance(resolved, int):
                    _trained_trace_failure("missing_item_resolution", f"episode {trace_id} beam {beam_id}")
                if not valid and resolved is not None:
                    _trained_trace_failure("invalid_path_resolved", f"episode {trace_id} beam {beam_id}")
                if not isinstance(beam.get("sequence_score"), (int, float)):
                    _trained_trace_failure("missing_sequence_score", f"episode {trace_id} beam {beam_id}")
                beam_rows += 1

        ranked = episode.get("ranked_items")
        if not isinstance(ranked, list) or not ranked:
            _trained_trace_failure("empty_ranked_export", f"episode {trace_id} has no ranked items")
        final_support: dict[int, list[float]] = {}
        for beam in attempts[-1]["final_beams"]:
            if beam["valid"]:
                final_support.setdefault(beam["normalized_item_id"], []).append(float(beam["sequence_score"]))
        ranked_ids: set[int] = set()
        previous_score: float | None = None
        for expected_rank, row in enumerate(ranked, start=1):
            if not isinstance(row, Mapping) or row.get("rank") != expected_rank:
                _trained_trace_failure("rank_order_mismatch", f"episode {trace_id} ranked export is invalid")
            if not isinstance(row.get("normalized_item_id"), int):
                _trained_trace_failure("missing_ranked_item_identity", f"episode {trace_id} rank {expected_rank}")
            item_id = row["normalized_item_id"]
            if item_id in ranked_ids:
                _trained_trace_failure("duplicate_ranked_item", f"episode {trace_id} item {item_id}")
            ranked_ids.add(item_id)
            if not isinstance(row.get("score"), (int, float)):
                _trained_trace_failure("missing_ranked_item_score", f"episode {trace_id} rank {expected_rank}")
            score = float(row["score"])
            if previous_score is not None and score > previous_score:
                _trained_trace_failure("rank_score_order_mismatch", f"episode {trace_id} rank {expected_rank}")
            previous_score = score
            if not isinstance(row.get("supporting_beam_count"), int) or row["supporting_beam_count"] <= 0:
                _trained_trace_failure("invalid_support_count", f"episode {trace_id} rank {expected_rank}")
            scores = final_support.get(item_id)
            if not scores:
                _trained_trace_failure("ranked_item_not_resolved", f"episode {trace_id} item {item_id}")
            if row["supporting_beam_count"] != len(scores):
                _trained_trace_failure("support_count_mismatch", f"episode {trace_id} item {item_id}")
            expected_score = max(scores)
            if method == "Latte" and aggregation == "agg_sum":
                expected_score = float(np.logaddexp.reduce(scores))
            if not np.isclose(score, expected_score, rtol=1e-6, atol=1e-8):
                _trained_trace_failure("aggregation_score_mismatch", f"episode {trace_id} item {item_id}")
            ranked_rows += 1

    return {
        "schema": "sidscope.latte_psid_trained_trace_verification.v1",
        "status": "pass",
        "method": method,
        "episode_count": len(episodes),
        "beam_row_count": beam_rows,
        "ranked_item_row_count": ranked_rows,
        "retry_episode_count": retries,
        "checkpoint_sha256": evidence["checkpoint_sha256"],
        "sid_cache_sha256": evidence["sid_cache_sha256"],
        "split_id": evidence["split_id"],
    }

@dataclass(frozen=True)
class LatteItemIdentity:
    """One source item and its normalized/model-facing identities."""

    source_item_id: str
    normalized_item_id: int
    latte_item_token_id: int


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise LatteCacheContractError("duplicate_json_key", f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object while rejecting duplicate keys."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_reject_duplicate_pairs)
    except LatteCacheContractError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise LatteCacheContractError("invalid_json", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LatteCacheContractError("expected_json_object", f"expected JSON object in {path}")
    return value


def read_latte_item_mapping(path: Path) -> list[LatteItemIdentity]:
    """Validate the upstream PAD-reserved item mapping.

    Latte assigns ``[PAD]`` model token 0 and real items contiguous tokens from
    1.  SIDScope removes PAD and uses the zero-based ``token_id - 1`` identity.
    """

    raw = read_json_object(path)
    item2id = raw.get("item2id")
    id2item = raw.get("id2item")
    if not isinstance(item2id, dict) or not isinstance(id2item, list):
        raise LatteCacheContractError(
            "invalid_item_mapping_shape", "id_mapping.json must contain item2id object and id2item list"
        )
    if item2id.get("[PAD]") != 0 or not id2item or id2item[0] != "[PAD]":
        raise LatteCacheContractError("invalid_padding_identity", "Latte [PAD] must have token id 0")
    if len(item2id) != len(id2item):
        raise LatteCacheContractError("mapping_cardinality_mismatch", "item2id and id2item lengths differ")

    identities: list[LatteItemIdentity] = []
    for token_id, source_value in enumerate(id2item):
        source_item_id = str(source_value)
        mapped = item2id.get(source_item_id)
        if mapped != token_id:
            raise LatteCacheContractError(
                "mapping_inverse_mismatch",
                f"item2id/id2item disagree for {source_item_id!r}: expected {token_id}, got {mapped!r}",
            )
        if token_id:
            identities.append(
                LatteItemIdentity(
                    source_item_id=source_item_id,
                    normalized_item_id=token_id - 1,
                    latte_item_token_id=token_id,
                )
            )
    if not identities:
        raise LatteCacheContractError("empty_item_mapping", "mapping contains no non-PAD items")
    if len({item.source_item_id for item in identities}) != len(identities):
        raise LatteCacheContractError("duplicate_source_item", "mapping contains duplicate source item IDs")
    return identities


def read_sem_ids_cache(
    path: Path,
    *,
    expected_source_items: Iterable[str],
    n_codebooks: int,
    codebook_size: int,
) -> dict[str, tuple[int, ...]]:
    """Validate one complete upstream-shaped ``.sem_ids`` cache."""

    if n_codebooks <= 0 or codebook_size <= 0:
        raise LatteCacheContractError("invalid_vq_configuration", "VQ dimensions must be positive")
    raw = read_json_object(path)
    expected = {str(item) for item in expected_source_items}
    observed = set(raw)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise LatteCacheContractError(
            "cache_catalog_mismatch",
            f"cache/catalog mismatch: missing={missing[:5]} extra={extra[:5]}",
        )

    out: dict[str, tuple[int, ...]] = {}
    reverse: dict[tuple[int, ...], str] = {}
    for source_item_id in sorted(raw):
        values = raw[source_item_id]
        if not isinstance(values, list) or len(values) != n_codebooks:
            raise LatteCacheContractError(
                "wrong_sid_depth", f"{source_item_id!r} must contain exactly {n_codebooks} SID values"
            )
        codes: list[int] = []
        for level, value in enumerate(values):
            if isinstance(value, bool) or not isinstance(value, int):
                raise LatteCacheContractError(
                    "non_integer_sid_code", f"{source_item_id!r} level {level} is not an integer"
                )
            if value < 0 or value >= codebook_size:
                raise LatteCacheContractError(
                    "sid_code_out_of_range",
                    f"{source_item_id!r} level {level} value {value} is outside [0, {codebook_size})",
                )
            codes.append(value)
        semantic_id = tuple(codes)
        if semantic_id in reverse:
            raise LatteCacheContractError(
                "semantic_id_collision",
                f"conflict-free PSID cache maps both {reverse[semantic_id]!r} and {source_item_id!r} to {semantic_id}",
            )
        reverse[semantic_id] = source_item_id
        out[source_item_id] = semantic_id
    return out


def psid_vocabulary_tokens(codes: Sequence[int], codebook_size: int) -> tuple[int, ...]:
    """Apply the official PSID disjoint-codebook token offsets."""

    return tuple(int(code) + level * codebook_size + 1 for level, code in enumerate(codes))


def latte_vocabulary_tokens(
    codes: Sequence[int], codebook_size: int, n_latent_tokens: int
) -> tuple[int, ...]:
    """Apply the official Latte offsets after the latent-token range."""

    if n_latent_tokens <= 0:
        raise LatteCacheContractError("invalid_latent_configuration", "n_latent_tokens must be positive")
    return tuple(
        int(code) + n_latent_tokens + level * codebook_size + 1
        for level, code in enumerate(codes)
    )


def normalize_latte_sem_ids(
    sem_ids_path: Path,
    item_mapping_path: Path,
    *,
    method: str,
    dataset: str,
    vq_method: str,
    n_codebooks: int,
    codebook_size: int,
) -> pd.DataFrame:
    """Normalize an official-shaped Latte/PSID cache into SIDScope rows."""

    identities = read_latte_item_mapping(item_mapping_path)
    cache = read_sem_ids_cache(
        sem_ids_path,
        expected_source_items=(item.source_item_id for item in identities),
        n_codebooks=n_codebooks,
        codebook_size=codebook_size,
    )
    rows: list[dict[str, Any]] = []
    for item in identities:
        codes = cache[item.source_item_id]
        row: dict[str, Any] = {
            "item_id": item.normalized_item_id,
            "source_item_id": item.source_item_id,
            "latte_item_token_id": item.latte_item_token_id,
            "method": method,
            "dataset": dataset,
            "vq_method": vq_method,
        }
        for level, code in enumerate(codes):
            row[f"sid_level_{level}"] = code
        row["sid"] = "-".join(str(code) for code in codes)
        rows.append(row)
    out = pd.DataFrame(rows)
    validate_columns("sid_assignments", out.columns)
    return out


def normalize_latte_metadata(
    item_mapping_path: Path,
    *,
    dataset: str,
    category: str,
    metadata_path: Path | None = None,
) -> pd.DataFrame:
    """Normalize item identity and optional upstream sentence metadata."""

    identities = read_latte_item_mapping(item_mapping_path)
    metadata = read_json_object(metadata_path) if metadata_path else {}
    if metadata_path:
        missing = sorted({item.source_item_id for item in identities} - set(metadata))
        extra = sorted(set(metadata) - {item.source_item_id for item in identities})
        if missing or extra:
            raise LatteCacheContractError(
                "metadata_catalog_mismatch", f"metadata/catalog mismatch: missing={missing[:5]} extra={extra[:5]}"
            )
    rows = [
        {
            "item_id": item.normalized_item_id,
            "source_item_id": item.source_item_id,
            "latte_item_token_id": item.latte_item_token_id,
            "dataset": dataset,
            "category": category,
            **({"text": str(metadata[item.source_item_id])} if metadata_path else {}),
        }
        for item in identities
    ]
    out = pd.DataFrame(rows)
    validate_columns("item_metadata", out.columns)
    return out


def normalize_latte_interactions(
    all_item_seqs_path: Path,
    item_mapping_path: Path,
    *,
    dataset: str,
) -> pd.DataFrame:
    """Normalize the upstream longest-per-user item-sequence cache."""

    mapping = read_json_object(item_mapping_path)
    identities = read_latte_item_mapping(item_mapping_path)
    source_to_item = {item.source_item_id: item for item in identities}
    user2id = mapping.get("user2id")
    id2user = mapping.get("id2user")
    if not isinstance(user2id, dict) or not isinstance(id2user, list):
        raise LatteCacheContractError("invalid_user_mapping_shape", "mapping lacks user2id/id2user")
    sequences = read_json_object(all_item_seqs_path)
    rows: list[dict[str, Any]] = []
    for source_user_id in sorted(sequences):
        if source_user_id not in user2id or user2id[source_user_id] <= 0:
            raise LatteCacheContractError("unknown_source_user", f"unknown source user {source_user_id!r}")
        sequence = sequences[source_user_id]
        if not isinstance(sequence, list) or not sequence:
            raise LatteCacheContractError("invalid_item_sequence", f"user {source_user_id!r} has no item sequence")
        unknown = [str(value) for value in sequence if str(value) not in source_to_item]
        if unknown:
            raise LatteCacheContractError(
                "interaction_catalog_mismatch", f"user {source_user_id!r} references unknown items {unknown[:5]}"
            )
        user_token_id = int(user2id[source_user_id])
        if user_token_id >= len(id2user) or str(id2user[user_token_id]) != source_user_id:
            raise LatteCacheContractError("mapping_inverse_mismatch", f"user mapping disagrees for {source_user_id!r}")
        for position, source_item_value in enumerate(sequence):
            source_item_id = str(source_item_value)
            item = source_to_item[source_item_id]
            rows.append(
                {
                    "user_id": user_token_id - 1,
                    "source_user_id": source_user_id,
                    "latte_user_token_id": user_token_id,
                    "item_id": item.normalized_item_id,
                    "source_item_id": source_item_id,
                    "latte_item_token_id": item.latte_item_token_id,
                    "dataset": dataset,
                    "position": position,
                }
            )
    if not rows:
        raise LatteCacheContractError("empty_interactions", "all_item_seqs contains no interactions")
    out = pd.DataFrame(rows)
    validate_columns("interactions", out.columns)
    return out


def export_latte_trace(
    *,
    route_id: str,
    trace_id: str,
    split_id: str,
    cache: Mapping[str, Sequence[int]],
    normalized_item_ids: Mapping[str, int],
    beams: Sequence[Mapping[str, Any]],
    codebook_size: int,
    n_latent_tokens: int,
    aggregation_method: str,
) -> dict[str, Any]:
    """Export a deterministic Latte beam/aggregation trace.

    Each input beam supplies ``latent_token``, zero-based ``semantic_codes``,
    ``score`` (normalized log probability), and optional ``beam_id`` and
    ``parent_beam_id``.  Invalid paths remain in the trace with failure labels.
    """

    if aggregation_method not in {"agg_max", "agg_sum"}:
        raise LatteCacheContractError("invalid_aggregation_method", aggregation_method)
    if not cache:
        raise LatteCacheContractError("empty_sem_ids_cache", "trace cache cannot be empty")
    reverse = {tuple(int(v) for v in codes): source for source, codes in cache.items()}
    if len(reverse) != len(cache):
        raise LatteCacheContractError("semantic_id_collision", "cache is not conflict-free")

    rows: list[dict[str, Any]] = []
    valid_scores: dict[str, list[float]] = {}
    for index, beam in enumerate(beams):
        latent_token = int(beam["latent_token"])
        codes = tuple(int(value) for value in beam["semantic_codes"])
        failure_labels: list[str] = []
        if latent_token < 1 or latent_token > n_latent_tokens:
            failure_labels.append("invalid_latent_token")
        if len(codes) != len(next(iter(cache.values()))):
            failure_labels.append("wrong_sid_depth")
        if any(code < 0 or code >= codebook_size for code in codes):
            failure_labels.append("sid_code_out_of_range")
        source_item_id = reverse.get(codes)
        if source_item_id is None and not failure_labels:
            failure_labels.append("unresolved_semantic_id")
        score = float(beam["score"])
        valid = not failure_labels
        if valid and source_item_id is not None:
            valid_scores.setdefault(source_item_id, []).append(score)
        vocabulary_tokens = latte_vocabulary_tokens(codes, codebook_size, n_latent_tokens)
        prefix_states = [
            {
                "prefix_depth": depth,
                "latent_token": latent_token,
                "ordered_semantic_prefix": list(codes[:depth]),
                "ordered_model_vocabulary_prefix": list(vocabulary_tokens[:depth]),
            }
            for depth in range(len(codes) + 1)
        ]
        rows.append(
            {
                "beam_id": str(beam.get("beam_id", index)),
                "parent_beam_id": beam.get("parent_beam_id"),
                "latent_token": latent_token,
                "ordered_semantic_codes": list(codes),
                "ordered_model_vocabulary_tokens": list(vocabulary_tokens),
                "prefix_states": prefix_states,
                "score_normalized_log_probability": score,
                "source_item_id": source_item_id,
                "normalized_item_id": normalized_item_ids.get(source_item_id) if source_item_id else None,
                "valid": valid,
                "failure_labels": failure_labels,
            }
        )

    ranked: list[dict[str, Any]] = []
    for source_item_id, scores in valid_scores.items():
        aggregate = max(scores) if aggregation_method == "agg_max" else float(np.logaddexp.reduce(scores))
        ranked.append(
            {
                "source_item_id": source_item_id,
                "normalized_item_id": normalized_item_ids[source_item_id],
                "aggregated_score": aggregate,
                "supporting_beam_count": len(scores),
            }
        )
    ranked.sort(key=lambda row: (-float(row["aggregated_score"]), int(row["normalized_item_id"])))
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return {
        "schema": "sidscope.latte_autoregressive_trace.v1",
        "route_id": route_id,
        "trace_id": trace_id,
        "adapter_kind": "autoregressive_generator",
        "decode_state_kind": "latent_token_then_ordered_sid_prefix",
        "split_id": split_id,
        "aggregation_method": aggregation_method,
        "beams": rows,
        "ranked_items": ranked,
    }
