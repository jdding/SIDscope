"""DiffGRM masked-diffusion adapter contracts.

This module is a revision-bound interoperability layer for the official
DiffGRM implementation.  It does not vendor upstream code, checkpoints, data,
or embeddings.  The contract keeps DiffGRM's adaptive masked-state beam search
distinct from autoregressive prefix decoding and records raw beams before the
official legality filtering, de-duplication, and padding path.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


PREPARED_SCHEMA = "sidscope.diffgrm_prepared_dataset.v1"
SELECTION_SCHEMA = "sidscope.diffgrm_episode_selection.v1"
TRACE_SCHEMA = "sidscope.diffgrm_masked_trace_bundle.v1"
TRACE_SCHEMA_V2 = "sidscope.diffgrm_masked_trace_bundle.v2"
ADAPTER_VERSION = "sidscope.diffgrm_adapter.v1"
SOURCE_REVISION = "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c"
CANONICAL_GAP_BUCKETS = ("short", "30-90d", "90-180d", "180-365d", ">365d")
N_DIGIT = 4
CODEBOOK_SIZE = 256
PAD_TOKEN = 0
BOS_TOKEN = 1
EOS_TOKEN = 2
SID_OFFSET = 3
MASK_TOKEN = -1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_EXPORT_KEYS = {
    "source_item_id",
    "source_user_id",
    "raw_item_id",
    "raw_user_id",
    "user_id",
    "asin",
    "checkpoint_path",
    "source_path",
    "private_path",
}


class DiffGRMContractError(ValueError):
    """A typed DiffGRM contract failure."""

    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


@dataclass(frozen=True)
class DiffGRMCatalogItem:
    """One normalized item and its official four-code DiffGRM SID."""

    normalized_item_id: str
    semantic_codes: tuple[int, ...]
    model_vocabulary_tokens: tuple[int, ...]


def canonical_sha256(value: Any) -> str:
    """Hash JSON-compatible data with a stable serialization."""

    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_sha256(value: Any, field: str) -> str:
    text = str(value)
    if not _SHA256.fullmatch(text):
        raise DiffGRMContractError("invalid_sha256", f"{field} must be lowercase SHA-256")
    return text


def _reject_identity_and_private_path_leaks(value: Any, location: str = "bundle") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_EXPORT_KEYS:
                raise DiffGRMContractError(
                    "identity_or_private_path_leak", f"forbidden field {location}.{key}"
                )
            _reject_identity_and_private_path_leaks(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_identity_and_private_path_leaks(child, f"{location}[{index}]")
    elif isinstance(value, str) and value.startswith("/"):
        raise DiffGRMContractError(
            "identity_or_private_path_leak", f"absolute private path at {location}"
        )


def _validate_trained_bindings(bundle: Mapping[str, Any]) -> dict[str, Any]:
    schema = bundle.get("schema")
    source_revision = bundle.get("source_revision")
    if source_revision != SOURCE_REVISION:
        raise DiffGRMContractError(
            "source_revision_mismatch", "trace is not bound to the pinned DiffGRM revision"
        )
    if schema == TRACE_SCHEMA:
        return {
            "binding_level": "legacy_v1_contract_fixture",
            "source_revision": source_revision,
        }
    if schema != TRACE_SCHEMA_V2:
        raise DiffGRMContractError("trace_schema_mismatch", "unexpected trace schema")
    if bundle.get("evidence_kind") not in {
        "checkpoint_bound_trained_smoke",
        "checkpoint_bound_trained_diagnostic",
    }:
        raise DiffGRMContractError(
            "trained_evidence_kind_required", "v2 requires checkpoint-bound trained evidence"
        )
    configuration = bundle.get("configuration")
    if not isinstance(configuration, Mapping):
        raise DiffGRMContractError("missing_configuration", "configuration must be an object")
    seed = configuration.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise DiffGRMContractError("missing_training_seed", "v2 configuration requires an integer seed")
    evidence = bundle.get("evidence")
    if not isinstance(evidence, Mapping):
        raise DiffGRMContractError("missing_trained_bindings", "v2 evidence must be an object")
    if evidence.get("source_revision") != source_revision:
        raise DiffGRMContractError(
            "source_binding_mismatch", "evidence source revision differs from trace identity"
        )
    required_hashes = (
        "source_manifest_sha256",
        "configuration_sha256",
        "checkpoint_sha256",
        "training_manifest_sha256",
        "semantic_id_cache_sha256",
    )
    bindings = {"source_revision": source_revision, "seed": seed}
    for field in required_hashes:
        bindings[field] = _require_sha256(evidence.get(field), f"evidence.{field}")
    expected_configuration_sha256 = canonical_sha256(configuration)
    if bindings["configuration_sha256"] != expected_configuration_sha256:
        raise DiffGRMContractError(
            "configuration_binding_mismatch",
            "evidence configuration hash differs from the canonical configuration",
        )
    for field, value in evidence.items():
        if field.endswith("_sha256") and field not in required_hashes:
            _require_sha256(value, f"evidence.{field}")
    return {"binding_level": "checkpoint_bound_v2", **bindings}


def model_vocabulary_tokens(
    semantic_codes: Sequence[int],
    *,
    n_digit: int = N_DIGIT,
    codebook_size: int = CODEBOOK_SIZE,
) -> tuple[int, ...]:
    """Apply DiffGRM's position-disjoint SID token offsets."""

    codes = tuple(int(value) for value in semantic_codes)
    if len(codes) != n_digit:
        raise DiffGRMContractError(
            "wrong_semantic_code_count",
            f"expected {n_digit} semantic codes, observed {len(codes)}",
        )
    tokens: list[int] = []
    for position, code in enumerate(codes):
        if code < 0 or code >= codebook_size:
            raise DiffGRMContractError(
                "semantic_code_out_of_range",
                f"code {code} is outside [0, {codebook_size}) at position {position}",
            )
        tokens.append(SID_OFFSET + position * codebook_size + code)
    return tuple(tokens)


