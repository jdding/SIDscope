"""Versioned conformance profile discovery and deterministic composition."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Mapping, Sequence

from sidinspector.contracts.hashing import verify_content_sha256
from sidinspector.contracts.method_families import METHOD_FAMILIES


PROFILE_REGISTRY_SCHEMA = "sidscope.conformance_profile_registry.v1"


class ProfileCompositionError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class GateDefinition:
    gate_id: str
    owner: str
    depends_on: tuple[str, ...]
    failure_code: str


@dataclass(frozen=True)
class ConformanceProfile:
    profile_id: str
    revision: str
    extends: tuple[str, ...]
    method_family: str | None
    gates: tuple[GateDefinition, ...]


@dataclass(frozen=True)
class ComposedProfile:
    profile_ids: tuple[str, ...]
    gates: tuple[GateDefinition, ...]


def _fail(code: str, detail: str) -> None:
    raise ProfileCompositionError(code, detail)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_profile_value", field)
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail("invalid_profile_type", field)
    result = tuple(_text(item, f"{field}[]") for item in value)
    if list(result) != sorted(set(result)):
        _fail("noncanonical_profile_order", field)
    return result


def validate_profile_registry(value: Mapping[str, Any]) -> tuple[ConformanceProfile, ...]:
    if not isinstance(value, Mapping):
        _fail("invalid_profile_type", "registry must be an object")
    if value.get("schema") != PROFILE_REGISTRY_SCHEMA:
        _fail("profile_registry_schema_mismatch", str(value.get("schema")))
    if set(value) != {"schema", "schema_revision", "profiles", "content_sha256"}:
        _fail("profile_registry_fields_mismatch", str(sorted(value)))
    if value.get("schema_revision") != "1.0.0":
        _fail("profile_registry_revision_mismatch", str(value.get("schema_revision")))
    if not verify_content_sha256(value):
        _fail("profile_registry_hash_mismatch", "conformance_profile_registry.v1.json")
    rows = value.get("profiles")
    if not isinstance(rows, list) or not rows:
        _fail("invalid_profile_type", "profiles")
    profiles: list[ConformanceProfile] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != {
            "profile_id", "revision", "extends", "method_family", "gates"
        }:
            _fail("profile_registry_row_mismatch", str(index))
        gates_raw = row.get("gates")
        if not isinstance(gates_raw, list) or not gates_raw:
            _fail("invalid_profile_type", f"profiles[{index}].gates")
        gates: list[GateDefinition] = []
        for gate_index, gate in enumerate(gates_raw):
            if not isinstance(gate, Mapping) or set(gate) != {
                "gate_id", "owner", "depends_on", "failure_code"
            }:
                _fail("profile_gate_fields_mismatch", f"{index}:{gate_index}")
            gates.append(
                GateDefinition(
                    gate_id=_text(gate.get("gate_id"), "gate_id"),
                    owner=_text(gate.get("owner"), "owner"),
                    depends_on=_strings(gate.get("depends_on"), "depends_on"),
                    failure_code=_text(gate.get("failure_code"), "failure_code"),
                )
            )
        gate_ids = [gate.gate_id for gate in gates]
        if len(gate_ids) != len(set(gate_ids)):
            _fail("duplicate_profile_gate", str(gate_ids))
        method_family = row.get("method_family")
        if method_family is not None:
            method_family = _text(method_family, "method_family")
            if method_family not in METHOD_FAMILIES:
                _fail("unsupported_method_family", method_family)
        profiles.append(
            ConformanceProfile(
                profile_id=_text(row.get("profile_id"), "profile_id"),
                revision=_text(row.get("revision"), "revision"),
                extends=_strings(row.get("extends"), "extends"),
                method_family=method_family,
                gates=tuple(gates),
            )
        )
    profile_ids = [profile.profile_id for profile in profiles]
    if profile_ids != sorted(set(profile_ids)):
        _fail("noncanonical_profile_order", str([profile.profile_id for profile in profiles]))
    known = set(profile_ids)
    for profile in profiles:
        unknown = sorted(set(profile.extends) - known)
        if unknown:
            _fail("unknown_profile_extension", f"{profile.profile_id}: {unknown}")
    return tuple(profiles)


def load_profile_registry() -> tuple[ConformanceProfile, ...]:
    path = resources.files("sidinspector.schemas").joinpath("conformance_profile_registry.v1.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("invalid_profile_type", "registry must be an object")
    return validate_profile_registry(value)


def compose_profiles(profile_ids: Sequence[str]) -> ComposedProfile:
    registry = {profile.profile_id: profile for profile in load_profile_registry()}
    requested = tuple(sorted(set(profile_ids)))
    if not requested:
        _fail("empty_profile_composition", "profile_ids")
    selected: set[str] = set()

    def include(profile_id: str, stack: tuple[str, ...] = ()) -> None:
        if profile_id in stack:
            _fail("profile_extension_cycle", " -> ".join((*stack, profile_id)))
        profile = registry.get(profile_id)
        if profile is None:
            _fail("unknown_profile", profile_id)
        for parent in profile.extends:
            include(parent, (*stack, profile_id))
        selected.add(profile_id)

    for profile_id in requested:
        include(profile_id)
    method_families = {
        registry[profile_id].method_family
        for profile_id in selected
        if registry[profile_id].method_family is not None
    }
    if len(method_families) > 1:
        _fail("conflicting_method_families", str(sorted(method_families)))
    gates: dict[str, GateDefinition] = {}
    for profile_id in sorted(selected):
        for gate in registry[profile_id].gates:
            existing = gates.get(gate.gate_id)
            if existing is not None and existing != gate:
                _fail("conflicting_gate_definition", gate.gate_id)
            gates[gate.gate_id] = gate
    for gate in gates.values():
        missing = sorted(set(gate.depends_on) - set(gates))
        if missing:
            _fail("missing_gate_dependency", f"{gate.gate_id}: {missing}")
    ordered: list[GateDefinition] = []
    remaining = dict(gates)
    while remaining:
        ready = sorted(
            gate_id
            for gate_id, gate in remaining.items()
            if set(gate.depends_on).issubset(item.gate_id for item in ordered)
        )
        if not ready:
            _fail("gate_dependency_cycle", str(sorted(remaining)))
        for gate_id in ready:
            ordered.append(remaining.pop(gate_id))
    return ComposedProfile(tuple(sorted(selected)), tuple(ordered))


def composed_profile_document(profile_ids: Sequence[str]) -> dict[str, Any]:
    composed = compose_profiles(profile_ids)
    return {
        "schema": "sidscope.composed_conformance_profile.v1",
        "status": "pass",
        "profile_ids": list(composed.profile_ids),
        "gates": [
            {
                "gate_id": gate.gate_id,
                "owner": gate.owner,
                "depends_on": list(gate.depends_on),
                "failure_code": gate.failure_code,
            }
            for gate in composed.gates
        ],
    }
