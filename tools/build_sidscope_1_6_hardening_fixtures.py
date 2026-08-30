#!/usr/bin/env python3
"""Build deterministic SIDScope 1.6 hardening evidence fixtures."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.cli import build_parser
from sidinspector.contracts import canonical_json_bytes, with_content_sha256
from sidinspector.evidence import validate_evidence_bundle


OUTPUT_ROOT = ROOT / "docs" / "reproducibility"
FIXTURE_ROOT = ROOT / "examples" / "compatibility_hardening_fixture"
PRODUCT_VERSION = "1.6.0.dev0"
PUBLIC_MODULES = (
    "sidinspector.contracts",
    "sidinspector.sdk",
    "sidinspector.adapters_core",
    "sidinspector.trace",
    "sidinspector.evaluation",
    "sidinspector.conformance_core",
    "sidinspector.evidence",
    "sidinspector.submission",
)
WRAPPER_OWNER = {
    "sidinspector.adapters": "adapter-compatibility-maintainer",
    "sidinspector.conformance": "conformance-compatibility-maintainer",
    "sidinspector.d7_trace": "trace-compatibility-maintainer",
    "sidinspector.interface": "sdk-compatibility-maintainer",
    "sidinspector.metrics": "evaluation-compatibility-maintainer",
    "sidinspector.preflight": "adapter-compatibility-maintainer",
    "sidinspector.trace_analysis": "trace-compatibility-maintainer",
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(with_content_sha256(document)) + b"\n")


def _cli_leaf_paths() -> list[str]:
    paths: list[str] = []

    def visit(parser: argparse.ArgumentParser, prefix: tuple[str, ...]) -> None:
        subparsers = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if not subparsers:
            paths.append(" ".join(prefix))
            return
        if len(subparsers) != 1:
            raise ValueError(f"ambiguous CLI parser at {' '.join(prefix)}")
        for name, child in sorted(subparsers[0].choices.items()):
            visit(child, (*prefix, name))

    visit(build_parser(), ())
    return paths


def build_compatibility_matrix() -> dict[str, Any]:
    return {
        "schema": "sidscope.compatibility_hardening_matrix.v1",
        "schema_revision": "1.0.0",
        "product_version": PRODUCT_VERSION,
        "historical_intervals": [
            {
                "interval": "1.0.2",
                "support_state": "frozen_tois_replay_only",
                "verification_mode": "immutable_tag_and_historical_verifier",
            },
            {
                "interval": "1.1.0",
                "support_state": "released_historical_replay",
                "verification_mode": "immutable_tag_archive_and_historical_verifier",
            },
            {
                "interval": "1.1.1.dev0",
                "support_state": "legacy_migration_baseline",
                "verification_mode": "hash_bound_route_authority_or_canonical_replay",
            },
            {
                "interval": ">=1.2.0.dev0,<2.0",
                "support_state": "pre_stable_canonical_development",
                "verification_mode": "current_contract_profile_plugin_and_bundle_gates",
            },
        ],
        "axes": [
            {
                "axis": "product_package",
                "supported": ["sidinspector import", "sidscope CLI", PRODUCT_VERSION],
                "positive_case": "installed_metadata_matches_pyproject_setup_and_cli",
                "typed_negative": "package_version_mismatch",
            },
            {
                "axis": "adapter_sdk",
                "supported": ["0.1.0", "0.2.0"],
                "positive_case": "legacy_and_current_capability_descriptors",
                "typed_negative": "sdk_version_incompatible",
            },
            {
                "axis": "canonical_schema",
                "supported": ["eleven contract registry entries at accepted revisions"],
                "positive_case": "all_canonical_and_negative_contract_fixtures",
                "typed_negative": "dependency_revision_incompatible",
            },
            {
                "axis": "conformance_profile",
                "supported": ["six legacy family profiles", "four governed admission profiles"],
                "positive_case": "legacy_composition_and_governed_report_validation",
                "typed_negative": "unknown_profile",
            },
            {
                "axis": "native_trace_payload",
                "supported": [
                    "autoregressive_prefix",
                    "parallel_graph_token_set",
                    "masked_diffusion",
                    "latent_retry",
                    "decoder_overlay",
                ],
                "positive_case": "registered_family_fixtures",
                "typed_negative": "unregistered_payload_schema",
            },
            {
                "axis": "evidence_bundle",
                "supported": ["sidscope.evidence_bundle.v1@1.0.0"],
                "positive_case": "compatible_cross_family_comparison",
                "typed_negative": "dataset_identity_mismatch",
            },
        ],
        "policy": {
            "development_versions_are_public_releases": False,
            "historical_objects_rewritten": False,
            "missing_legacy_bindings_fabricated": False,
            "typed_negative_required_per_axis": True,
        },
    }


def build_migration_records() -> tuple[dict[str, Any], dict[str, Any]]:
    source_path = OUTPUT_ROOT / "sidscope_1_2_legacy_migration_matrix.json"
    source = _read_json(source_path)
    records = []
    status_entries = []
    for row in source["routes"]:
        authority_path = ROOT / row["legacy_authority"]
        verifier_path = ROOT / row["legacy_verifier"]
        profile_id = (
            "overlay_g0_g5"
            if row["route_id"] == "isd"
            else "generator_g0_g5"
            if row["route_kind"] == "generator"
            else "static_mapping_c0_c5"
        )
        migration_state = (
            "canonical_replay_retained"
            if row["shared_1_2_disposition"] == "canonical_end_to_end_fixture_parity"
            else "immutable_historical_record"
        )
        record = {
            "route_id": row["route_id"],
            "route_kind": row["route_kind"],
            "legacy_status": row["legacy_status"],
            "profile_id": profile_id,
            "legacy_authority": {
                "path": row["legacy_authority"],
                "sha256": _file_sha256(authority_path),
            },
            "legacy_verifier": {
                "path": row["legacy_verifier"],
                "sha256": _file_sha256(verifier_path),
            },
            "migration_state": migration_state,
            "canonical_disposition": row["shared_1_2_disposition"],
            "missing_canonical_surfaces": row["missing_canonical_surfaces"],
            "status_equivalence_policy": row["status_equivalence_policy"],
            "retirement_or_archive_decision": (
                "retain_canonical_replay_and_legacy_verifier"
                if migration_state == "canonical_replay_retained"
                else "retain_hash_bound_history_until_canonical_regeneration"
            ),
        }
        records.append(record)
        status_entries.append(
            {
                "route_id": record["route_id"],
                "route_kind": record["route_kind"],
                "status": record["legacy_status"],
                "profile_id": profile_id,
                "migration_state": migration_state,
                "authority_sha256": record["legacy_authority"]["sha256"],
            }
        )
    migration = {
        "schema": "sidscope.legacy_migration_records.v1",
        "schema_revision": "1.0.0",
        "product_version": PRODUCT_VERSION,
        "source_matrix": {
            "path": str(source_path.relative_to(ROOT)),
            "sha256": _file_sha256(source_path),
        },
        "record_count": len(records),
        "records": records,
        "policy": {
            "legacy_authority_retained": True,
            "canonical_regeneration_may_be_inferred": False,
            "historical_status_may_be_promoted": False,
        },
    }
    status_index = {
        "schema": "sidscope.legacy_migration_status_index.v1",
        "schema_revision": "1.0.0",
        "authority": "sidscope.legacy_migration_records.v1",
        "entries": sorted(status_entries, key=lambda item: item["route_id"]),
    }
    return migration, status_index


def build_api_inventory() -> dict[str, Any]:
    dependency_matrix = _read_json(
        OUTPUT_ROOT / "sidscope_module_dependencies.json"
    )
    wrappers = []
    for module_name in dependency_matrix["legacy_compatibility_modules"]:
        wrappers.append(
            {
                "module": module_name,
                "owner": WRAPPER_OWNER[module_name],
                "support_interval": ">=1.1.1.dev0,<3.0",
                "lifecycle": "historical_replay_compatibility",
                "retirement_or_archive_decision": "archive_for_1.x_and_2.x_replay; reconsider_for_3.0",
            }
        )
    public_modules = []
    for module_name in PUBLIC_MODULES:
        module = importlib.import_module(module_name)
        symbols = sorted(getattr(module, "__all__", ()))
        if not symbols:
            raise ValueError(f"{module_name} has no explicit __all__")
        public_modules.append(
            {
                "module": module_name,
                "owner": "sidscope-core-maintainers",
                "stability": "2.0_candidate",
                "public_symbols": symbols,
            }
        )
    return {
        "schema": "sidscope.public_api_inventory.v1",
        "schema_revision": "1.0.0",
        "product_version": PRODUCT_VERSION,
        "python_modules": public_modules,
        "cli": {
            "command": "sidscope",
            "owner": "sidscope-core-maintainers",
            "stability": "2.0_candidate",
            "leaf_commands": _cli_leaf_paths(),
        },
        "compatibility_wrappers": wrappers,
        "policy": {
            "removal_before_2_0_allowed": False,
            "undocumented_breaking_change_allowed": False,
            "method_or_training_api_in_scope": False,
        },
    }


def build_cross_family_fixtures() -> tuple[dict[str, Any], dict[str, Any]]:
    baseline = _read_json(
        ROOT / "examples" / "evidence_system_fixture" / "baseline_bundle.json"
    )
    bundles = []
    for family, adapter_id, hit, ndcg, nfe in (
        ("parallel_graph_token_set", "external-parallel-fixture", 0.20, 0.10, 10),
        ("masked_diffusion", "external-masked-fixture", 0.24, 0.12, 20),
    ):
        bundle = copy.deepcopy(baseline)
        bundle["bundle_id"] = f"fixture:1.6:{family}"
        bundle["producer"] = {"name": "sidscope.1.6.fixture-builder", "version": PRODUCT_VERSION}
        bundle["profile_binding"]["profile_id"] = "generator_g0_g5"
        bundle["subject"] = {"adapter_id": adapter_id, "method_family": family}
        bundle["result_card"]["overall_metrics"] = {
            "hit_at_10": hit,
            "ndcg_at_10": ndcg,
        }
        bundle["result_card"]["slice_metrics"]["overall"] = {
            "hit_at_10": hit,
            "ndcg_at_10": ndcg,
        }
        bundle["result_card"]["compute"]["nfe"] = nfe
        bundle = with_content_sha256(bundle)
        validate_evidence_bundle(bundle)
        bundles.append(bundle)
    return bundles[0], bundles[1]


def build() -> dict[str, Any]:
    compatibility = build_compatibility_matrix()
    migration, status_index = build_migration_records()
    api_inventory = build_api_inventory()
    parallel, masked = build_cross_family_fixtures()
    outputs = {
        OUTPUT_ROOT / "sidscope_1_6_compatibility_matrix.json": compatibility,
        OUTPUT_ROOT / "sidscope_1_6_legacy_migration_records.json": migration,
        OUTPUT_ROOT / "sidscope_1_6_legacy_status_index.json": status_index,
        OUTPUT_ROOT / "sidscope_1_6_public_api_inventory.json": api_inventory,
        FIXTURE_ROOT / "parallel_graph_bundle.json": parallel,
        FIXTURE_ROOT / "masked_diffusion_bundle.json": masked,
    }
    for path, document in outputs.items():
        _write(path, document)
    return {
        "schema": "sidscope.1_6_fixture_build.v1",
        "status": "pass",
        "output_count": len(outputs),
        "outputs": [str(path.relative_to(ROOT)) for path in outputs],
    }


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