def validate_sid_compatibility(
    *,
    n_digit: int,
    codebook_size: int,
    pad_token: int,
    bos_token: int,
    eos_token: int,
    mask_token: int,
    sid_offset: int,
) -> dict[str, Any]:
    """Fail closed unless an external SID cache exactly matches DiffGRM."""

    observed = {
        "n_digit": int(n_digit),
        "codebook_size": int(codebook_size),
        "pad_token": int(pad_token),
        "bos_token": int(bos_token),
        "eos_token": int(eos_token),
        "mask_token": int(mask_token),
        "sid_offset": int(sid_offset),
    }
    expected = {
        "n_digit": N_DIGIT,
        "codebook_size": CODEBOOK_SIZE,
        "pad_token": PAD_TOKEN,
        "bos_token": BOS_TOKEN,
        "eos_token": EOS_TOKEN,
        "mask_token": MASK_TOKEN,
        "sid_offset": SID_OFFSET,
    }
    mismatches = {
        key: {"expected": expected[key], "observed": observed[key]}
        for key in expected
        if expected[key] != observed[key]
    }
    if mismatches:
        raise DiffGRMContractError(
            "incompatible_sid_contract",
            "DiffGRM SID identity mismatch: " + json.dumps(mismatches, sort_keys=True),
        )
    return {"status": "pass", "contract": expected}


