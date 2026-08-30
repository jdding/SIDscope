#!/usr/bin/env python3
"""Build the deterministic SIDScope schema/profile/evidence architecture inventory."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


if str(Path(__file__).resolve().parents[1] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sidinspector.contracts import load_contract_registry
from sidinspector.conformance_core import load_profile_registry


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "reproducibility" / "sidscope_architecture_inventory.json"
RELEASE_MANIFEST = ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"
SCHEMA_PATTERN = re.compile(r"\bsidscope\.[A-Za-z0-9_.-]+\.v[0-9]+\b")
TEXT_SUFFIXES = {".csv", ".json", ".md", ".py", ".toml", ".txt"}
SCAN_EXCLUDES = {
    "docs/reproducibility/sidscope_architecture_inventory.json",
}


def _public_paths() -> list[Path]:
    with RELEASE_MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    paths: set[Path] = set()
    for row in rows:
        if row.get("public_package", "").strip().lower() != "yes":
            continue
        root = ROOT / row["path"].strip()
        if root.is_file():
            paths.add(root)
        elif root.is_dir():
            paths.update(path for path in root.rglob("*") if path.is_file())
    return sorted(paths)


def _schema_owner(schema_id: str) -> str:
    prefix = schema_id.removeprefix("sidscope.").split(".", 1)[0]
    adapter_owners = {
        "dact_tiger": "adapter:dact_tiger",
        "diffgrm": "adapter:diffgrm",
        "isd": "adapter:isd",
        "latte": "adapter:latte_psid",
        "latte_psid": "adapter:latte_psid",
        "llada_rec": "adapter:llada_rec",
        "rpg": "adapter:rpg",
    }
    if prefix in adapter_owners:
        return adapter_owners[prefix]
    if prefix in {
        "source_identity",
        "dataset_identity",
        "sid_space_identity",
        "prepared_dataset",
        "episode_selection",
        "run_identity",
        "checkpoint_binding",
        "trace_envelope",
        "evidence_index",
        "contract_registry",
        "contract_validation",
        "module_dependency_matrix",
    }:
        return "core:contracts"
    if prefix in {"adapter_capabilities", "adapter_fixture_manifest"}:
        return "core:sdk"
    if prefix.startswith("trace_payload") or prefix == "native_payload_validation":
        return "core:trace"
    if prefix in {"conformance_profile_registry", "composed_conformance_profile"}:
        return "core:conformance"
    if prefix in {
        "adapter_conformance_report",
        "adapter_manifest",
        "generator_adapter_coverage",
        "generator_source_audit",
        "source_license_config_inventory",
    }:
        return "core:conformance"
    if prefix in {
        "g8_fresh_env_smoke",
        "public_url_smoke",
        "release_archive_smoke",
        "release_candidate_archive",
        "release_metadata_verification",
        "resource_package_verification",
        "sampled_regeneration",
        "architecture_inventory",
        "architecture_inventory_verification",
    }:
        return "core:release"
    return "core:diagnostics"


def _path_kind(rel_path: str) -> str:
    name = Path(rel_path).name
    if rel_path.startswith("tests/") or (
        rel_path.startswith("tools/") and name.startswith("verify_")
    ):
        return "verifier"
    if rel_path.startswith(("src/", "tools/")):
        return "producer"
    return "artifact"


def schema_inventory() -> list[dict[str, Any]]:
    occurrences: dict[str, set[str]] = {}
    for path in _public_paths():
        rel_path = path.relative_to(ROOT).as_posix()
        if rel_path in SCAN_EXCLUDES or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for schema_id in SCHEMA_PATTERN.findall(text):
            occurrences.setdefault(schema_id, set()).add(rel_path)

    records: list[dict[str, Any]] = []
    for schema_id, paths in sorted(occurrences.items()):
        declarations = sorted(paths)
        records.append(
            {
                "schema_id": schema_id,
                "owner": _schema_owner(schema_id),
                "lifecycle": "active_or_historical_legacy_authority",
                "declaration_paths": declarations,
                "producer_paths": [path for path in declarations if _path_kind(path) == "producer"],
                "verifier_paths": [path for path in declarations if _path_kind(path) == "verifier"],
                "artifact_paths": [path for path in declarations if _path_kind(path) == "artifact"],
            }
        )
    return records


def generator_routes() -> list[dict[str, str]]:
    path = ROOT / "docs" / "reproducibility" / "generator_adapter_coverage.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "route_id": row["route_id"],
            "profile": "generator_g0_g5",
            "adapter_kind": row["adapter_kind"],
            "status": row["current_decision"],
            "contract_state": row["contract_state"],
            "authority_path": row["evidence_path"],
            "owner": f"adapter:{row['route_id']}",
            "migration_state": "legacy_authority",
        }
        for row in rows
    ]


def static_mapping_routes() -> list[dict[str, str]]:
    path = ROOT / "docs" / "reproducibility" / "sidscope_source_license_config_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "route_id": row["route_id"],
            "profile": "static_mapping_c0_c5",
            "status": row["conformance_status"],
            "authority_path": row["conformance_evidence"],
            "owner": f"adapter:{row['route_id']}",
            "migration_state": "legacy_authority",
        }
        for row in rows
    ]


def package_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = text.split("[project]", 1)[1].split("[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"', project, re.MULTILINE)
    if match is None:
        raise RuntimeError("cannot parse project.version")
    return match.group(1)


def build_inventory() -> dict[str, Any]:
    schemas = schema_inventory()
    registry = load_contract_registry(repository_root=ROOT)
    native_profiles = load_profile_registry()
    return {
        "schema": "sidscope.architecture_inventory.v1",
        "status": "pass",
        "scope": "public_release_manifest_plus_active_route_ledgers",
        "product_version": package_version(),
        "version_axes": {
            "product_package": package_version(),
            "adapter_sdk": "0.2.0-alpha",
            "canonical_schemas": [
                f"{descriptor.schema_id}@{descriptor.schema_revision}"
                for descriptor in registry.contracts
            ],
            "conformance_profiles": [
                "static_mapping_c0_c5", "generator_g0_g5", "release_local",
                *[f"{profile.profile_id}@{profile.revision}" for profile in native_profiles],
            ],
            "evidence_bundle": "canonical_evidence_index_v1_plus_route_specific_legacy_authorities",
        },
        "profiles": [
            {
                "profile_id": "static_mapping_c0_c5",
                "owner": "core:conformance",
                "authority": "docs/ADAPTER_CONFORMANCE.md",
                "verifier": "tools/verify_adapter_conformance_assets.py",
                "migration_state": "legacy_authority",
            },
            {
                "profile_id": "generator_g0_g5",
                "owner": "core:conformance",
                "authority": "docs/GENERATOR_ADAPTER_CONFORMANCE.md",
                "verifier": "docs/reproducibility/generator_adapter_coverage.csv",
                "migration_state": "legacy_authority",
            },
            {
                "profile_id": "release_local",
                "owner": "core:release",
                "authority": "docs/SIDSCOPE_RELEASE_CHECKLIST.md",
                "verifier": "tools/verify_sidscope_resource_package.py",
                "migration_state": "active",
            },
            *[
                {
                    "profile_id": profile.profile_id,
                    "owner": "core:conformance",
                    "authority": "src/sidinspector/schemas/conformance_profile_registry.v1.json",
                    "verifier": "tools/verify_sidscope_1_3_plugin_ecosystem.py",
                    "migration_state": "active",
                }
                for profile in native_profiles
            ],
        ],
        "schema_count": len(schemas),
        "schemas": schemas,
        "canonical_contract_registry": {
            "registry_id": registry.registry_id,
            "schema": registry.schema,
            "schema_revision": registry.schema_revision,
            "content_sha256": registry.content_sha256,
            "contract_count": len(registry.contracts),
            "contracts": [descriptor.to_dict() for descriptor in registry.contracts],
        },
        "routes": {
            "generator": generator_routes(),
            "static_mapping": static_mapping_routes(),
        },
        "canonical_evidence_edges": [
            {"from": "PreparedDataset", "to": "DatasetIdentity", "status": "implemented"},
            {"from": "PreparedDataset", "to": "SIDSpaceIdentity", "status": "implemented"},
            {"from": "EpisodeSelection", "to": "PreparedDataset", "status": "implemented"},
            {"from": "RunIdentity", "to": "PreparedDataset", "status": "implemented"},
            {"from": "RunIdentity", "to": "SourceIdentity", "status": "implemented"},
            {"from": "CheckpointBinding", "to": "RunIdentity", "status": "implemented"},
            {"from": "TraceEnvelope", "to": "EpisodeSelection", "status": "implemented"},
            {"from": "TraceEnvelope", "to": "RunIdentity", "status": "implemented"},
            {"from": "TraceEnvelope", "to": "CheckpointBinding", "status": "implemented"},
            {"from": "DiagnosticReport", "to": "TraceEnvelope", "status": "implemented"},
            {"from": "DiagnosticReport", "to": "EpisodeSelection", "status": "implemented"},
            {"from": "ConformanceReport", "to": "TraceEnvelope", "status": "implemented"},
            {"from": "ConformanceReport", "to": "DiagnosticReport", "status": "implemented"},
            {"from": "EvidenceIndex", "to": "ConformanceReport", "status": "implemented"},
        ],
        "module_dependency_matrix": "docs/reproducibility/sidscope_module_dependencies.json",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stdout", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.dumps(build_inventory(), indent=2, sort_keys=True) + "\n"
    if not args.stdout:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
