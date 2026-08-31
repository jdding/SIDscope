"""Versioned shared conformance profiles and profile-bound report contracts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from sidinspector.contracts import (
    SHA256_PATTERN,
    verify_content_sha256,
    with_content_sha256,
)


PROFILE_CATALOG_SCHEMA = "sidscope.conformance_profile_catalog.v1"
PROFILE_CATALOG_REVISION = "1.0.0"
DATASET_PROFILE_DESCRIPTOR_SCHEMA = "sidscope.dataset_profile_descriptor.v1"
PROFILE_CONFORMANCE_REPORT_SCHEMA = "sidscope.profile_conformance_report.v1"
CONTRACT_REVISION = "1.0.0"
PROFILE_KINDS = frozenset({"static_mapping", "generator", "overlay", "release"})
PROFILE_LIFECYCLE_STATUSES = frozenset({"active", "deprecated", "blocked"})
GATE_STATUSES = frozenset({"pass", "partial", "fail"})
SPLIT_ROLES = ("train", "validation", "test")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class ProfileEngineError(ValueError):
    """Stable typed failure for catalog, descriptor and profile report validation."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SharedGateDefinition:
    gate_id: str
    owner: str
    depends_on: tuple[str, ...]
    failure_code: str


@dataclass(frozen=True)
class SharedProfileDefinition:
    profile_id: str
    revision: str
    profile_kind: str
    owner: str
    gates: tuple[SharedGateDefinition, ...]
    fixture: Mapping[str, Any]
    lifecycle: Mapping[str, str]
    status_label_policy: Mapping[str, str]


@dataclass(frozen=True)
class DatasetProfileDescriptor:
    descriptor_id: str
    content_sha256: str
    document: Mapping[str, Any]

    @property
    def schema(self) -> str:
        return DATASET_PROFILE_DESCRIPTOR_SCHEMA

    @property
    def schema_revision(self) -> str:
        return CONTRACT_REVISION

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.document, allow_nan=False))


@dataclass(frozen=True)
class ProfileConformanceReport:
    report_id: str
    profile_id: str
    profile_revision: str
    decision_status: str
    status_label: str
    content_sha256: str
    document: Mapping[str, Any]

    @property
    def schema(self) -> str:
        return PROFILE_CONFORMANCE_REPORT_SCHEMA

    @property
    def schema_revision(self) -> str:
        return CONTRACT_REVISION

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.document, allow_nan=False))


def _fail(code: str, detail: str) -> None:
    raise ProfileEngineError(code, detail)


