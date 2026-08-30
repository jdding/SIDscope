"""Versioned conformance profile discovery and deterministic composition."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Mapping, Sequence

from sidinspector.contracts.hashing import verify_content_sha256


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


def load_profile_registry() -> tuple[ConformanceProfile, ...]:
    path = resources.files("sidinspector.schemas").joinpath("conformance_profile_registry.v1.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != PROFILE_REGISTRY_SCHEMA:
        _fail("profile_registry_schema_mismatch", str(value.get("schema")))
    if set(value) != {"schema", "schema_revision", "profiles", "content_sha256"}:
        _fail("profile_registry_fields_mismatch", str(sorted(value)))
    if value.get("schema_revision") != "1.0.0":
        _fail("profile_registry_revision_mismatch", str(value.get("schema_revision")))
    if not verify_content_sha256(value):
        _fail("profile_registry_hash_mismatch", "conformance_profile_registry.v1.json")
    profiles: list[ConformanceProfile] = []
    for row in value.get("profiles", []):
        gates = tuple(
            GateDefinition(
                gate_id=gate["gate_id"],
                owner=gate["owner"],
                depends_on=tuple(gate["depends_on"]),
                failure_code=gate["failure_code"],
            )
            for gate in row["gates"]
        )
        profiles.append(
            ConformanceProfile(
                profile_id=row["profile_id"],
                revision=row["revision"],
                extends=tuple(row["extends"]),
                method_family=row["method_family"],
                gates=gates,
            )
        )
    if [profile.profile_id for profile in profiles] != sorted(profile.profile_id for profile in profiles):
        _fail("noncanonical_profile_order", str([profile.profile_id for profile in profiles]))
    return tuple(profiles)


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
