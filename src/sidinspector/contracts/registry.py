"""Versioned contract registry and generic validator dispatch."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .dataset_identity import load_dataset_identity
from .hashing import SHA256_PATTERN, verify_content_sha256
from .prepared_dataset import load_prepared_dataset
from .report_contracts import (
    load_conformance_report,
    load_diagnostic_report,
    load_evidence_index,
)
from .runtime_contracts import (
    load_checkpoint_binding,
    load_episode_selection,
    load_run_identity,
    load_trace_envelope,
)
from .sid_space_identity import load_sid_space_identity
from .source_identity import load_source_identity


CONTRACT_REGISTRY_SCHEMA = "sidscope.contract_registry.v1"
CONTRACT_REGISTRY_SCHEMA_REVISION = "1.0.0"


class ContractRegistryError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class NegativeFixture:
    path: str
    expected_failure: str


@dataclass(frozen=True)
class ContractDependency:
    schema_id: str
    accepted_revisions: tuple[str, ...]


@dataclass(frozen=True)
class ContractDescriptor:
    contract_type: str
    schema_id: str
    schema_revision: str
    owner: str
    schema_resource: str
    compatibility: str
    supported_revisions: tuple[str, ...]
    canonical_fixture: str
    negative_fixtures: tuple[NegativeFixture, ...]
    dependencies: tuple[ContractDependency, ...]
    result_id_field: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_id": self.schema_id,
            "schema_revision": self.schema_revision,
            "owner": self.owner,
            "schema_resource": self.schema_resource,
            "compatibility": {
                "policy": self.compatibility,
                "supported_revisions": list(self.supported_revisions),
            },
            "canonical_fixture": self.canonical_fixture,
            "negative_fixtures": [
                {"path": fixture.path, "expected_failure": fixture.expected_failure}
                for fixture in self.negative_fixtures
            ],
            "dependencies": [
                {
                    "schema_id": dependency.schema_id,
                    "accepted_revisions": list(dependency.accepted_revisions),
                }
                for dependency in self.dependencies
            ],
            "result_id_field": self.result_id_field,
        }


@dataclass(frozen=True)
class ContractRegistry:
    schema: str
    schema_revision: str
    registry_id: str
    producer_name: str
    producer_version: str
    contracts: tuple[ContractDescriptor, ...]
    content_sha256: str

    def by_type(self, contract_type: str) -> ContractDescriptor:
        for descriptor in self.contracts:
            if descriptor.contract_type == contract_type:
                return descriptor
        raise ContractRegistryError("unknown_contract_type", contract_type)

    def by_schema_id(self, schema_id: str) -> ContractDescriptor:
        for descriptor in self.contracts:
            if descriptor.schema_id == schema_id:
                return descriptor
        raise ContractRegistryError("unknown_schema_id", schema_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_revision": self.schema_revision,
            "registry_id": self.registry_id,
            "producer": {"name": self.producer_name, "version": self.producer_version},
            "contracts": [descriptor.to_dict() for descriptor in self.contracts],
            "content_sha256": self.content_sha256,
        }


def _fail(code: str, detail: str) -> None:
    raise ContractRegistryError(code, detail)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be a non-empty string")
    return value


def _safe_path(value: Any, field: str) -> str:
    path = _text(value, field)
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or path != pure.as_posix():
        _fail("unsafe_registry_path", f"{field}={path}")
    return path


def validate_contract_registry(
    value: Mapping[str, Any], *, repository_root: Path | None = None
) -> ContractRegistry:
    if not isinstance(value, Mapping):
        _fail("invalid_type", "registry must be an object")
    fields = {"schema", "schema_revision", "registry_id", "producer", "contracts", "content_sha256"}
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        _fail("unknown_field", f"unsupported top-level fields: {unknown}")
    if missing:
        _fail("missing_field", f"missing top-level fields: {missing}")
    if value.get("schema") != CONTRACT_REGISTRY_SCHEMA:
        _fail("schema_mismatch", f"schema must be {CONTRACT_REGISTRY_SCHEMA}")
    if value.get("schema_revision") != CONTRACT_REGISTRY_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))

    producer = value.get("producer")
    if not isinstance(producer, Mapping) or set(producer) != {"name", "version"}:
        _fail("invalid_producer", "producer must contain exactly name and version")
    contracts_raw = value.get("contracts")
    if not isinstance(contracts_raw, Sequence) or isinstance(contracts_raw, (str, bytes)):
        _fail("invalid_type", "contracts must be an array")

    descriptors: list[ContractDescriptor] = []
    descriptor_fields = {
        "contract_type", "schema_id", "schema_revision", "owner", "schema_resource",
        "compatibility", "canonical_fixture", "negative_fixtures", "dependencies",
        "result_id_field",
    }
    for index, raw in enumerate(contracts_raw):
        if not isinstance(raw, Mapping) or set(raw) != descriptor_fields:
            _fail("invalid_descriptor", f"contracts[{index}] fields differ from registry v1")
        compatibility = raw.get("compatibility")
        if not isinstance(compatibility, Mapping) or set(compatibility) != {"policy", "supported_revisions"}:
            _fail("invalid_compatibility", f"contracts[{index}].compatibility")
        policy = _text(compatibility.get("policy"), "compatibility.policy")
        if policy != "exact_major_supported_revision":
            _fail("unsupported_compatibility_policy", policy)
        revisions_raw = compatibility.get("supported_revisions")
        if not isinstance(revisions_raw, Sequence) or isinstance(revisions_raw, (str, bytes)):
            _fail("invalid_type", "supported_revisions must be an array")
        revisions = tuple(_text(item, "supported_revisions[]") for item in revisions_raw)
        if list(revisions) != sorted(set(revisions)):
            _fail("noncanonical_order", "supported_revisions must be sorted and unique")
        revision = _text(raw.get("schema_revision"), "schema_revision")
        if revision not in revisions:
            _fail("unsupported_schema_revision", revision)

        negative_raw = raw.get("negative_fixtures")
        if not isinstance(negative_raw, Sequence) or isinstance(negative_raw, (str, bytes)):
            _fail("invalid_type", "negative_fixtures must be an array")
        negative: list[NegativeFixture] = []
        for fixture_index, fixture in enumerate(negative_raw):
            if not isinstance(fixture, Mapping) or set(fixture) != {"path", "expected_failure"}:
                _fail("invalid_negative_fixture", f"contracts[{index}].negative_fixtures[{fixture_index}]")
            negative.append(
                NegativeFixture(
                    path=_safe_path(fixture.get("path"), "negative_fixtures.path"),
                    expected_failure=_text(fixture.get("expected_failure"), "expected_failure"),
                )
            )
        paths = [fixture.path for fixture in negative]
        if paths != sorted(set(paths)):
            _fail("noncanonical_order", "negative fixtures must be sorted by unique path")

        dependencies_raw = raw.get("dependencies")
        if not isinstance(dependencies_raw, Sequence) or isinstance(dependencies_raw, (str, bytes)):
            _fail("invalid_type", "dependencies must be an array")
        dependencies: list[ContractDependency] = []
        for dependency_index, dependency in enumerate(dependencies_raw):
            if not isinstance(dependency, Mapping) or set(dependency) != {
                "schema_id",
                "accepted_revisions",
            }:
                _fail(
                    "invalid_dependency",
                    f"contracts[{index}].dependencies[{dependency_index}]",
                )
            accepted_raw = dependency.get("accepted_revisions")
            if not isinstance(accepted_raw, Sequence) or isinstance(
                accepted_raw, (str, bytes)
            ):
                _fail("invalid_type", "accepted_revisions must be an array")
            accepted = tuple(
                _text(item, "accepted_revisions[]") for item in accepted_raw
            )
            if not accepted or list(accepted) != sorted(set(accepted)):
                _fail(
                    "noncanonical_order",
                    "accepted_revisions must be nonempty, sorted, and unique",
                )
            dependencies.append(
                ContractDependency(
                    schema_id=_text(dependency.get("schema_id"), "dependency.schema_id"),
                    accepted_revisions=accepted,
                )
            )
        dependency_ids = [dependency.schema_id for dependency in dependencies]
        if dependency_ids != sorted(set(dependency_ids)):
            _fail("noncanonical_order", "dependencies must be sorted by unique schema_id")
        descriptor = ContractDescriptor(
            contract_type=_text(raw.get("contract_type"), "contract_type"),
            schema_id=_text(raw.get("schema_id"), "schema_id"),
            schema_revision=revision,
            owner=_text(raw.get("owner"), "owner"),
            schema_resource=_safe_path(raw.get("schema_resource"), "schema_resource"),
            compatibility=policy,
            supported_revisions=revisions,
            canonical_fixture=_safe_path(raw.get("canonical_fixture"), "canonical_fixture"),
            negative_fixtures=tuple(negative),
            dependencies=tuple(dependencies),
            result_id_field=_text(raw.get("result_id_field"), "result_id_field"),
        )
        descriptors.append(descriptor)

    type_names = [item.contract_type for item in descriptors]
    schema_ids = [item.schema_id for item in descriptors]
    if type_names != sorted(set(type_names)):
        _fail("noncanonical_contract_order", "contracts must be sorted by unique contract_type")
    if len(schema_ids) != len(set(schema_ids)):
        _fail("duplicate_schema_id", "schema IDs must be unique")
    known = set(schema_ids)
    descriptors_by_schema = {item.schema_id: item for item in descriptors}
    for item in descriptors:
        unknown_dependencies = sorted(
            dependency.schema_id
            for dependency in item.dependencies
            if dependency.schema_id not in known
        )
        if unknown_dependencies:
            _fail("unknown_dependency", f"{item.schema_id}: {unknown_dependencies}")
        for dependency in item.dependencies:
            target = descriptors_by_schema[dependency.schema_id]
            unsupported = sorted(
                set(dependency.accepted_revisions) - set(target.supported_revisions)
            )
            if unsupported:
                _fail(
                    "incompatible_dependency",
                    f"{item.schema_id} requires {dependency.schema_id} "
                    f"at unsupported revisions {unsupported}",
                )

    graph = {
        item.schema_id: {dependency.schema_id for dependency in item.dependencies}
        for item in descriptors
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(schema_id: str) -> None:
        if schema_id in visiting:
            _fail("dependency_cycle", schema_id)
        if schema_id in visited:
            return
        visiting.add(schema_id)
        for dependency in graph[schema_id]:
            visit(dependency)
        visiting.remove(schema_id)
        visited.add(schema_id)

    for schema_id in sorted(graph):
        visit(schema_id)

    content_sha256 = value.get("content_sha256")
    if not isinstance(content_sha256, str) or SHA256_PATTERN.fullmatch(content_sha256) is None:
        _fail("invalid_sha256", "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", "registry content hash mismatch")

    if repository_root is not None:
        registry_schema_path = (
            repository_root
            / "src"
            / "sidinspector"
            / "schemas"
            / "contract_registry.v1.schema.json"
        )
        if not registry_schema_path.is_file():
            _fail("missing_schema_resource", "contract_registry.v1.schema.json")
        registry_schema = json.loads(registry_schema_path.read_text(encoding="utf-8"))
        if registry_schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            _fail("schema_dialect_mismatch", "contract_registry.v1.schema.json")
        for item in descriptors:
            for rel_path in (
                item.canonical_fixture,
                *(fixture.path for fixture in item.negative_fixtures),
            ):
                if not (repository_root / rel_path).is_file():
                    _fail("missing_registry_resource", rel_path)
            schema_path = repository_root / "src" / "sidinspector" / "schemas" / item.schema_resource
            if not schema_path.is_file():
                _fail("missing_schema_resource", item.schema_resource)
            schema_doc = json.loads(schema_path.read_text(encoding="utf-8"))
            if schema_doc.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                _fail("schema_dialect_mismatch", item.schema_resource)
            if schema_doc.get("properties", {}).get("schema", {}).get("const") != item.schema_id:
                _fail("schema_resource_mismatch", item.schema_resource)

    return ContractRegistry(
        schema=CONTRACT_REGISTRY_SCHEMA,
        schema_revision=CONTRACT_REGISTRY_SCHEMA_REVISION,
        registry_id=_text(value.get("registry_id"), "registry_id"),
        producer_name=_text(producer.get("name"), "producer.name"),
        producer_version=_text(producer.get("version"), "producer.version"),
        contracts=tuple(descriptors),
        content_sha256=content_sha256,
    )


def contract_registry_path() -> Path:
    return Path(resources.files("sidinspector.schemas").joinpath("contract_registry.v1.json"))


@lru_cache(maxsize=1)
def _load_bundled_contract_registry() -> ContractRegistry:
    source = contract_registry_path()
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{source} must contain a JSON object")
    return validate_contract_registry(value, repository_root=None)


def load_contract_registry(
    path: Path | None = None, *, repository_root: Path | None = None
) -> ContractRegistry:
    # The bundled registry is an immutable packaged resource; caching its one
    # validation per process removes repeated scans without weakening any
    # check. Explicit paths and repository roots always reload fail-closed.
    if path is None and repository_root is None:
        return _load_bundled_contract_registry()
    source = path or contract_registry_path()
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{source} must contain a JSON object")
    return validate_contract_registry(value, repository_root=repository_root)


_LOADERS: Mapping[str, Callable[[Path], Any]] = {
    "checkpoint-binding": load_checkpoint_binding,
    "conformance-report": load_conformance_report,
    "dataset-identity": load_dataset_identity,
    "diagnostic-report": load_diagnostic_report,
    "episode-selection": load_episode_selection,
    "evidence-index": load_evidence_index,
    "prepared-dataset": load_prepared_dataset,
    "run-identity": load_run_identity,
    "sid-space-identity": load_sid_space_identity,
    "source-identity": load_source_identity,
    "trace-envelope": load_trace_envelope,
}


def load_registered_contract(contract_type: str, path: Path) -> tuple[ContractDescriptor, Any]:
    descriptor = load_contract_registry().by_type(contract_type)
    loader = _LOADERS.get(contract_type)
    if loader is None:
        _fail("missing_validator", contract_type)
    artifact = loader(path)
    if artifact.schema != descriptor.schema_id:
        _fail("registry_schema_mismatch", f"{artifact.schema} != {descriptor.schema_id}")
    if artifact.schema_revision not in descriptor.supported_revisions:
        _fail("unsupported_schema_revision", artifact.schema_revision)
    return descriptor, artifact
