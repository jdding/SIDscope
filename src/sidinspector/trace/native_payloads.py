"""Registered method-native trace payload contracts for SIDScope 1.3."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from sidinspector.contracts import (
    METHOD_FAMILY_PAYLOAD_SCHEMAS,
    SHA256_PATTERN,
    verify_content_sha256,
)


PAYLOAD_REGISTRY_SCHEMA = "sidscope.trace_payload_registry.v1"
PAYLOAD_SCHEMA_REVISION = "1.0.0"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
FAMILY_SCHEMAS = METHOD_FAMILY_PAYLOAD_SCHEMAS


class NativePayloadValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class NativePayload:
    schema: str
    method_family: str
    payload_id: str
    content_sha256: str
    document: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.document))


@dataclass(frozen=True)
class NativePayloadDescriptor:
    method_family: str
    schema_id: str
    schema_revision: str
    schema_resource: str
    canonical_fixture: str
    negative_fixtures: tuple[Mapping[str, str], ...]


def _fail(code: str, detail: str) -> None:
    raise NativePayloadValidationError(code, detail)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", field)
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_count", field)
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("invalid_number", field)
    result = float(value)
    if not math.isfinite(result):
        _fail("invalid_number", field)
    return result


def _sequence(value: Any, field: str, *, nonempty: bool = False) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("invalid_type", field)
    if nonempty and not value:
        _fail("empty_collection", field)
    return value


def _exact(value: Any, fields: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("invalid_fields", field)
    return value


def _safe_relative_path(value: Any, field: str) -> str:
    path = _text(value, field)
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or path != pure.as_posix():
        _fail("unsafe_registry_path", f"{field}={path}")
    return path


def _ranked_topk(value: Any, field: str) -> None:
    rows = _sequence(value, field, nonempty=True)
    for index, row in enumerate(rows):
        row = _exact(row, {"rank", "token_id", "logprob"}, f"{field}[{index}]")
        if _integer(row["rank"], f"{field}[{index}].rank", 1) != index + 1:
            _fail("noncanonical_rank", field)
        _integer(row["token_id"], f"{field}[{index}].token_id")
        _number(row["logprob"], f"{field}[{index}].logprob")


def _resolution_events(value: Any, field: str) -> None:
    rows = _sequence(value, field)
    for index, row in enumerate(rows):
        row = _exact(
            row,
            {"raw_sid", "raw_valid", "resolved_normalized_item_id", "collision_count"},
            f"{field}[{index}]",
        )
        for token in _sequence(row["raw_sid"], f"{field}[{index}].raw_sid", nonempty=True):
            _integer(token, f"{field}[{index}].raw_sid[]")
        if not isinstance(row["raw_valid"], bool):
            _fail("invalid_boolean", f"{field}[{index}].raw_valid")
        resolved = row["resolved_normalized_item_id"]
        if resolved is not None:
            _integer(resolved, f"{field}[{index}].resolved_normalized_item_id")
        collision_count = _integer(row["collision_count"], f"{field}[{index}].collision_count")
        if (resolved is None) != (collision_count == 0):
            _fail("resolution_collision_mismatch", f"{field}[{index}]")


def _episode_end(row: Mapping[str, Any], field: str) -> None:
    termination = _text(row["termination_state"], f"{field}.termination_state")
    failure = row["failure_state"]
    if failure is not None:
        _text(failure, f"{field}.failure_state")
    if termination == "success" and failure is not None:
        _fail("termination_failure_mismatch", field)


def _base(value: Mapping[str, Any], family: str) -> tuple[str, Sequence[Any], str]:
    expected = {
        "schema", "schema_revision", "payload_id", "method_family", "episodes",
        "privacy", "content_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        _fail("payload_fields_mismatch", family)
    schema = FAMILY_SCHEMAS[family]
    if value["schema"] != schema or value["method_family"] != family:
        _fail("payload_family_mismatch", f"{value.get('schema')} / {value.get('method_family')}")
    if value["schema_revision"] != PAYLOAD_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value["schema_revision"]))
    payload_id = _text(value["payload_id"], "payload_id")
    if ID_PATTERN.fullmatch(payload_id) is None:
        _fail("invalid_payload_id", payload_id)
    episodes = _sequence(value["episodes"], "episodes", nonempty=True)
    episode_ids: list[str] = []
    for index, episode in enumerate(episodes):
        if not isinstance(episode, Mapping):
            _fail("invalid_type", f"episodes[{index}]")
        episode_ids.append(_text(episode.get("episode_id"), f"episodes[{index}].episode_id"))
    if len(episode_ids) != len(set(episode_ids)):
        _fail("duplicate_episode_id", str(episode_ids))
    privacy = _exact(
        value["privacy"],
        {"source_user_ids_exported", "source_item_ids_exported", "absolute_private_paths_exported"},
        "privacy",
    )
    if any(not isinstance(flag, bool) for flag in privacy.values()) or any(privacy.values()):
        _fail("privacy_boundary_violation", str(dict(privacy)))
    content_sha = value["content_sha256"]
    if not isinstance(content_sha, str) or SHA256_PATTERN.fullmatch(content_sha) is None:
        _fail("invalid_sha256", "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", payload_id)
    return payload_id, episodes, content_sha


def _validate_autoregressive(value: Mapping[str, Any]) -> NativePayload:
    payload_id, episodes, content_sha = _base(value, "autoregressive_prefix")
    for ei, episode in enumerate(episodes):
        episode = _exact(
            episode,
            {"episode_id", "beams", "resolution_events", "termination_state", "failure_state"},
            f"episodes[{ei}]",
        )
        _text(episode["episode_id"], f"episodes[{ei}].episode_id")
        known: set[str] = set()
        for bi, beam in enumerate(_sequence(episode["beams"], f"episodes[{ei}].beams", nonempty=True)):
            beam = _exact(beam, {"beam_id", "parent_beam_id", "steps", "retained"}, f"beam[{bi}]")
            beam_id = _text(beam["beam_id"], f"beam[{bi}].beam_id")
            if beam_id in known:
                _fail("duplicate_beam_id", beam_id)
            parent = beam["parent_beam_id"]
            if parent is not None and parent not in known:
                _fail("unknown_parent_beam", f"{beam_id}->{parent}")
            steps = _sequence(beam["steps"], f"beam[{bi}].steps", nonempty=True)
            previous_after: list[int] | None = None
            for si, step in enumerate(steps):
                step = _exact(step, {"step_index", "prefix_before", "topk", "selected_token_id", "prefix_after"}, f"step[{si}]")
                if _integer(step["step_index"], f"step[{si}].step_index") != si:
                    _fail("noncanonical_step_order", beam_id)
                before = list(_sequence(step["prefix_before"], "prefix_before"))
                after = list(_sequence(step["prefix_after"], "prefix_after", nonempty=True))
                selected = _integer(step["selected_token_id"], "selected_token_id")
                _ranked_topk(step["topk"], "topk")
                if previous_after is not None and before != previous_after:
                    _fail("prefix_chain_discontinuity", beam_id)
                if after != [*before, selected]:
                    _fail("prefix_transition_mismatch", beam_id)
                previous_after = after
            if not isinstance(beam["retained"], bool):
                _fail("invalid_boolean", f"beam[{bi}].retained")
            known.add(beam_id)
        _resolution_events(episode["resolution_events"], f"episodes[{ei}].resolution_events")
        _episode_end(episode, f"episodes[{ei}]")
    return NativePayload(value["schema"], value["method_family"], payload_id, content_sha, dict(value))


def _validate_parallel(value: Mapping[str, Any]) -> NativePayload:
    payload_id, episodes, content_sha = _base(value, "parallel_graph_token_set")
    for ei, episode in enumerate(episodes):
        episode = _exact(episode, {"episode_id", "attempts", "resolution_events", "termination_state", "failure_state"}, f"episodes[{ei}]")
        _text(episode["episode_id"], f"episodes[{ei}].episode_id")
        for ai, attempt in enumerate(_sequence(episode["attempts"], "attempts", nonempty=True)):
            if isinstance(attempt, Mapping) and "parent_beam_id" in attempt:
                _fail("synthetic_ancestry_forbidden", f"attempt[{ai}]")
            attempt = _exact(attempt, {"attempt_index", "parallel_position_scores", "retained_token_sets", "visited_item_nodes", "expanded_item_frontier"}, f"attempt[{ai}]")
            if _integer(attempt["attempt_index"], "attempt_index") != ai:
                _fail("noncanonical_attempt_order", str(ai))
            for pi, position in enumerate(_sequence(attempt["parallel_position_scores"], "parallel_position_scores", nonempty=True)):
                position = _exact(position, {"position", "topk"}, f"position[{pi}]")
                _integer(position["position"], f"position[{pi}].position")
                _ranked_topk(position["topk"], f"position[{pi}].topk")
            for token_set in _sequence(attempt["retained_token_sets"], "retained_token_sets", nonempty=True):
                for token in _sequence(token_set, "retained_token_set", nonempty=True):
                    _integer(token, "retained_token_set[]")
            for field in ("visited_item_nodes", "expanded_item_frontier"):
                for item in _sequence(attempt[field], field):
                    _integer(item, f"{field}[]")
        _resolution_events(episode["resolution_events"], "resolution_events")
        _episode_end(episode, f"episodes[{ei}]")
    return NativePayload(value["schema"], value["method_family"], payload_id, content_sha, dict(value))


def _validate_masked(value: Mapping[str, Any]) -> NativePayload:
    payload_id, episodes, content_sha = _base(value, "masked_diffusion")
    for ei, episode in enumerate(episodes):
        episode = _exact(episode, {"episode_id", "steps", "final_raw_tuples", "resolution_events", "termination_state", "failure_state"}, f"episodes[{ei}]")
        _text(episode["episode_id"], f"episodes[{ei}].episode_id")
        previous_after: list[int] | None = None
        for si, step in enumerate(_sequence(episode["steps"], "steps", nonempty=True)):
            step = _exact(step, {"step_index", "mask_positions_before", "mask_positions_after", "position_topk", "selected_positions", "selected_order", "retained_beams", "pruned_beams"}, f"step[{si}]")
            if _integer(step["step_index"], "step_index") != si:
                _fail("noncanonical_step_order", str(si))
            before = [_integer(item, "mask_positions_before[]") for item in _sequence(step["mask_positions_before"], "mask_positions_before")]
            after = [_integer(item, "mask_positions_after[]") for item in _sequence(step["mask_positions_after"], "mask_positions_after")]
            selected = [_integer(item, "selected_positions[]") for item in _sequence(step["selected_positions"], "selected_positions")]
            order = [_integer(item, "selected_order[]") for item in _sequence(step["selected_order"], "selected_order")]
            if any(len(items) != len(set(items)) for items in (before, after, selected, order)):
                _fail("duplicate_mask_position", f"step={si}")
            if previous_after is not None and before != previous_after:
                _fail("invalid_mask_transition", f"step={si}")
            if not set(after).issubset(before):
                _fail("invalid_mask_transition", f"step={si}")
            if set(before) - set(after) != set(selected) or set(order) != set(selected):
                _fail("invalid_unmask_decision", f"step={si}")
            for row in _sequence(step["position_topk"], "position_topk"):
                row = _exact(row, {"position", "topk"}, "position_topk[]")
                _integer(row["position"], "position_topk.position")
                _ranked_topk(row["topk"], "position_topk.topk")
            for field in ("retained_beams", "pruned_beams"):
                for beam_id in _sequence(step[field], field):
                    _text(beam_id, f"{field}[]")
            previous_after = after
        for raw_tuple in _sequence(episode["final_raw_tuples"], "final_raw_tuples", nonempty=True):
            for token in _sequence(raw_tuple, "final_raw_tuple", nonempty=True):
                _integer(token, "final_raw_tuple[]")
        _resolution_events(episode["resolution_events"], "resolution_events")
        _episode_end(episode, f"episodes[{ei}]")
    return NativePayload(value["schema"], value["method_family"], payload_id, content_sha, dict(value))


def _validate_retry(value: Mapping[str, Any]) -> NativePayload:
    payload_id, episodes, content_sha = _base(value, "latent_retry")
    for ei, episode in enumerate(episodes):
        episode = _exact(episode, {"episode_id", "retries", "resolution_events", "termination_state", "failure_state"}, f"episodes[{ei}]")
        _text(episode["episode_id"], f"episodes[{ei}].episode_id")
        for ri, retry in enumerate(_sequence(episode["retries"], "retries", nonempty=True)):
            retry = _exact(retry, {"retry_index", "latent_state_sha256", "beams", "accepted", "failure_state"}, f"retry[{ri}]")
            if _integer(retry["retry_index"], "retry_index") != ri:
                _fail("invalid_retry_order", str(ri))
            if not isinstance(retry["latent_state_sha256"], str) or SHA256_PATTERN.fullmatch(retry["latent_state_sha256"]) is None:
                _fail("invalid_sha256", "latent_state_sha256")
            for beam in _sequence(retry["beams"], "beams", nonempty=True):
                beam = _exact(beam, {"beam_id", "ordered_tokens", "score"}, "beam")
                _text(beam["beam_id"], "beam_id")
                for token in _sequence(beam["ordered_tokens"], "ordered_tokens", nonempty=True):
                    _integer(token, "ordered_tokens[]")
                _number(beam["score"], "beam.score")
            if not isinstance(retry["accepted"], bool):
                _fail("invalid_boolean", "retry.accepted")
            if retry["failure_state"] is not None:
                _text(retry["failure_state"], "retry.failure_state")
            if retry["accepted"] == (retry["failure_state"] is not None):
                _fail("retry_acceptance_failure_mismatch", f"retry[{ri}]")
        _resolution_events(episode["resolution_events"], "resolution_events")
        _episode_end(episode, f"episodes[{ei}]")
    return NativePayload(value["schema"], value["method_family"], payload_id, content_sha, dict(value))


def _validate_overlay(value: Mapping[str, Any]) -> NativePayload:
    payload_id, episodes, content_sha = _base(value, "decoder_overlay")
    for ei, episode in enumerate(episodes):
        episode = _exact(episode, {"episode_id", "base_ranked_items", "overlay_support", "fused_ranked_items", "resolution_events", "termination_state", "failure_state"}, f"episodes[{ei}]")
        _text(episode["episode_id"], f"episodes[{ei}].episode_id")
        ranked_item_ids: dict[str, set[int]] = {}
        for field in ("base_ranked_items", "fused_ranked_items"):
            seen: set[int] = set()
            for index, row in enumerate(_sequence(episode[field], field, nonempty=True)):
                row = _exact(row, {"rank", "normalized_item_id", "score"}, f"{field}[{index}]")
                if _integer(row["rank"], f"{field}.rank", 1) != index + 1:
                    _fail("noncanonical_rank", field)
                item_id = _integer(row["normalized_item_id"], f"{field}.normalized_item_id")
                if item_id in seen:
                    _fail("duplicate_ranked_item", field)
                seen.add(item_id)
                _number(row["score"], f"{field}.score")
            ranked_item_ids[field] = seen
        inserted = ranked_item_ids["fused_ranked_items"] - ranked_item_ids["base_ranked_items"]
        if inserted:
            _fail("provider_only_item_insertion", str(sorted(inserted)))
        for row in _sequence(episode["overlay_support"], "overlay_support"):
            row = _exact(row, {"normalized_item_id", "support_source", "support_score"}, "overlay_support[]")
            _integer(row["normalized_item_id"], "overlay_support.normalized_item_id")
            _text(row["support_source"], "overlay_support.support_source")
            _number(row["support_score"], "overlay_support.support_score")
        _resolution_events(episode["resolution_events"], "resolution_events")
        _episode_end(episode, f"episodes[{ei}]")
    return NativePayload(value["schema"], value["method_family"], payload_id, content_sha, dict(value))


VALIDATORS: Mapping[str, Callable[[Mapping[str, Any]], NativePayload]] = {
    FAMILY_SCHEMAS["autoregressive_prefix"]: _validate_autoregressive,
    FAMILY_SCHEMAS["parallel_graph_token_set"]: _validate_parallel,
    FAMILY_SCHEMAS["masked_diffusion"]: _validate_masked,
    FAMILY_SCHEMAS["latent_retry"]: _validate_retry,
    FAMILY_SCHEMAS["decoder_overlay"]: _validate_overlay,
}


def validate_native_payload(value: Mapping[str, Any]) -> NativePayload:
    schema = value.get("schema") if isinstance(value, Mapping) else None
    validator = VALIDATORS.get(str(schema))
    if validator is None:
        _fail("unregistered_payload_schema", str(schema))
    return validator(value)


def load_native_payload(path: Path) -> NativePayload:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("invalid_type", str(path))
    return validate_native_payload(value)


def validate_payload_binding(payload: NativePayload, *, schema_id: str, content_sha256: str) -> None:
    if payload.schema != schema_id or payload.content_sha256 != content_sha256:
        _fail("payload_binding_mismatch", f"{payload.schema}@{payload.content_sha256}")


def native_payload_registry_path() -> Path:
    return Path(resources.files("sidinspector.schemas").joinpath("trace_payload_registry.v1.json"))


def validate_native_payload_registry(
    value: Mapping[str, Any], *, repository_root: Path | None = None
) -> tuple[NativePayloadDescriptor, ...]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema", "schema_revision", "payload_contracts", "content_sha256"
    }:
        _fail("payload_registry_fields_mismatch", str(sorted(value) if isinstance(value, Mapping) else type(value).__name__))
    if value.get("schema") != PAYLOAD_REGISTRY_SCHEMA:
        _fail("payload_registry_schema_mismatch", str(value.get("schema")))
    if value.get("schema_revision") != PAYLOAD_SCHEMA_REVISION:
        _fail("payload_registry_revision_mismatch", str(value.get("schema_revision")))
    if not verify_content_sha256(value):
        _fail("payload_registry_hash_mismatch", "trace_payload_registry.v1.json")
    rows = value.get("payload_contracts")
    if not isinstance(rows, list) or len(rows) != len(FAMILY_SCHEMAS):
        _fail("payload_registry_count_mismatch", str(rows))
    result = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "method_family", "schema_id", "schema_revision", "schema_resource",
            "canonical_fixture", "negative_fixtures",
        }:
            _fail("payload_registry_row_mismatch", str(row))
        negatives = row["negative_fixtures"]
        if not isinstance(negatives, list):
            _fail("payload_registry_negative_mismatch", str(negatives))
        checked_negatives: list[Mapping[str, str]] = []
        for negative in negatives:
            if not isinstance(negative, Mapping) or set(negative) != {"path", "expected_failure"}:
                _fail("payload_registry_negative_mismatch", str(negative))
            checked_negatives.append(
                {
                    "path": _safe_relative_path(negative.get("path"), "negative_fixtures.path"),
                    "expected_failure": _text(negative.get("expected_failure"), "expected_failure"),
                }
            )
        negative_paths = [item["path"] for item in checked_negatives]
        if negative_paths != sorted(set(negative_paths)):
            _fail("noncanonical_payload_registry_negatives", str(negative_paths))
        descriptor = NativePayloadDescriptor(
            method_family=_text(row["method_family"], "method_family"),
            schema_id=_text(row["schema_id"], "schema_id"),
            schema_revision=_text(row["schema_revision"], "schema_revision"),
            schema_resource=_safe_relative_path(row["schema_resource"], "schema_resource"),
            canonical_fixture=_safe_relative_path(row["canonical_fixture"], "canonical_fixture"),
            negative_fixtures=tuple(checked_negatives),
        )
        if FAMILY_SCHEMAS.get(descriptor.method_family) != descriptor.schema_id:
            _fail("payload_registry_family_mismatch", descriptor.method_family)
        if descriptor.schema_revision != PAYLOAD_SCHEMA_REVISION:
            _fail("payload_registry_revision_mismatch", descriptor.method_family)
        if not descriptor.schema_resource.endswith(".schema.json"):
            _fail("payload_registry_resource_mismatch", descriptor.schema_resource)
        result.append(descriptor)
    if [item.method_family for item in result] != sorted(FAMILY_SCHEMAS):
        _fail("noncanonical_payload_registry_order", str([item.method_family for item in result]))
    if repository_root is not None:
        for descriptor in result:
            schema_path = repository_root / "src" / "sidinspector" / "schemas" / descriptor.schema_resource
            if not schema_path.is_file():
                _fail("missing_payload_registry_resource", descriptor.schema_resource)
            for relative in (
                descriptor.canonical_fixture,
                *(item["path"] for item in descriptor.negative_fixtures),
            ):
                if not (repository_root / relative).is_file():
                    _fail("missing_payload_registry_resource", relative)
    return tuple(result)


def load_native_payload_registry(
    *, repository_root: Path | None = None
) -> tuple[NativePayloadDescriptor, ...]:
    value = json.loads(native_payload_registry_path().read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("payload_registry_fields_mismatch", type(value).__name__)
    return validate_native_payload_registry(value, repository_root=repository_root)