def validate_prepared_dataset(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the dataset-parameterized DiffGRM prepared-data contract."""

    if manifest.get("schema") != PREPARED_SCHEMA:
        raise DiffGRMContractError("prepared_schema_mismatch", "unexpected prepared schema")
    if manifest.get("route_id") != "diffgrm_www2026":
        raise DiffGRMContractError("route_mismatch", "prepared route must be diffgrm_www2026")

    sid = manifest.get("sid_contract", {})
    validate_sid_compatibility(
        n_digit=sid.get("n_digit"),
        codebook_size=sid.get("codebook_size"),
        pad_token=sid.get("pad_token"),
        bos_token=sid.get("bos_token"),
        eos_token=sid.get("eos_token"),
        mask_token=sid.get("mask_token"),
        sid_offset=sid.get("sid_offset"),
    )
    if sid.get("quantizer") != "opq_pq" or sid.get("index_factory") != "OPQ4,IVF1,PQ4x8":
        raise DiffGRMContractError(
            "unsupported_sid_quantizer",
            "the formal adapter requires official OPQ4,IVF1,PQ4x8 identity",
        )
    if sid.get("dedup_semantics") != "preserve_all_item_collisions":
        raise DiffGRMContractError(
            "collision_semantics_mismatch", "prepared data must preserve all SID collisions"
        )

    split_hashes = manifest.get("split_sha256", {})
    for split in ("train", "validation", "test"):
        _require_sha256(split_hashes.get(split), f"split_sha256.{split}")
    _require_sha256(manifest.get("train_observed_catalog_sha256"), "catalog hash")
    _require_sha256(manifest.get("canonical_target_universe_sha256"), "target universe hash")

    catalog: list[DiffGRMCatalogItem] = []
    seen: set[str] = set()
    for raw in manifest.get("catalog", []):
        normalized = str(raw.get("normalized_item_id"))
        if normalized in seen:
            raise DiffGRMContractError(
                "duplicate_normalized_item", f"duplicate item {normalized!r}"
            )
        codes = tuple(int(value) for value in raw.get("semantic_codes", []))
        tokens = model_vocabulary_tokens(codes)
        declared_tokens = tuple(int(value) for value in raw.get("model_vocabulary_tokens", []))
        if declared_tokens != tokens:
            raise DiffGRMContractError(
                "model_token_offset_mismatch", f"model tokens disagree for item {normalized!r}"
            )
        catalog.append(DiffGRMCatalogItem(normalized, codes, tokens))
        seen.add(normalized)
    if not catalog:
        raise DiffGRMContractError("empty_catalog", "prepared catalog cannot be empty")
    if int(manifest.get("train_observed_catalog_count", -1)) != len(catalog):
        raise DiffGRMContractError(
            "catalog_count_mismatch", "catalog count does not match catalog rows"
        )
    if manifest.get("dormancy_fields_in_generator_input") is not False:
        raise DiffGRMContractError(
            "dormancy_input_leakage", "dormancy bucket and label must remain evaluator-only"
        )
    if manifest.get("source_item_ids_exported") is not False:
        raise DiffGRMContractError(
            "source_identity_exposure", "prepared public contract must be pseudonymous"
        )

    collisions: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for item in catalog:
        collisions[item.semantic_codes].append(item.normalized_item_id)
    return {
        "schema": PREPARED_SCHEMA,
        "status": "pass",
        "catalog": catalog,
        "catalog_collision_count": sum(1 for values in collisions.values() if len(values) > 1),
        "prepared_dataset_contract_sha256": canonical_sha256(manifest),
    }


def validate_episode_selection(
    selection: Mapping[str, Any], prepared: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate ordered, explicit episode selection independently of row order."""

    if selection.get("schema") != SELECTION_SCHEMA:
        raise DiffGRMContractError("selection_schema_mismatch", "unexpected selection schema")
    if selection.get("prepared_dataset_contract_sha256") != canonical_sha256(prepared):
        raise DiffGRMContractError(
            "prepared_binding_mismatch", "selection is not bound to the prepared contract"
        )
    rows = selection.get("episodes", [])
    if not rows:
        raise DiffGRMContractError("empty_episode_selection", "selection cannot be empty")
    episode_ids: set[str] = set()
    ordinals: list[int] = []
    catalog_ids = {str(row["normalized_item_id"]) for row in prepared["catalog"]}
    episode_index: dict[str, Mapping[str, Any]] = {}
    for indexed in prepared.get("episode_index", []):
        indexed_id = str(indexed.get("episode_id"))
        if indexed_id in episode_index:
            raise DiffGRMContractError(
                "duplicate_prepared_episode", f"duplicate prepared episode {indexed_id!r}"
            )
        episode_index[indexed_id] = indexed
    if not episode_index:
        raise DiffGRMContractError(
            "missing_prepared_episode_index", "prepared contract needs an episode index"
        )
    for row in rows:
        episode_id = str(row.get("episode_id"))
        if episode_id in episode_ids:
            raise DiffGRMContractError(
                "duplicate_episode_selection", f"duplicate episode {episode_id!r}"
            )
        episode_ids.add(episode_id)
        ordinals.append(int(row.get("selection_ordinal", -1)))
        if episode_id not in episode_index:
            raise DiffGRMContractError(
                "missing_selected_episode", f"episode {episode_id!r} is absent from prepared data"
            )
        indexed = episode_index[episode_id]
        if row.get("split") != "test" or indexed.get("split") != "test":
            raise DiffGRMContractError(
                "selected_episode_out_of_split", f"episode {episode_id!r} is not in test"
            )
        target = str(row.get("target_normalized_item_id"))
        if target != str(indexed.get("target_normalized_item_id")):
            raise DiffGRMContractError(
                "selection_target_mismatch", f"target mismatch for {episode_id!r}"
            )
        if indexed.get("catalog_reachable") is not True or target not in catalog_ids:
            raise DiffGRMContractError(
                "selection_target_outside_catalog", f"target outside catalog for {episode_id!r}"
            )
        if row.get("generator_input_contains_bucket_or_label") is not False:
            raise DiffGRMContractError(
                "dormancy_input_leakage", f"selection {episode_id!r} leaks evaluator labels"
            )
    if ordinals != list(range(1, len(rows) + 1)):
        raise DiffGRMContractError(
            "noncontiguous_selection_order", "selection ordinals must be contiguous from one"
        )
    return {
        "schema": SELECTION_SCHEMA,
        "status": "pass",
        "episode_count": len(rows),
        "episode_selection_manifest_sha256": canonical_sha256(selection),
    }


def _masked_positions(state: Sequence[int]) -> list[int]:
    return [position for position, token in enumerate(state) if int(token) == MASK_TOKEN]


def _validate_topk(rows: Sequence[Mapping[str, Any]], masked_positions: set[int]) -> None:
    covered: set[int] = set()
    for row in rows:
        position = int(row.get("position", -1))
        if position not in masked_positions:
            raise DiffGRMContractError(
                "topk_for_unmasked_position", f"top-k exported for unmasked position {position}"
            )
        covered.add(position)
        candidates = row.get("candidates", [])
        if not candidates:
            raise DiffGRMContractError("empty_position_topk", "position top-k cannot be empty")
        previous = math.inf
        for candidate in candidates:
            token = int(candidate.get("codebook_token_id", -1))
            logprob = float(candidate.get("log_probability"))
            if token < 0 or token >= CODEBOOK_SIZE:
                raise DiffGRMContractError(
                    "semantic_code_out_of_range", "top-k token is outside the codebook"
                )
            if logprob > previous:
                raise DiffGRMContractError(
                    "unsorted_position_topk", "position top-k must be descending"
                )
            previous = logprob
    if covered != masked_positions:
        raise DiffGRMContractError(
            "incomplete_position_topk", "top-k must cover every currently masked position"
        )


def _catalog_resolution(
    codes: Sequence[int], catalog: Sequence[DiffGRMCatalogItem]
) -> dict[str, Any]:
    values = tuple(int(value) for value in codes)
    matches = sorted(
        item.normalized_item_id for item in catalog if item.semantic_codes == values
    )
    return {
        "raw_validity": "catalog_exact_match" if matches else "invalid_raw_tuple",
        "resolved_normalized_item_ids": matches,
        "resolution_state": (
            "unresolved"
            if not matches
            else "unique"
            if len(matches) == 1
            else "collision"
        ),
        "projection_state": "projection_not_applicable",
    }


def validate_trace_bundle(
    bundle: Mapping[str, Any],
    prepared: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate native masked-state ancestry and exact item resolution."""

    prepared_result = validate_prepared_dataset(prepared)
    selection_result = validate_episode_selection(selection, prepared)
    _reject_identity_and_private_path_leaks(bundle)
    bindings = _validate_trained_bindings(bundle)
    if bundle.get("adapter_version") != ADAPTER_VERSION:
        raise DiffGRMContractError("adapter_version_mismatch", "unexpected adapter version")
    if bundle.get("route_id") != "diffgrm_www2026":
        raise DiffGRMContractError("route_mismatch", "trace route must be diffgrm_www2026")
    if bundle.get("prepared_dataset_contract_sha256") != canonical_sha256(prepared):
        raise DiffGRMContractError("prepared_binding_mismatch", "trace prepared binding mismatch")
    if bundle.get("episode_selection_manifest_sha256") != canonical_sha256(selection):
        raise DiffGRMContractError("selection_binding_mismatch", "trace selection binding mismatch")
    if "prefix_depth" in json.dumps(bundle, sort_keys=True):
        raise DiffGRMContractError(
            "autoregressive_field_forbidden", "DiffGRM traces cannot claim prefix depth"
        )
    ranking = bundle.get("ranking_diagnostic", {})
    cutoff = int(ranking.get("evaluation_cutoff", -1))
    depth = int(ranking.get("published_rank_depth", -1))
    if cutoff != 10 or depth < cutoff or depth > 256:
        raise DiffGRMContractError(
            "invalid_ranking_depth", "evaluation cutoff must be 10 and publication depth 10..256"
        )

    catalog: list[DiffGRMCatalogItem] = prepared_result["catalog"]
    selected_ids = [str(row["episode_id"]) for row in selection["episodes"]]
    episodes = bundle.get("episodes", [])
    if [str(row.get("episode_id")) for row in episodes] != selected_ids:
        raise DiffGRMContractError(
            "episode_order_mismatch", "trace episodes must follow explicit selection order"
        )

    hit_count = 0
    ndcg_sum = 0.0
    exact_rank_count = 0
    censored_count = 0
    invalid_raw_count = 0
    duplicate_count = 0
    unique_candidate_count = 0
    generation_search_miss_count = 0
    resolution_loss_count = 0
    ranking_conversion_miss_count = 0
    nfe_total = 0
    forward_calls_total = 0
    logits_total = 0
    expansion_total = 0
    visited_total = 0
    latency_total = 0.0
    five_bucket_counts = {bucket: 0 for bucket in CANONICAL_GAP_BUCKETS}
    bucket_hits = {bucket: 0 for bucket in CANONICAL_GAP_BUCKETS}
    bucket_ndcg = {bucket: 0.0 for bucket in CANONICAL_GAP_BUCKETS}
    for episode, selected in zip(episodes, selection["episodes"]):
        if str(episode.get("target_normalized_item_id")) != str(
            selected.get("target_normalized_item_id")
        ):
            raise DiffGRMContractError(
                "episode_target_mismatch", "trace target differs from selected target"
            )
        gap_bucket = str(selected.get("gap_bucket"))
        if str(episode.get("gap_bucket")) != gap_bucket:
            raise DiffGRMContractError(
                "episode_bucket_mismatch", "trace bucket differs from evaluator-side selection"
            )
        if bundle.get("schema") == TRACE_SCHEMA_V2 and gap_bucket not in five_bucket_counts:
            raise DiffGRMContractError(
                "unknown_gap_bucket", f"unsupported natural gap bucket {gap_bucket!r}"
            )
        if gap_bucket in five_bucket_counts:
            five_bucket_counts[gap_bucket] += 1
        noising_views = episode.get("forward_noising_ocn", [])
        if len(noising_views) != N_DIGIT:
            raise DiffGRMContractError(
                "incomplete_forward_noising_trace",
                f"expected {N_DIGIT} forward-noising views",
            )
        previous_timestep = -math.inf
        for expected_view, view in enumerate(noising_views, start=1):
            if int(view.get("view_ordinal", -1)) != expected_view:
                raise DiffGRMContractError(
                    "noncontiguous_noising_view", "noising views must start at one"
                )
            timestep = float(view.get("timestep"))
            if timestep <= previous_timestep or timestep <= 0.0 or timestep > 1.0:
                raise DiffGRMContractError(
                    "invalid_noising_timestep", "noising timesteps must increase within (0, 1]"
                )
            previous_timestep = timestep
            positions = [int(value) for value in view.get("mask_positions", [])]
            weights = [float(value) for value in view.get("mask_weights", [])]
            if not positions or len(weights) != N_DIGIT:
                raise DiffGRMContractError(
                    "invalid_noising_mask", "noising view needs positions and four weights"
                )
            if any(weight < 0.0 or weight > 1.0 for weight in weights):
                raise DiffGRMContractError(
                    "invalid_noising_weight", "mask weights must lie within [0, 1]"
                )
            weighted_positions = {
                index for index, weight in enumerate(weights) if weight > 0.0
            }
            if weighted_positions != set(positions):
                raise DiffGRMContractError(
                    "noising_weight_mismatch", "mask weights disagree with masked positions"
                )
        attempts = episode.get("attempts", [])
        if not attempts:
            raise DiffGRMContractError("missing_attempt", "every episode needs an attempt")
        target_generated_from_raw = False
        for attempt in attempts:
            active: dict[str, tuple[int, ...]] = {
                "root": tuple([MASK_TOKEN] * N_DIGIT)
            }
            previous_visited = 0
            for expected_step, step in enumerate(attempt.get("steps", []), start=1):
                if int(step.get("denoising_step", -1)) != expected_step:
                    raise DiffGRMContractError(
                        "noncontiguous_denoising_step", "denoising steps must start at one"
                    )
                if int(step.get("nfe", -1)) != 1:
                    raise DiffGRMContractError("invalid_nfe", "each fixture step must bind one NFE")
                expansions = step.get("expanded_candidates", [])
                if int(step.get("candidate_expansion_count", -1)) != len(expansions):
                    raise DiffGRMContractError(
                        "candidate_expansion_count_mismatch",
                        "declared candidate expansion count differs from trace rows",
                    )
                forward_calls = int(step.get("forward_calls", -1))
                logits_evaluated = int(step.get("logits_evaluated", -1))
                visited_states = int(step.get("visited_state_count", -1))
                if forward_calls < 1 or logits_evaluated < 0:
                    raise DiffGRMContractError(
                        "invalid_compute_count", "forward calls and logits must be nonnegative"
                    )
                if visited_states <= previous_visited:
                    raise DiffGRMContractError(
                        "nonmonotonic_visited_state_count", "visited state count must increase"
                    )
                previous_visited = visited_states
                nfe_total += int(step["nfe"])
                forward_calls_total += forward_calls
                logits_total += logits_evaluated
                expansion_total += len(expansions)
                retained_ids = [str(value) for value in step.get("retained_beam_ids", [])]
                observed_retained: list[str] = []
                next_active: dict[str, tuple[int, ...]] = {}
                parents_with_topk: set[str] = set()
                for expansion in expansions:
                    parent_id = str(expansion.get("parent_beam_id"))
                    beam_id = str(expansion.get("beam_id"))
                    if parent_id not in active:
                        raise DiffGRMContractError(
                            "unknown_parent_beam", f"unknown parent {parent_id!r}"
                        )
                    pre = tuple(int(value) for value in expansion.get("pre_codes", []))
                    post = tuple(int(value) for value in expansion.get("post_codes", []))
                    if pre != active[parent_id] or len(post) != N_DIGIT:
                        raise DiffGRMContractError(
                            "parent_state_mismatch", f"beam {beam_id!r} state disagrees with parent"
                        )
                    masked = set(_masked_positions(pre))
                    position = int(expansion.get("selected_unmask_position", -1))
                    token = int(expansion.get("selected_codebook_token_id", -1))
                    if position not in masked:
                        raise DiffGRMContractError(
                            "selected_position_not_masked", f"position {position} was not masked"
                        )
                    if token < 0 or token >= CODEBOOK_SIZE:
                        raise DiffGRMContractError(
                            "semantic_code_out_of_range", "selected token outside codebook"
                        )
                    expected_post = list(pre)
                    expected_post[position] = token
                    if tuple(expected_post) != post:
                        raise DiffGRMContractError(
                            "post_state_mismatch", f"beam {beam_id!r} changed more than one position"
                        )
                    if expansion.get("masked_positions_before") != sorted(masked):
                        raise DiffGRMContractError(
                            "masked_positions_mismatch", "masked positions before are inconsistent"
                        )
                    if expansion.get("masked_positions_after") != _masked_positions(post):
                        raise DiffGRMContractError(
                            "masked_positions_mismatch", "masked positions after are inconsistent"
                        )
                    _validate_topk(expansion.get("per_position_topk", []), masked)
                    selected_candidates = next(
                        (
                            row.get("candidates", [])
                            for row in expansion.get("per_position_topk", [])
                            if int(row.get("position", -1)) == position
                        ),
                        [],
                    )
                    selected_evidence = next(
                        (
                            candidate
                            for candidate in selected_candidates
                            if int(candidate.get("codebook_token_id", -1)) == token
                        ),
                        None,
                    )
                    if selected_evidence is None or not math.isclose(
                        float(selected_evidence.get("log_probability")),
                        float(expansion.get("selected_log_probability")),
                        abs_tol=1e-12,
                    ):
                        raise DiffGRMContractError(
                            "selected_token_missing_topk_evidence",
                            f"selected token lacks matching top-k evidence for {beam_id!r}",
                        )
                    parents_with_topk.add(parent_id)
                    if expansion.get("retained") is True:
                        if beam_id in next_active:
                            raise DiffGRMContractError(
                                "duplicate_retained_beam", f"duplicate retained beam {beam_id!r}"
                            )
                        next_active[beam_id] = post
                        observed_retained.append(beam_id)
                    elif expansion.get("prune_reason") != "beam_score_pruned":
                        raise DiffGRMContractError(
                            "missing_prune_reason", "pruned candidate needs beam_score_pruned"
                        )
                if set(parents_with_topk) != set(active):
                    raise DiffGRMContractError(
                        "missing_parent_expansion", "every active beam needs an expansion record"
                    )
                if observed_retained != retained_ids:
                    raise DiffGRMContractError(
                        "retained_beam_list_mismatch", "retained IDs disagree with candidates"
                    )
                active = next_active
            if len(attempt.get("steps", [])) != N_DIGIT:
                raise DiffGRMContractError(
                    "wrong_denoising_step_count", f"DiffGRM requires {N_DIGIT} steps"
                )

            raw_beams = attempt.get("raw_final_beams", [])
            if not raw_beams:
                raise DiffGRMContractError("missing_raw_frontier", "raw final frontier is required")
            visited_total += previous_visited
            seen_codes: set[tuple[int, ...]] = set()
            for ordinal, raw in enumerate(raw_beams, start=1):
                if int(raw.get("raw_rank", -1)) != ordinal:
                    raise DiffGRMContractError(
                        "noncontiguous_raw_rank", "raw ranks must be contiguous"
                    )
                beam_id = str(raw.get("beam_id"))
                codes = tuple(int(value) for value in raw.get("semantic_codes", []))
                if beam_id not in active or active[beam_id] != codes or MASK_TOKEN in codes:
                    raise DiffGRMContractError(
                        "raw_frontier_state_mismatch", "raw frontier does not match final beams"
                    )
                expected_resolution = _catalog_resolution(codes, catalog)
                for field, expected in expected_resolution.items():
                    if raw.get(field) != expected:
                        raise DiffGRMContractError(
                            "resolution_claim_mismatch", f"unsupported {field} claim for {beam_id!r}"
                        )
                is_duplicate = codes in seen_codes
                if raw.get("raw_duplicate") is not is_duplicate:
                    raise DiffGRMContractError(
                        "duplicate_claim_mismatch", f"raw duplicate claim mismatch for {beam_id!r}"
                    )
                duplicate_count += int(is_duplicate)
                unique_candidate_count += int(not is_duplicate)
                seen_codes.add(codes)
                if expected_resolution["raw_validity"] == "invalid_raw_tuple":
                    invalid_raw_count += 1
                    if raw.get("raw_generation_success") is not False:
                        raise DiffGRMContractError(
                            "invalid_raw_marked_success", "invalid tuple cannot be generation success"
                        )
                elif raw.get("raw_generation_success") is not True:
                    raise DiffGRMContractError(
                        "valid_raw_marked_failure", "catalog-exact raw tuple must be generation success"
                    )
                if str(episode.get("target_normalized_item_id")) in expected_resolution[
                    "resolved_normalized_item_ids"
                ]:
                    target_generated_from_raw = True

        ranked = episode.get("ranked_items", [])
        if len(ranked) > depth:
            raise DiffGRMContractError(
                "rank_depth_overflow", "ranked items exceed published depth"
            )
        for expected_rank, row in enumerate(ranked, start=1):
            if int(row.get("rank", -1)) != expected_rank:
                raise DiffGRMContractError("noncontiguous_rank", "item ranks must be contiguous")
        target = str(episode.get("target_normalized_item_id"))
        observed_rank = next(
            (int(row["rank"]) for row in ranked if str(row["normalized_item_id"]) == target),
            None,
        )
        claimed_rank = episode.get("target_rank")
        claimed_state = episode.get("target_rank_state")
        if observed_rank is None:
            if claimed_rank is not None or claimed_state != "right_censored_beyond_published_depth":
                raise DiffGRMContractError(
                    "unsupported_exact_rank_claim", "absent target must be typed right-censored"
                )
            censored_count += 1
        else:
            if claimed_rank != observed_rank or claimed_state != "observed_exact":
                raise DiffGRMContractError(
                    "unsupported_exact_rank_claim", "target rank lacks ordered row support"
                )
            exact_rank_count += 1
            if observed_rank <= cutoff:
                hit_count += 1
                ndcg_sum += 1.0 / math.log2(observed_rank + 1)
                if gap_bucket in bucket_hits:
                    bucket_hits[gap_bucket] += 1
                    bucket_ndcg[gap_bucket] += 1.0 / math.log2(observed_rank + 1)

        target_generated_claim = episode.get("target_generated_raw")
        target_resolved_claim = episode.get("target_resolved")
        if target_generated_claim is not target_generated_from_raw:
            raise DiffGRMContractError(
                "target_generation_claim_mismatch",
                "target_generated_raw differs from raw frontier resolution",
            )
        if target_resolved_claim is not target_generated_from_raw:
            raise DiffGRMContractError(
                "target_resolution_claim_mismatch",
                "exact SID lookup requires target_resolved to match raw target presence",
            )
        generation_search_miss_count += int(not target_generated_from_raw)
        resolution_loss_count += int(target_generated_from_raw and not target_resolved_claim)
        ranking_conversion_miss_count += int(
            bool(target_resolved_claim) and (observed_rank is None or observed_rank > cutoff)
        )
        latency = float(episode.get("latency_ms"))
        if not math.isfinite(latency) or latency < 0.0:
            raise DiffGRMContractError("invalid_latency", "episode latency must be finite")
        latency_total += latency

    episode_count = len(episodes)
    expected_hit = hit_count / episode_count
    expected_ndcg = ndcg_sum / episode_count
    summary = bundle.get("summary", {})
    if not math.isclose(float(summary.get("hit_at_10")), expected_hit, abs_tol=1e-12):
        raise DiffGRMContractError("metric_mismatch", "Hit@10 does not match ranked rows")
    if not math.isclose(float(summary.get("ndcg_at_10")), expected_ndcg, abs_tol=1e-12):
        raise DiffGRMContractError("metric_mismatch", "NDCG@10 does not match ranked rows")
    if summary.get("recall_at_10_semantics") != "single_target_hit_at_10_alias":
        raise DiffGRMContractError(
            "recall_alias_mismatch", "single-target Recall@10 must be labeled as Hit@10 alias"
        )
    computed_summary = {
        "target_support_count": episode_count,
        "generation_search_miss_count": generation_search_miss_count,
        "resolution_loss_count": resolution_loss_count,
        "ranking_conversion_miss_count": ranking_conversion_miss_count,
        "unique_candidate_count": unique_candidate_count,
        "duplicate_candidate_count": duplicate_count,
        "nfe": nfe_total,
        "forward_calls": forward_calls_total,
        "logits_evaluated": logits_total,
        "candidate_expansion_count": expansion_total,
        "visited_state_count": visited_total,
    }
    if bundle.get("schema") == TRACE_SCHEMA_V2:
        for field, expected in computed_summary.items():
            if summary.get(field) != expected:
                raise DiffGRMContractError(
                    "summary_count_mismatch", f"summary.{field} differs from trace rows"
                )

    per_bucket = {}
    for bucket in CANONICAL_GAP_BUCKETS:
        count = five_bucket_counts[bucket]
        per_bucket[bucket] = {
            "episode_count": count,
            "hit_at_10": bucket_hits[bucket] / count if count else None,
            "ndcg_at_10": bucket_ndcg[bucket] / count if count else None,
        }

    return {
        "schema": "sidscope.diffgrm_trained_trace_verification.v1",
        "status": "pass",
        "route_id": "diffgrm_www2026",
        "adapter_version": ADAPTER_VERSION,
        "episode_count": episode_count,
        "prepared_dataset_contract_sha256": prepared_result[
            "prepared_dataset_contract_sha256"
        ],
        "episode_selection_manifest_sha256": selection_result[
            "episode_selection_manifest_sha256"
        ],
        "catalog_collision_count": prepared_result["catalog_collision_count"],
        "exact_target_rank_count": exact_rank_count,
        "right_censored_target_rank_count": censored_count,
        "invalid_raw_tuple_count": invalid_raw_count,
        "raw_duplicate_count": duplicate_count,
        "hit_at_10": expected_hit,
        "ndcg_at_10": expected_ndcg,
        "five_bucket_counts": five_bucket_counts,
        "per_bucket": per_bucket,
        "bindings": bindings,
        "resolution_summary": {
            "catalog_collision_count": prepared_result["catalog_collision_count"],
            "invalid_raw_tuple_count": invalid_raw_count,
            "unique_raw_tuple_count": unique_candidate_count,
            "duplicate_raw_tuple_count": duplicate_count,
            "generation_search_miss_count": generation_search_miss_count,
            "resolution_loss_count": resolution_loss_count,
            "ranking_conversion_miss_count": ranking_conversion_miss_count,
        },
        "compute_summary": {
            "nfe": nfe_total,
            "forward_calls": forward_calls_total,
            "logits_evaluated": logits_total,
            "candidate_expansion_count": expansion_total,
            "visited_state_count": visited_total,
            "latency_ms": latency_total,
        },
        "projection_semantics": "projection_not_applicable",
    }


__all__ = [
    "ADAPTER_VERSION",
    "BOS_TOKEN",
    "CODEBOOK_SIZE",
    "DiffGRMCatalogItem",
    "DiffGRMContractError",
    "EOS_TOKEN",
    "MASK_TOKEN",
    "N_DIGIT",
    "PAD_TOKEN",
    "PREPARED_SCHEMA",
    "SELECTION_SCHEMA",
    "SID_OFFSET",
    "TRACE_SCHEMA",
    "TRACE_SCHEMA_V2",
    "SOURCE_REVISION",
    "CANONICAL_GAP_BUCKETS",
    "canonical_sha256",
    "model_vocabulary_tokens",
    "validate_episode_selection",
    "validate_prepared_dataset",
    "validate_sid_compatibility",
    "validate_trace_bundle",
]
