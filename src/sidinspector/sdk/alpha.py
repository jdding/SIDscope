"""Stable adapter capability contracts with the historical SDK 0.1 reader.

The module name is retained to avoid breaking pre-2.0 imports. Public users
import from :mod:`sidinspector.sdk`; the supported stable SDK version is 1.0.0.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from sidinspector.contracts import (
    METHOD_FAMILIES,
    METHOD_FAMILY_PAYLOAD_SCHEMAS,
    load_contract_registry,
    load_registered_contract,
    verify_content_sha256,
)


LEGACY_ADAPTER_CAPABILITIES_SCHEMA = "sidscope.adapter_capabilities.alpha.v1"
ADAPTER_CAPABILITIES_SCHEMA = "sidscope.adapter_capabilities.v1"
ADAPTER_SDK_VERSION = "1.0.0"
_SUPPORTED_API_VERSIONS = ("0.2.0", ADAPTER_SDK_VERSION)
ADAPTER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class AdapterSDKError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AdapterCapabilities:
    schema: str
    adapter_id: str
    method_family: str
    contract_types: tuple[str, ...]
    payload_schema: str | None
    telemetry_supported: tuple[str, ...]
    telemetry_unavailable: tuple[str, ...]
    runtime_requirements: tuple[str, ...]
    document: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.document))


class ArtifactProducer(Protocol):
    def produce(self, contract_type: str, output_path: Path) -> Path:
        """Produce one declared canonical artifact and return its path."""


def _fail(code: str, detail: str) -> None:
    raise AdapterSDKError(code, detail)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", field)
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail("invalid_type", field)
    result = tuple(_text(item, f"{field}[]") for item in value)
    if list(result) != sorted(set(result)):
        _fail("noncanonical_order", field)
    return result


def _version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        _fail("invalid_sdk_version", value)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _validate_legacy_capabilities(value: Mapping[str, Any]) -> AdapterCapabilities:
    fields = {
        "schema", "sdk_version", "adapter_id", "producer", "method_family",
        "contract_types", "telemetry", "execution_boundary", "content_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("descriptor_fields_mismatch", str(sorted(set(value) ^ fields)))
    if value.get("schema") != LEGACY_ADAPTER_CAPABILITIES_SCHEMA:
        _fail("schema_mismatch", str(value.get("schema")))
    if value.get("sdk_version") != "0.1.0":
        _fail("sdk_version_mismatch", str(value.get("sdk_version")))
    adapter_id = _text(value.get("adapter_id"), "adapter_id")
    if ADAPTER_ID_PATTERN.fullmatch(adapter_id) is None:
        _fail("invalid_adapter_id", adapter_id)
    producer = value.get("producer")
    if not isinstance(producer, Mapping) or set(producer) != {"name", "version"}:
        _fail("invalid_producer", adapter_id)
    _text(producer.get("name"), "producer.name")
    _text(producer.get("version"), "producer.version")
    method_family = _text(value.get("method_family"), "method_family")
    if method_family not in METHOD_FAMILIES:
        _fail("unsupported_method_family", method_family)
    contract_types = _strings(value.get("contract_types"), "contract_types")
    known_types = {item.contract_type for item in load_contract_registry().contracts}
    unknown = sorted(set(contract_types) - known_types)
    if unknown:
        _fail("unknown_contract_capability", str(unknown))
    telemetry = value.get("telemetry")
    if not isinstance(telemetry, Mapping) or set(telemetry) != {"supported", "unavailable"}:
        _fail("invalid_telemetry", adapter_id)
    supported = _strings(telemetry.get("supported"), "telemetry.supported")
    unavailable = _strings(telemetry.get("unavailable"), "telemetry.unavailable")
    overlap = sorted(set(supported).intersection(unavailable))
    if overlap:
        _fail("telemetry_overlap", str(overlap))
    if value.get("execution_boundary") != "external_runtime":
        _fail("execution_boundary_mismatch", str(value.get("execution_boundary")))
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", adapter_id)
    return AdapterCapabilities(
        LEGACY_ADAPTER_CAPABILITIES_SCHEMA,
        adapter_id,
        method_family,
        contract_types,
        None,
        supported,
        unavailable,
        (),
        dict(value),
    )


def _validate_v1_capabilities(value: Mapping[str, Any]) -> AdapterCapabilities:
    fields = {
        "schema", "schema_revision", "sdk_compatibility", "adapter_id", "producer",
        "method_family", "contract_types", "payload_schema", "telemetry",
        "execution_boundary", "runtime_requirements", "content_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("descriptor_fields_mismatch", str(sorted(set(value) ^ fields)))
    if value.get("schema") != ADAPTER_CAPABILITIES_SCHEMA:
        _fail("schema_mismatch", str(value.get("schema")))
    if value.get("schema_revision") != "1.0.0":
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    compatibility = value.get("sdk_compatibility")
    if not isinstance(compatibility, Mapping) or set(compatibility) != {"minimum", "maximum_exclusive"}:
        _fail("invalid_sdk_compatibility", str(compatibility))
    minimum = _text(compatibility.get("minimum"), "sdk_compatibility.minimum")
    maximum = _text(compatibility.get("maximum_exclusive"), "sdk_compatibility.maximum_exclusive")
    lower, upper = _version(minimum), _version(maximum)
    compatible = [version for version in _SUPPORTED_API_VERSIONS if lower <= _version(version) < upper]
    if not compatible:
        _fail("sdk_version_incompatible", f"{minimum} <= one of {_SUPPORTED_API_VERSIONS} < {maximum}")
    adapter_id = _text(value.get("adapter_id"), "adapter_id")
    if ADAPTER_ID_PATTERN.fullmatch(adapter_id) is None:
        _fail("invalid_adapter_id", adapter_id)
    producer = value.get("producer")
    if not isinstance(producer, Mapping) or set(producer) != {"name", "version"}:
        _fail("invalid_producer", adapter_id)
    _text(producer.get("name"), "producer.name")
    _text(producer.get("version"), "producer.version")
    method_family = _text(value.get("method_family"), "method_family")
    if method_family not in METHOD_FAMILIES:
        _fail("unsupported_method_family", method_family)
    contract_types = _strings(value.get("contract_types"), "contract_types")
    known_types = {item.contract_type for item in load_contract_registry().contracts}
    unknown = sorted(set(contract_types) - known_types)
    if unknown:
        _fail("unknown_contract_capability", str(unknown))
    payload_schema = _text(value.get("payload_schema"), "payload_schema")
    if METHOD_FAMILY_PAYLOAD_SCHEMAS[method_family] != payload_schema:
        _fail("payload_capability_mismatch", f"{method_family}->{payload_schema}")
    telemetry = value.get("telemetry")
    if not isinstance(telemetry, Mapping) or set(telemetry) != {"supported", "unavailable"}:
        _fail("invalid_telemetry", adapter_id)
    supported = _strings(telemetry.get("supported"), "telemetry.supported")
    unavailable = _strings(telemetry.get("unavailable"), "telemetry.unavailable")
    overlap = sorted(set(supported).intersection(unavailable))
    if overlap:
        _fail("telemetry_overlap", str(overlap))
    if value.get("execution_boundary") != "external_runtime":
        _fail("execution_boundary_mismatch", str(value.get("execution_boundary")))
    requirements = _strings(value.get("runtime_requirements"), "runtime_requirements")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", adapter_id)
    return AdapterCapabilities(
        ADAPTER_CAPABILITIES_SCHEMA,
        adapter_id,
        method_family,
        contract_types,
        payload_schema,
        supported,
        unavailable,
        requirements,
        dict(value),
    )


def validate_adapter_capabilities(value: Mapping[str, Any]) -> AdapterCapabilities:
    if not isinstance(value, Mapping):
        _fail("invalid_type", "adapter capabilities must be an object")
    if value.get("schema") == LEGACY_ADAPTER_CAPABILITIES_SCHEMA:
        return _validate_legacy_capabilities(value)
    return _validate_v1_capabilities(value)


def load_adapter_capabilities(path: Path) -> AdapterCapabilities:
    from sidinspector.contracts import load_json
    value = load_json(path)
    if not isinstance(value, Mapping):
        _fail("invalid_type", str(path))
    return validate_adapter_capabilities(value)


class AdapterHarness:
    """Fail-closed producer harness; it never imports an upstream runtime itself."""

    def __init__(self, capabilities: AdapterCapabilities, producer: ArtifactProducer) -> None:
        self.capabilities = capabilities
        self.producer = producer

    def produce(self, contract_type: str, output_path: Path) -> Any:
        if contract_type not in self.capabilities.contract_types:
            _fail("undeclared_contract_capability", contract_type)
        produced_path = self.producer.produce(contract_type, output_path)
        if produced_path != output_path:
            _fail("producer_output_mismatch", f"{produced_path} != {output_path}")
        _, artifact = load_registered_contract(contract_type, output_path)
        return artifact
