"""Unified discovery and two-stage validation for public SIDScope schemas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator


class PublicSchemaValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PublicSchemaDescriptor:
    schema_id: str
    schema_resource: str
    owner: str
    semantic_validator: str

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_id": self.schema_id,
            "schema_resource": self.schema_resource,
            "owner": self.owner,
            "semantic_validator": self.semantic_validator,
        }


def _fail(code: str, detail: str) -> None:
    raise PublicSchemaValidationError(code, detail)


def _owner_and_validator(resource_name: str) -> tuple[str, str]:
    if resource_name == "cli_result.v1.schema.json":
        return "sidinspector.schemas", "sidinspector.schemas.result_contracts.validate_cli_result"
    if resource_name.startswith("adapter_capabilities"):
        return "sidinspector.sdk", "sidinspector.sdk.validate_adapter_capabilities"
    if resource_name.startswith("trace_payload_"):
        return "sidinspector.trace", "sidinspector.trace.validate_native_payload"
    if resource_name in {
        "conformance_profile_catalog.v1.schema.json",
        "dataset_profile_descriptor.v1.schema.json",
        "profile_conformance_report.v1.schema.json",
    }:
        name = {
            "conformance_profile_catalog.v1.schema.json": "validate_profile_catalog",
            "dataset_profile_descriptor.v1.schema.json": "validate_dataset_profile_descriptor",
            "profile_conformance_report.v1.schema.json": "validate_profile_conformance_report",
        }[resource_name]
        return "sidinspector.conformance_core", f"sidinspector.conformance_core.{name}"
    if resource_name == "evidence_bundle.v1.schema.json":
        return "sidinspector.evidence", "sidinspector.evidence.validate_evidence_bundle"
    if resource_name == "evidence_comparison.v1.schema.json":
        return "sidinspector.evidence", "sidinspector.evidence.validate_evidence_comparison"
    if resource_name in {
        "evidence_submission.v1.schema.json",
        "submission_check_report.v1.schema.json",
    }:
        name = {
            "evidence_submission.v1.schema.json": "validate_evidence_submission",
            "submission_check_report.v1.schema.json": "validate_submission_check_report",
        }[resource_name]
        return "sidinspector.submission", f"sidinspector.submission.{name}"
    contract_validators = {
        "checkpoint_binding.v1.schema.json": "validate_checkpoint_binding",
        "conformance_report.v1.schema.json": "validate_conformance_report",
        "contract_registry.v1.schema.json": "validate_contract_registry",
        "dataset_identity.v1.schema.json": "validate_dataset_identity",
        "diagnostic_report.v1.schema.json": "validate_diagnostic_report",
        "episode_selection.v1.schema.json": "validate_episode_selection",
        "evidence_index.v1.schema.json": "validate_evidence_index",
        "prepared_dataset.v1.schema.json": "validate_prepared_dataset",
        "run_identity.v1.schema.json": "validate_run_identity",
        "sid_space_identity.v1.schema.json": "validate_sid_space_identity",
        "source_identity.v1.schema.json": "validate_source_identity",
        "trace_envelope.v1.schema.json": "validate_trace_envelope",
    }
    name = contract_validators.get(resource_name)
    if name is None:
        _fail("unowned_schema_resource", resource_name)
    return "sidinspector.contracts", f"sidinspector.contracts.{name}"


def _schema_ids(document: Mapping[str, Any], resource_name: str) -> tuple[str, ...]:
    schema_property = document.get("properties", {}).get("schema", {})
    constant = schema_property.get("const")
    if isinstance(constant, str) and constant:
        return (constant,)
    values = schema_property.get("enum")
    if (
        isinstance(values, list)
        and values
        and all(isinstance(value, str) and value for value in values)
    ):
        if values != sorted(set(values)):
            _fail("noncanonical_schema_ids", resource_name)
        return tuple(values)
    _fail("missing_schema_identity", resource_name)


def load_public_schema_catalog() -> tuple[PublicSchemaDescriptor, ...]:
    """Discover every bundled public ``*.schema.json`` resource fail closed."""

    descriptors: list[PublicSchemaDescriptor] = []
    schema_root = resources.files("sidinspector.schemas")
    for resource in sorted(schema_root.iterdir(), key=lambda item: item.name):
        if not resource.name.endswith(".schema.json"):
            continue
        document = json.loads(resource.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            _fail("invalid_schema_resource", resource.name)
        if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            _fail("schema_dialect_mismatch", resource.name)
        try:
            Draft202012Validator.check_schema(document)
        except Exception as exc:
            _fail("invalid_json_schema", f"{resource.name}: {exc}")
        owner, validator = _owner_and_validator(resource.name)
        for schema_id in _schema_ids(document, resource.name):
            descriptors.append(
                PublicSchemaDescriptor(schema_id, resource.name, owner, validator)
            )
    descriptors.sort(key=lambda item: item.schema_id)
    schema_ids = [item.schema_id for item in descriptors]
    if schema_ids != sorted(set(schema_ids)):
        _fail("duplicate_schema_id", str(schema_ids))
    return tuple(descriptors)


def get_public_schema_descriptor(schema_id: str) -> PublicSchemaDescriptor:
    for descriptor in load_public_schema_catalog():
        if descriptor.schema_id == schema_id:
            return descriptor
    _fail("unknown_schema_id", schema_id)


def _semantic_validators() -> Mapping[str, Callable[[Mapping[str, Any]], Any]]:
    from sidinspector.schemas.result_contracts import validate_cli_result
    from sidinspector.conformance_core import (
        validate_dataset_profile_descriptor,
        validate_profile_catalog,
        validate_profile_conformance_report,
    )
    from sidinspector.contracts import (
        validate_checkpoint_binding,
        validate_conformance_report,
        validate_contract_registry,
        validate_dataset_identity,
        validate_diagnostic_report,
        validate_episode_selection,
        validate_evidence_index,
        validate_prepared_dataset,
        validate_run_identity,
        validate_sid_space_identity,
        validate_source_identity,
        validate_trace_envelope,
    )
    from sidinspector.evidence import validate_evidence_bundle, validate_evidence_comparison
    from sidinspector.sdk import validate_adapter_capabilities
    from sidinspector.submission import (
        validate_evidence_submission,
        validate_submission_check_report,
    )
    from sidinspector.trace import validate_native_payload

    return {
        "sidinspector.schemas.result_contracts.validate_cli_result": validate_cli_result,
        "sidinspector.conformance_core.validate_dataset_profile_descriptor": validate_dataset_profile_descriptor,
        "sidinspector.conformance_core.validate_profile_catalog": validate_profile_catalog,
        "sidinspector.conformance_core.validate_profile_conformance_report": validate_profile_conformance_report,
        "sidinspector.contracts.validate_checkpoint_binding": validate_checkpoint_binding,
        "sidinspector.contracts.validate_conformance_report": validate_conformance_report,
        "sidinspector.contracts.validate_contract_registry": validate_contract_registry,
        "sidinspector.contracts.validate_dataset_identity": validate_dataset_identity,
        "sidinspector.contracts.validate_diagnostic_report": validate_diagnostic_report,
        "sidinspector.contracts.validate_episode_selection": validate_episode_selection,
        "sidinspector.contracts.validate_evidence_index": validate_evidence_index,
        "sidinspector.contracts.validate_prepared_dataset": validate_prepared_dataset,
        "sidinspector.contracts.validate_run_identity": validate_run_identity,
        "sidinspector.contracts.validate_sid_space_identity": validate_sid_space_identity,
        "sidinspector.contracts.validate_source_identity": validate_source_identity,
        "sidinspector.contracts.validate_trace_envelope": validate_trace_envelope,
        "sidinspector.evidence.validate_evidence_bundle": validate_evidence_bundle,
        "sidinspector.evidence.validate_evidence_comparison": validate_evidence_comparison,
        "sidinspector.sdk.validate_adapter_capabilities": validate_adapter_capabilities,
        "sidinspector.submission.validate_evidence_submission": validate_evidence_submission,
        "sidinspector.submission.validate_submission_check_report": validate_submission_check_report,
        "sidinspector.trace.validate_native_payload": validate_native_payload,
    }


def validate_public_document(value: Mapping[str, Any]) -> PublicSchemaDescriptor:
    """Validate JSON Schema structure first, then the owning semantic validator."""

    if not isinstance(value, Mapping):
        _fail("invalid_type", "public document must be an object")
    schema_id = value.get("schema")
    if not isinstance(schema_id, str) or not schema_id:
        _fail("missing_schema_id", str(schema_id))
    descriptor = get_public_schema_descriptor(schema_id)
    resource = resources.files("sidinspector.schemas").joinpath(
        descriptor.schema_resource
    )
    schema_document = json.loads(resource.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema_document).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        _fail("structural_schema_violation", f"{location}: {error.message}")
    validator = _semantic_validators().get(descriptor.semantic_validator)
    if validator is None:
        _fail("missing_semantic_validator", descriptor.semantic_validator)
    try:
        validator(value)
    except PublicSchemaValidationError:
        raise
    except Exception as exc:
        code = getattr(exc, "code", "semantic_validation_error")
        detail = getattr(exc, "detail", str(exc))
        _fail(str(code), str(detail))
    return descriptor
