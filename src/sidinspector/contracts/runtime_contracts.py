"""Canonical EpisodeSelection, RunIdentity, CheckpointBinding, and TraceEnvelope."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Sequence

from .hashing import SHA256_PATTERN, verify_content_sha256


EPISODE_SELECTION_SCHEMA = "sidscope.episode_selection.v1"
RUN_IDENTITY_SCHEMA = "sidscope.run_identity.v1"
CHECKPOINT_BINDING_SCHEMA = "sidscope.checkpoint_binding.v1"
TRACE_ENVELOPE_SCHEMA = "sidscope.trace_envelope.v1"
RUNTIME_SCHEMA_REVISION = "1.0.0"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
METHOD_FAMILIES = frozenset(
    {
        "autoregressive_prefix",
        "parallel_graph_token_set",
        "masked_diffusion",
        "latent_retry",
        "decoder_overlay",
    }
)
RANK_STATES = frozenset({"exact", "right_censored", "not_applicable"})
RUN_KINDS = frozenset({"training", "evaluation", "trace_export", "fixture"})


class RuntimeContractValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class RuntimeContract:
    schema: str
    schema_revision: str
    artifact_id: str
    content_sha256: str
    document: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.document))


def _fail(code: str, detail: str) -> None:
    raise RuntimeContractValidationError(code, detail)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be a non-empty string")
    return value


def _sha(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def _count(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_count", f"{field} must be integer >= {minimum}")
    return value


def _nonnegative_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("invalid_number", f"{field} must be a finite number >= 0")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        _fail("invalid_number", f"{field} must be a finite number >= 0")
    return number


def _object(parent: Mapping[str, Any], key: str, fields: set[str]) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{key} must be an object")
    if set(value) != fields:
        _fail("invalid_fields", f"{key} fields differ: {sorted(set(value) ^ fields)}")
    return value


def _binding(parent: Mapping[str, Any], key: str, expected_schema: str) -> Mapping[str, Any]:
    value = _object(parent, key, {"schema_id", "schema_revision", "content_sha256"})
    if value.get("schema_id") != expected_schema:
        _fail("dependency_schema_mismatch", f"{key}={value.get('schema_id')}")
    if value.get("schema_revision") != RUNTIME_SCHEMA_REVISION:
        _fail("dependency_revision_mismatch", key)
    _sha(value.get("content_sha256"), f"{key}.content_sha256")
    return value


def _producer(value: Mapping[str, Any]) -> None:
    producer = _object(value, "producer", {"name", "version"})
    _text(producer.get("name"), "producer.name")
    _text(producer.get("version"), "producer.version")


def _base(
    value: Mapping[str, Any],
    *,
    schema: str,
    id_field: str,
    fields: set[str],
) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        _fail("invalid_type", "contract must be an object")
    if set(value) != fields:
        unknown = sorted(set(value) - fields)
        missing = sorted(fields - set(value))
        _fail("contract_fields_mismatch", f"unknown={unknown}, missing={missing}")
    if value.get("schema") != schema:
        _fail("schema_mismatch", f"expected {schema}")
    if value.get("schema_revision") != RUNTIME_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    artifact_id = _text(value.get(id_field), id_field)
    if ID_PATTERN.fullmatch(artifact_id) is None:
        _fail("invalid_artifact_id", artifact_id)
    _producer(value)
    content_sha256 = _sha(value.get("content_sha256"), "content_sha256") or ""
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", "content_sha256 does not bind canonical payload")
    return artifact_id, content_sha256


def _runtime(value: Mapping[str, Any], schema: str, id_field: str, fields: set[str]) -> RuntimeContract:
    artifact_id, content_sha256 = _base(
        value, schema=schema, id_field=id_field, fields=fields
    )
    return RuntimeContract(schema, RUNTIME_SCHEMA_REVISION, artifact_id, content_sha256, dict(value))


def validate_episode_selection(value: Mapping[str, Any]) -> RuntimeContract:
    fields = {
        "schema", "schema_revision", "selection_id", "producer",
        "prepared_dataset_binding", "split", "policies", "rows", "content_sha256",
    }
    artifact_id, content_sha256 = _base(
        value, schema=EPISODE_SELECTION_SCHEMA, id_field="selection_id", fields=fields
    )
    _binding(value, "prepared_dataset_binding", "sidscope.prepared_dataset.v1")
    split = _object(value, "split", {"split_id", "sha256"})
    _text(split.get("split_id"), "split.split_id")
    _sha(split.get("sha256"), "split.sha256")
    policies = _object(
        value,
        "policies",
        {"missing_row", "duplicate_row", "out_of_split", "target_mismatch", "catalog_unreachable"},
    )
    if any(policies.get(key) != "reject" for key in policies):
        _fail("non_fail_closed_selection_policy", str(dict(policies)))
    rows = value.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        _fail("invalid_selection_rows", "rows must be a non-empty array")
    observed_ids: set[str] = set()
    for index, row in enumerate(rows):
        expected = {
            "order", "episode_id", "split_row_index",
            "target_normalized_item_id", "evaluator_labels",
        }
        if not isinstance(row, Mapping) or set(row) != expected:
            _fail("invalid_selection_row", str(index))
        if _count(row.get("order"), f"rows[{index}].order") != index:
            _fail("noncanonical_selection_order", str(index))
        episode_id = _text(row.get("episode_id"), f"rows[{index}].episode_id")
        if episode_id in observed_ids:
            _fail("duplicate_episode_id", episode_id)
        observed_ids.add(episode_id)
        _count(row.get("split_row_index"), f"rows[{index}].split_row_index")
        _count(
            row.get("target_normalized_item_id"),
            f"rows[{index}].target_normalized_item_id",
        )
        labels = row.get("evaluator_labels")
        if not isinstance(labels, Mapping):
            _fail("invalid_evaluator_labels", episode_id)
        forbidden = {"source_user_id", "source_item_id", "user_id", "item_id"}.intersection(labels)
        if forbidden:
            _fail("source_identity_exposure", f"{episode_id}: {sorted(forbidden)}")
    return RuntimeContract(
        EPISODE_SELECTION_SCHEMA,
        RUNTIME_SCHEMA_REVISION,
        artifact_id,
        content_sha256,
        dict(value),
    )


def validate_run_identity(value: Mapping[str, Any]) -> RuntimeContract:
    fields = {
        "schema", "schema_revision", "run_id", "producer", "run_kind",
        "source_binding", "prepared_dataset_binding", "configuration_sha256",
        "seed", "command_sha256", "environment_sha256",
        "training_manifest_sha256", "content_sha256",
    }
    artifact_id, content_sha256 = _base(
        value, schema=RUN_IDENTITY_SCHEMA, id_field="run_id", fields=fields
    )
    run_kind = _text(value.get("run_kind"), "run_kind")
    if run_kind not in RUN_KINDS:
        _fail("unsupported_run_kind", run_kind)
    _binding(value, "source_binding", "sidscope.source_identity.v1")
    _binding(value, "prepared_dataset_binding", "sidscope.prepared_dataset.v1")
    _sha(value.get("configuration_sha256"), "configuration_sha256")
    _sha(value.get("command_sha256"), "command_sha256")
    _sha(value.get("environment_sha256"), "environment_sha256")
    training_hash = _sha(
        value.get("training_manifest_sha256"), "training_manifest_sha256", nullable=True
    )
    seed_value = value.get("seed")
    if (
        isinstance(seed_value, bool)
        or not isinstance(seed_value, int)
        or seed_value < 0
        or seed_value > 2**63 - 1
    ):
        _fail("invalid_seed", str(seed_value))
    if run_kind == "training" and training_hash is None:
        _fail("missing_training_manifest", run_kind)
    return RuntimeContract(
        RUN_IDENTITY_SCHEMA, RUNTIME_SCHEMA_REVISION, artifact_id, content_sha256, dict(value)
    )


def validate_checkpoint_binding(value: Mapping[str, Any]) -> RuntimeContract:
    fields = {
        "schema", "schema_revision", "checkpoint_id", "producer", "run_binding",
        "checkpoint_sha256", "state_kind", "completed_epoch", "global_step",
        "state_sha256", "epoch_ledger_sha256", "previous_checkpoint_sha256",
        "content_sha256",
    }
    artifact_id, content_sha256 = _base(
        value, schema=CHECKPOINT_BINDING_SCHEMA, id_field="checkpoint_id", fields=fields
    )
    _binding(value, "run_binding", RUN_IDENTITY_SCHEMA)
    checkpoint_sha = _sha(value.get("checkpoint_sha256"), "checkpoint_sha256")
    state_kind = _text(value.get("state_kind"), "state_kind")
    if state_kind not in {"complete_resumable", "inference_only"}:
        _fail("unsupported_checkpoint_state", state_kind)
    _count(value.get("completed_epoch"), "completed_epoch")
    _count(value.get("global_step"), "global_step")
    state = _object(value, "state_sha256", {"model", "optimizer", "scheduler", "rng"})
    hashes = {
        key: _sha(state.get(key), f"state_sha256.{key}", nullable=True) for key in state
    }
    if hashes["model"] != checkpoint_sha:
        _fail("checkpoint_model_hash_mismatch", str(hashes["model"]))
    ledger = _sha(value.get("epoch_ledger_sha256"), "epoch_ledger_sha256", nullable=True)
    _sha(value.get("previous_checkpoint_sha256"), "previous_checkpoint_sha256", nullable=True)
    if state_kind == "complete_resumable" and (
        any(hashes[key] is None for key in hashes) or ledger is None
    ):
        _fail("incomplete_resumable_state", "optimizer/scheduler/RNG/ledger are required")
    if state_kind == "inference_only" and any(
        hashes[key] is not None for key in ("optimizer", "scheduler", "rng")
    ):
        _fail("inference_checkpoint_overclaim", "training state must be null")
    return RuntimeContract(
        CHECKPOINT_BINDING_SCHEMA,
        RUNTIME_SCHEMA_REVISION,
        artifact_id,
        content_sha256,
        dict(value),
    )


def validate_trace_envelope(value: Mapping[str, Any]) -> RuntimeContract:
    fields = {
        "schema", "schema_revision", "trace_envelope_id", "producer",
        "episode_selection_binding", "run_binding", "checkpoint_binding",
        "method_family", "payload_schema", "payload_sha256", "observations",
        "content_sha256",
    }
    artifact_id, content_sha256 = _base(
        value, schema=TRACE_ENVELOPE_SCHEMA, id_field="trace_envelope_id", fields=fields
    )
    _binding(value, "episode_selection_binding", EPISODE_SELECTION_SCHEMA)
    _binding(value, "run_binding", RUN_IDENTITY_SCHEMA)
    _binding(value, "checkpoint_binding", CHECKPOINT_BINDING_SCHEMA)
    family = _text(value.get("method_family"), "method_family")
    if family not in METHOD_FAMILIES:
        _fail("unsupported_method_family", family)
    payload_schema = _text(value.get("payload_schema"), "payload_schema")
    if payload_schema == TRACE_ENVELOPE_SCHEMA:
        _fail("recursive_payload_schema", payload_schema)
    _sha(value.get("payload_sha256"), "payload_sha256")
    observations = value.get("observations")
    if not isinstance(observations, Sequence) or isinstance(
        observations, (str, bytes)
    ) or not observations:
        _fail("invalid_observations", "observations must be non-empty")
    episode_ids: set[str] = set()
    for index, row in enumerate(observations):
        expected = {
            "selection_order", "episode_id", "attempt_count", "termination_state",
            "failure_state", "target", "compute",
        }
        if not isinstance(row, Mapping) or set(row) != expected:
            _fail("invalid_observation", str(index))
        if _count(row.get("selection_order"), f"observations[{index}].selection_order") != index:
            _fail("noncanonical_observation_order", str(index))
        episode_id = _text(row.get("episode_id"), f"observations[{index}].episode_id")
        if episode_id in episode_ids:
            _fail("duplicate_episode_id", episode_id)
        episode_ids.add(episode_id)
        _count(row.get("attempt_count"), f"observations[{index}].attempt_count", minimum=1)
        _text(row.get("termination_state"), f"observations[{index}].termination_state")
        failure_state = row.get("failure_state")
        if failure_state is not None:
            _text(failure_state, f"observations[{index}].failure_state")
        target = row.get("target")
        target_fields = {
            "catalog_reachable", "generated", "resolved", "rank_state",
            "exact_rank", "rank_lower_bound",
        }
        if not isinstance(target, Mapping) or set(target) != target_fields:
            _fail("invalid_target_observation", episode_id)
        for flag in ("catalog_reachable", "generated", "resolved"):
            if not isinstance(target.get(flag), bool):
                _fail("invalid_boolean", f"{episode_id}.target.{flag}")
        rank_state = _text(target.get("rank_state"), f"{episode_id}.target.rank_state")
        if rank_state not in RANK_STATES:
            _fail("unsupported_rank_state", rank_state)
        exact = target.get("exact_rank")
        lower = target.get("rank_lower_bound")
        if exact is not None:
            _count(exact, f"{episode_id}.target.exact_rank", minimum=1)
        if lower is not None:
            _count(lower, f"{episode_id}.target.rank_lower_bound", minimum=1)
        if rank_state == "exact" and (exact is None or lower is not None):
            _fail("rank_state_mismatch", episode_id)
        if rank_state == "right_censored" and (exact is not None or lower is None):
            _fail("rank_state_mismatch", episode_id)
        if rank_state == "not_applicable" and (exact is not None or lower is not None):
            _fail("rank_state_mismatch", episode_id)
        compute = row.get("compute")
        compute_fields = {"nfe", "forward_calls", "candidate_count", "latency_ms"}
        if not isinstance(compute, Mapping) or set(compute) != compute_fields:
            _fail("invalid_compute", episode_id)
        for field in compute_fields - {"latency_ms"}:
            _count(compute.get(field), f"{episode_id}.compute.{field}")
        _nonnegative_number(compute.get("latency_ms"), f"{episode_id}.compute.latency_ms")
    return RuntimeContract(
        TRACE_ENVELOPE_SCHEMA,
        RUNTIME_SCHEMA_REVISION,
        artifact_id,
        content_sha256,
        dict(value),
    )


def validate_runtime_bindings(
    selection: RuntimeContract,
    run: RuntimeContract,
    checkpoint: RuntimeContract,
    trace: RuntimeContract,
    *,
    source_sha256: str,
    prepared_sha256: str,
) -> None:
    selection_doc = selection.to_dict()
    run_doc = run.to_dict()
    checkpoint_doc = checkpoint.to_dict()
    trace_doc = trace.to_dict()
    expected = (
        (selection_doc["prepared_dataset_binding"]["content_sha256"], prepared_sha256, "selection_prepared_binding_mismatch"),
        (run_doc["source_binding"]["content_sha256"], source_sha256, "run_source_binding_mismatch"),
        (run_doc["prepared_dataset_binding"]["content_sha256"], prepared_sha256, "run_prepared_binding_mismatch"),
        (checkpoint_doc["run_binding"]["content_sha256"], run.content_sha256, "checkpoint_run_binding_mismatch"),
        (trace_doc["episode_selection_binding"]["content_sha256"], selection.content_sha256, "trace_selection_binding_mismatch"),
        (trace_doc["run_binding"]["content_sha256"], run.content_sha256, "trace_run_binding_mismatch"),
        (trace_doc["checkpoint_binding"]["content_sha256"], checkpoint.content_sha256, "trace_checkpoint_binding_mismatch"),
    )
    for observed, wanted, code in expected:
        if observed != wanted:
            _fail(code, f"{observed} != {wanted}")
    selected = [row["episode_id"] for row in selection_doc["rows"]]
    traced = [row["episode_id"] for row in trace_doc["observations"]]
    if traced != selected:
        _fail("trace_selection_episode_mismatch", str(traced))


def _load(path: Path, validator: Any) -> RuntimeContract:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain an object")
    return validator(value)


def load_episode_selection(path: Path) -> RuntimeContract:
    return _load(path, validate_episode_selection)


def load_run_identity(path: Path) -> RuntimeContract:
    return _load(path, validate_run_identity)


def load_checkpoint_binding(path: Path) -> RuntimeContract:
    return _load(path, validate_checkpoint_binding)


def load_trace_envelope(path: Path) -> RuntimeContract:
    return _load(path, validate_trace_envelope)


def runtime_schema_path(name: str) -> Path:
    return Path(resources.files("sidinspector.schemas").joinpath(name))