def _exact_object(value: Any, fields: set[str], location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{location} must be an object")
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        _fail("unknown_field", f"{location}: {unknown}")
    if missing:
        _fail("missing_field", f"{location}: {missing}")
    return value


def _sequence(value: Any, location: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("invalid_type", f"{location} must be an array")
    return value


def _text(value: Any, location: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{location} must be non-empty text")
    if identifier and ID_PATTERN.fullmatch(value) is None:
        _fail("invalid_identifier", location)
    return value


def _sha(value: Any, location: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", location)
    return value


def _count(value: Any, location: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_count", f"{location} must be >= {minimum}")
    return value


def _producer(value: Any, location: str = "producer") -> Mapping[str, str]:
    producer = _exact_object(value, {"name", "version"}, location)
    return {
        "name": _text(producer.get("name"), f"{location}.name"),
        "version": _text(producer.get("version"), f"{location}.version"),
    }


def _relative_fixture_path(value: Any, location: str) -> str:
    path = _text(value, location)
    if Path(path).is_absolute() or ".." in Path(path).parts:
        _fail("unsafe_fixture_path", location)
    return path


def _validate_gate_order(gates: tuple[SharedGateDefinition, ...], profile_id: str) -> None:
    gate_ids = [gate.gate_id for gate in gates]
    if len(gate_ids) != len(set(gate_ids)):
        _fail("duplicate_gate", profile_id)
    emitted: set[str] = set()
    for gate in gates:
        missing = sorted(set(gate.depends_on) - set(gate_ids))
        if missing:
            _fail("unknown_gate_dependency", f"{gate.gate_id}: {missing}")
        late = sorted(set(gate.depends_on) - emitted)
        if late:
            _fail("noncanonical_gate_order", f"{gate.gate_id}: {late}")
        emitted.add(gate.gate_id)


def validate_profile_catalog(
    value: Mapping[str, Any],
) -> tuple[SharedProfileDefinition, ...]:
    """Strictly validate an arbitrary shared profile catalog document."""

    _exact_object(
        value, {"schema", "schema_revision", "profiles", "content_sha256"}, "catalog"
    )
    if value.get("schema") != PROFILE_CATALOG_SCHEMA:
        _fail("profile_catalog_schema_mismatch", str(value.get("schema")))
    if value.get("schema_revision") != PROFILE_CATALOG_REVISION:
        _fail("profile_catalog_revision_mismatch", str(value.get("schema_revision")))
    if not verify_content_sha256(value):
        _fail("profile_catalog_hash_mismatch", "catalog content hash mismatch")

    profiles: list[SharedProfileDefinition] = []
    for index, raw in enumerate(_sequence(value.get("profiles"), "catalog.profiles")):
        row = _exact_object(
            raw,
            {
                "profile_id",
                "revision",
                "profile_kind",
                "owner",
                "gates",
                "fixture",
                "lifecycle",
                "status_label_policy",
            },
            f"profiles[{index}]",
        )
        profile_id = _text(row.get("profile_id"), f"profiles[{index}].profile_id", identifier=True)
        revision = _text(row.get("revision"), f"profiles[{index}].revision")
        if SEMVER_PATTERN.fullmatch(revision) is None:
            _fail("invalid_profile_revision", f"{profile_id}@{revision}")
        profile_kind = _text(row.get("profile_kind"), f"profiles[{index}].profile_kind")
        if profile_kind not in PROFILE_KINDS:
            _fail("unsupported_profile_kind", profile_kind)
        owner = _text(row.get("owner"), f"profiles[{index}].owner")
        gates: list[SharedGateDefinition] = []
        for gate_index, raw_gate in enumerate(
            _sequence(row.get("gates"), f"profiles[{index}].gates")
        ):
            gate = _exact_object(
                raw_gate,
                {"gate_id", "owner", "depends_on", "failure_code"},
                f"profiles[{index}].gates[{gate_index}]",
            )
            dependencies = tuple(
                _text(item, f"profiles[{index}].gates[{gate_index}].depends_on[]", identifier=True)
                for item in _sequence(
                    gate.get("depends_on"),
                    f"profiles[{index}].gates[{gate_index}].depends_on",
                )
            )
            if list(dependencies) != sorted(set(dependencies)):
                _fail("noncanonical_gate_dependencies", str(gate.get("gate_id")))
            gates.append(
                SharedGateDefinition(
                    gate_id=_text(
                        gate.get("gate_id"),
                        f"profiles[{index}].gates[{gate_index}].gate_id",
                        identifier=True,
                    ),
                    owner=_text(gate.get("owner"), f"profiles[{index}].gates[{gate_index}].owner"),
                    depends_on=dependencies,
                    failure_code=_text(
                        gate.get("failure_code"),
                        f"profiles[{index}].gates[{gate_index}].failure_code",
                        identifier=True,
                    ),
                )
            )
        if not gates:
            _fail("empty_profile_gates", profile_id)
        _validate_gate_order(tuple(gates), profile_id)

        fixture = _exact_object(row.get("fixture"), {"positive", "negatives"}, "fixture")
        positive = _relative_fixture_path(fixture.get("positive"), "fixture.positive")
        negatives = tuple(
            _relative_fixture_path(item, "fixture.negatives[]")
            for item in _sequence(fixture.get("negatives"), "fixture.negatives")
        )
        if list(negatives) != sorted(set(negatives)) or not negatives:
            _fail("noncanonical_fixture_negatives", profile_id)

        lifecycle = _exact_object(
            row.get("lifecycle"),
            {"status", "migration_policy", "deprecation_policy"},
            "lifecycle",
        )
        lifecycle_status = _text(lifecycle.get("status"), "lifecycle.status")
        if lifecycle_status not in PROFILE_LIFECYCLE_STATUSES:
            _fail("unsupported_profile_lifecycle", lifecycle_status)
        lifecycle_value = {
            "status": lifecycle_status,
            "migration_policy": _text(
                lifecycle.get("migration_policy"), "lifecycle.migration_policy"
            ),
            "deprecation_policy": _text(
                lifecycle.get("deprecation_policy"), "lifecycle.deprecation_policy"
            ),
        }
        policy = _exact_object(
            row.get("status_label_policy"), {"pass", "partial", "fail"}, "status_label_policy"
        )
        policy_value = {
            status: _text(policy.get(status), f"status_label_policy.{status}")
            for status in ("pass", "partial", "fail")
        }
        profiles.append(
            SharedProfileDefinition(
                profile_id=profile_id,
                revision=revision,
                profile_kind=profile_kind,
                owner=owner,
                gates=tuple(gates),
                fixture={"positive": positive, "negatives": negatives},
                lifecycle=lifecycle_value,
                status_label_policy=policy_value,
            )
        )
    profile_ids = [profile.profile_id for profile in profiles]
    if profile_ids != sorted(set(profile_ids)):
        _fail("noncanonical_profile_order", str(profile_ids))
    if set(profile.profile_kind for profile in profiles) != PROFILE_KINDS:
        _fail("missing_profile_kind", str(sorted(set(profile.profile_kind for profile in profiles))))
    return tuple(profiles)


def load_profile_catalog() -> tuple[SharedProfileDefinition, ...]:
    """Load and strictly validate the packaged shared profile catalog."""

    path = resources.files("sidinspector.schemas").joinpath(
        "conformance_profile_catalog.v1.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain an object")
    return validate_profile_catalog(value)


def profile_catalog_content_sha256() -> str:
    path = resources.files("sidinspector.schemas").joinpath(
        "conformance_profile_catalog.v1.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    load_profile_catalog()
    return str(value["content_sha256"])


def get_profile_definition(
    profile_id: str,
    *,
    revision: str | None = None,
    require_active: bool = True,
) -> SharedProfileDefinition:
    profiles = {profile.profile_id: profile for profile in load_profile_catalog()}
    profile = profiles.get(profile_id)
    if profile is None:
        _fail("unknown_profile", profile_id)
    if revision is not None and revision != profile.revision:
        _fail("profile_revision_mismatch", f"{profile_id}: {revision} != {profile.revision}")
    if require_active and profile.lifecycle["status"] != "active":
        _fail("inactive_profile", f"{profile_id}: {profile.lifecycle['status']}")
    return profile


def validate_dataset_profile_descriptor(value: Mapping[str, Any]) -> DatasetProfileDescriptor:
    """Validate a strict, privacy-safe dataset/profile comparison descriptor."""

    fields = {
        "schema",
        "schema_revision",
        "descriptor_id",
        "producer",
        "dataset_identity_sha256",
        "split_bindings",
        "catalog",
        "target_universe",
        "evaluation",
        "privacy",
        "content_sha256",
    }
    _exact_object(value, fields, "dataset_profile_descriptor")
    if value.get("schema") != DATASET_PROFILE_DESCRIPTOR_SCHEMA:
        _fail("schema_mismatch", DATASET_PROFILE_DESCRIPTOR_SCHEMA)
    if value.get("schema_revision") != CONTRACT_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    descriptor_id = _text(value.get("descriptor_id"), "descriptor_id", identifier=True)
    _producer(value.get("producer"))
    _sha(value.get("dataset_identity_sha256"), "dataset_identity_sha256")

    split_roles: list[str] = []
    for index, raw in enumerate(_sequence(value.get("split_bindings"), "split_bindings")):
        split = _exact_object(
            raw, {"role", "content_sha256", "row_count"}, f"split_bindings[{index}]"
        )
        role = _text(split.get("role"), f"split_bindings[{index}].role")
        if role not in SPLIT_ROLES:
            _fail("unsupported_split_role", role)
        split_roles.append(role)
        _sha(split.get("content_sha256"), f"split_bindings[{index}].content_sha256")
        _count(split.get("row_count"), f"split_bindings[{index}].row_count")
    if tuple(split_roles) != SPLIT_ROLES:
        _fail("noncanonical_split_order", str(split_roles))

    for field, scopes in (
        ("catalog", {"train_only", "full_dataset"}),
        ("target_universe", {"train_only_catalog", "evaluation_targets"}),
    ):
        binding = _exact_object(
            value.get(field), {"scope", "item_count", "content_sha256"}, field
        )
        scope = _text(binding.get("scope"), f"{field}.scope")
        if scope not in scopes:
            _fail("unsupported_scope", f"{field}.scope={scope}")
        _count(binding.get("item_count"), f"{field}.item_count", positive=True)
        _sha(binding.get("content_sha256"), f"{field}.content_sha256")

    evaluation = _exact_object(
        value.get("evaluation"), {"cutoff", "publication_depth", "slices"}, "evaluation"
    )
    cutoff = _count(evaluation.get("cutoff"), "evaluation.cutoff", positive=True)
    depth = _count(
        evaluation.get("publication_depth"), "evaluation.publication_depth", positive=True
    )
    if depth < cutoff:
        _fail("invalid_evaluation_depth", f"cutoff={cutoff}, publication_depth={depth}")
    slice_ids: list[str] = []
    for index, raw in enumerate(_sequence(evaluation.get("slices"), "evaluation.slices")):
        slice_row = _exact_object(
            raw, {"slice_id", "definition_sha256"}, f"evaluation.slices[{index}]"
        )
        slice_ids.append(
            _text(slice_row.get("slice_id"), f"evaluation.slices[{index}].slice_id", identifier=True)
        )
        _sha(slice_row.get("definition_sha256"), f"evaluation.slices[{index}].definition_sha256")
    if not slice_ids or slice_ids != sorted(set(slice_ids)):
        _fail("noncanonical_slices", str(slice_ids))

    privacy = _exact_object(
        value.get("privacy"),
        {
            "policy_sha256",
            "source_user_ids_exported",
            "source_item_ids_exported",
            "absolute_private_paths_exported",
        },
        "privacy",
    )
    _sha(privacy.get("policy_sha256"), "privacy.policy_sha256")
    for flag in (
        "source_user_ids_exported",
        "source_item_ids_exported",
        "absolute_private_paths_exported",
    ):
        if not isinstance(privacy.get(flag), bool):
            _fail("invalid_privacy_flag", f"privacy.{flag}")
        if privacy[flag]:
            _fail("privacy_boundary_violation", f"privacy.{flag}")

    content_sha256 = _sha(value.get("content_sha256"), "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", DATASET_PROFILE_DESCRIPTOR_SCHEMA)
    return DatasetProfileDescriptor(descriptor_id, content_sha256, dict(value))


def load_dataset_profile_descriptor(path: Path) -> DatasetProfileDescriptor:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _fail("descriptor_load_failed", f"{path}: {error}")
    if not isinstance(value, Mapping):
        _fail("invalid_type", str(path))
    return validate_dataset_profile_descriptor(value)


def build_dataset_profile_descriptor(**fields: Any) -> DatasetProfileDescriptor:
    """Build and hash a descriptor from its exact non-hash fields."""

    document = {
        "schema": DATASET_PROFILE_DESCRIPTOR_SCHEMA,
        "schema_revision": CONTRACT_REVISION,
        **fields,
    }
    return validate_dataset_profile_descriptor(with_content_sha256(document))


def _artifact_rows(value: Any, descriptor_hash: str) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    identifiers: list[str] = []
    descriptor_matches = 0
    for index, raw in enumerate(_sequence(value, "artifacts")):
        row = _exact_object(
            raw,
            {"artifact_id", "role", "schema_id", "schema_revision", "content_sha256"},
            f"artifacts[{index}]",
        )
        artifact_id = _text(row.get("artifact_id"), f"artifacts[{index}].artifact_id", identifier=True)
        identifiers.append(artifact_id)
        role = _text(row.get("role"), f"artifacts[{index}].role", identifier=True)
        schema_id = _text(row.get("schema_id"), f"artifacts[{index}].schema_id")
        schema_revision = _text(
            row.get("schema_revision"), f"artifacts[{index}].schema_revision"
        )
        content_sha256 = _sha(row.get("content_sha256"), f"artifacts[{index}].content_sha256")
        if role == "dataset_profile_descriptor":
            descriptor_matches += 1
            if (
                schema_id != DATASET_PROFILE_DESCRIPTOR_SCHEMA
                or schema_revision != CONTRACT_REVISION
                or content_sha256 != descriptor_hash
            ):
                _fail("descriptor_artifact_binding_mismatch", artifact_id)
        rows.append(dict(row))
    if identifiers != sorted(set(identifiers)) or not identifiers:
        _fail("noncanonical_artifacts", str(identifiers))
    if descriptor_matches != 1:
        _fail("missing_descriptor_artifact", str(descriptor_matches))
    return tuple(rows)


def _derived_decision_status(gate_statuses: Sequence[str]) -> str:
    if any(status == "fail" for status in gate_statuses):
        return "fail"
    if any(status == "partial" for status in gate_statuses):
        return "partial"
    return "pass"


def validate_profile_conformance_report(
    value: Mapping[str, Any],
    *,
    descriptor: DatasetProfileDescriptor | Mapping[str, Any] | None = None,
) -> ProfileConformanceReport:
    """Validate a catalog-governed report with policy-derived status labels."""

    fields = {
        "schema",
        "schema_revision",
        "report_id",
        "producer",
        "profile_binding",
        "descriptor_binding",
        "artifacts",
        "gates",
        "decision",
        "content_sha256",
    }
    _exact_object(value, fields, "profile_conformance_report")
    if value.get("schema") != PROFILE_CONFORMANCE_REPORT_SCHEMA:
        _fail("schema_mismatch", PROFILE_CONFORMANCE_REPORT_SCHEMA)
    if value.get("schema_revision") != CONTRACT_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    report_id = _text(value.get("report_id"), "report_id", identifier=True)
    _producer(value.get("producer"))
    profile_binding = _exact_object(
        value.get("profile_binding"),
        {"profile_id", "profile_revision", "catalog_sha256"},
        "profile_binding",
    )
    profile_id = _text(profile_binding.get("profile_id"), "profile_binding.profile_id")
    profile_revision = _text(
        profile_binding.get("profile_revision"), "profile_binding.profile_revision"
    )
    profile = get_profile_definition(profile_id, revision=profile_revision)
    catalog_hash = _sha(profile_binding.get("catalog_sha256"), "profile_binding.catalog_sha256")
    if catalog_hash != profile_catalog_content_sha256():
        _fail("profile_catalog_binding_mismatch", catalog_hash)

    descriptor_binding = _exact_object(
        value.get("descriptor_binding"),
        {"schema_id", "schema_revision", "content_sha256"},
        "descriptor_binding",
    )
    if descriptor_binding.get("schema_id") != DATASET_PROFILE_DESCRIPTOR_SCHEMA:
        _fail("descriptor_schema_mismatch", str(descriptor_binding.get("schema_id")))
    if descriptor_binding.get("schema_revision") != CONTRACT_REVISION:
        _fail("descriptor_revision_mismatch", str(descriptor_binding.get("schema_revision")))
    descriptor_hash = _sha(
        descriptor_binding.get("content_sha256"), "descriptor_binding.content_sha256"
    )
    if descriptor is not None:
        validated_descriptor = (
            descriptor
            if isinstance(descriptor, DatasetProfileDescriptor)
            else validate_dataset_profile_descriptor(descriptor)
        )
        if validated_descriptor.content_sha256 != descriptor_hash:
            _fail("descriptor_binding_mismatch", descriptor_hash)
    _artifact_rows(value.get("artifacts"), descriptor_hash)

    expected_gate_ids = tuple(gate.gate_id for gate in profile.gates)
    gate_rows = _sequence(value.get("gates"), "gates")
    gate_ids: list[str] = []
    statuses: dict[str, str] = {}
    gate_by_id = {gate.gate_id: gate for gate in profile.gates}
    for index, raw in enumerate(gate_rows):
        row = _exact_object(raw, {"gate_id", "status", "failure"}, f"gates[{index}]")
        gate_id = _text(row.get("gate_id"), f"gates[{index}].gate_id", identifier=True)
        gate_ids.append(gate_id)
        status = _text(row.get("status"), f"gates[{index}].status")
        if status not in GATE_STATUSES:
            _fail("unsupported_gate_status", status)
        failure = row.get("failure")
        if status == "pass":
            if failure is not None:
                _fail("pass_gate_has_failure", gate_id)
        else:
            failure_row = _exact_object(
                failure, {"code", "detail"}, f"gates[{index}].failure"
            )
            code = _text(failure_row.get("code"), f"gates[{index}].failure.code", identifier=True)
            _text(failure_row.get("detail"), f"gates[{index}].failure.detail")
            definition = gate_by_id.get(gate_id)
            if definition is not None and code != definition.failure_code:
                _fail("unregistered_failure_code", f"{gate_id}: {code}")
        statuses[gate_id] = status
    if tuple(gate_ids) != expected_gate_ids:
        unknown = sorted(set(gate_ids) - set(expected_gate_ids))
        if unknown:
            _fail("unknown_profile_gate", f"{profile_id}: {unknown}")
        _fail("noncanonical_gate_order", f"{gate_ids} != {list(expected_gate_ids)}")
    for definition in profile.gates:
        if statuses[definition.gate_id] != "pass":
            continue
        failed_dependencies = [
            dependency
            for dependency in definition.depends_on
            if statuses[dependency] != "pass"
        ]
        if failed_dependencies:
            _fail(
                "gate_dependency_status_mismatch",
                f"{definition.gate_id}: {failed_dependencies}",
            )

    derived_status = _derived_decision_status(tuple(statuses[gate_id] for gate_id in gate_ids))
    decision = _exact_object(value.get("decision"), {"status", "status_label"}, "decision")
    decision_status = _text(decision.get("status"), "decision.status")
    if decision_status != derived_status:
        _fail("decision_gate_mismatch", f"{decision_status} != {derived_status}")
    expected_label = profile.status_label_policy[derived_status]
    status_label = _text(decision.get("status_label"), "decision.status_label")
    if status_label != expected_label:
        _fail("unsupported_status_label", f"{status_label} != {expected_label}")

    content_sha256 = _sha(value.get("content_sha256"), "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", PROFILE_CONFORMANCE_REPORT_SCHEMA)
    return ProfileConformanceReport(
        report_id=report_id,
        profile_id=profile_id,
        profile_revision=profile_revision,
        decision_status=derived_status,
        status_label=status_label,
        content_sha256=content_sha256,
        document=dict(value),
    )


def load_profile_conformance_report(
    path: Path,
    *,
    descriptor: DatasetProfileDescriptor | Mapping[str, Any] | None = None,
) -> ProfileConformanceReport:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _fail("report_load_failed", f"{path}: {error}")
    if not isinstance(value, Mapping):
        _fail("invalid_type", str(path))
    return validate_profile_conformance_report(value, descriptor=descriptor)


def build_profile_conformance_report(
    *,
    report_id: str,
    producer: Mapping[str, Any],
    profile_id: str,
    descriptor: DatasetProfileDescriptor | Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    gate_results: Sequence[Mapping[str, Any]],
) -> ProfileConformanceReport:
    """Build a report whose status and public label are catalog-policy derived."""

    validated_descriptor = (
        descriptor
        if isinstance(descriptor, DatasetProfileDescriptor)
        else validate_dataset_profile_descriptor(descriptor)
    )
    profile = get_profile_definition(profile_id)
    statuses = [str(row.get("status")) for row in gate_results]
    decision_status = _derived_decision_status(statuses)
    document = with_content_sha256(
        {
            "schema": PROFILE_CONFORMANCE_REPORT_SCHEMA,
            "schema_revision": CONTRACT_REVISION,
            "report_id": report_id,
            "producer": dict(producer),
            "profile_binding": {
                "profile_id": profile.profile_id,
                "profile_revision": profile.revision,
                "catalog_sha256": profile_catalog_content_sha256(),
            },
            "descriptor_binding": {
                "schema_id": DATASET_PROFILE_DESCRIPTOR_SCHEMA,
                "schema_revision": CONTRACT_REVISION,
                "content_sha256": validated_descriptor.content_sha256,
            },
            "artifacts": sorted(
                (dict(row) for row in artifacts), key=lambda row: row.get("artifact_id", "")
            ),
            "gates": [dict(row) for row in gate_results],
            "decision": {
                "status": decision_status,
                "status_label": profile.status_label_policy[decision_status],
            },
        }
    )
    return validate_profile_conformance_report(document, descriptor=validated_descriptor)


__all__ = [
    "CONTRACT_REVISION",
    "DATASET_PROFILE_DESCRIPTOR_SCHEMA",
    "PROFILE_CATALOG_REVISION",
    "PROFILE_CATALOG_SCHEMA",
    "PROFILE_CONFORMANCE_REPORT_SCHEMA",
    "DatasetProfileDescriptor",
    "ProfileConformanceReport",
    "ProfileEngineError",
    "SharedGateDefinition",
    "SharedProfileDefinition",
    "build_dataset_profile_descriptor",
    "build_profile_conformance_report",
    "get_profile_definition",
    "load_dataset_profile_descriptor",
    "load_profile_catalog",
    "load_profile_conformance_report",
    "profile_catalog_content_sha256",
    "validate_dataset_profile_descriptor",
    "validate_profile_conformance_report",
]
