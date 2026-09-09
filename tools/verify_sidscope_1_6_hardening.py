#!/usr/bin/env python3
"""Verify SIDScope 1.6 compatibility, migration, and adoption hardening."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.cli import build_parser
from sidinspector.contracts import (
    canonical_json_bytes,
    load_contract_registry,
    verify_content_sha256,
    with_content_sha256,
)
from sidinspector.conformance_core import (
    ProfileCompositionError,
    compose_profiles,
    load_profile_catalog,
    load_profile_registry,
)
from sidinspector.evidence import validate_evidence_bundle
from sidinspector.evidence.comparison import compare_legacy_evidence_bundles as compare_evidence_bundles
from sidinspector.sdk import (
    AdapterSDKError,
    load_adapter_capabilities,
    validate_adapter_capabilities,
)
from sidinspector.trace import (
    NativePayloadValidationError,
    load_native_payload,
    load_native_payload_registry,
    validate_native_payload,
)

from build_sidscope_1_6_hardening_fixtures import (
    PRODUCT_VERSION,
    PUBLIC_MODULES,
    WRAPPER_OWNER,
    build_compatibility_matrix,
    build_cross_family_fixtures,
    build_migration_records,
)
from verify_sidscope_1_3_plugin_ecosystem import verify_ecosystem
from verify_sidscope_release_metadata import verify_release_metadata


REPRO = ROOT / "docs" / "reproducibility"
FIXTURES = ROOT / "examples" / "compatibility_hardening_fixture"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        if "__pycache__" in item.parts:
            continue
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _assert_tracked_document(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    actual = _read_json(path)
    if not verify_content_sha256(actual):
        raise AssertionError(f"content hash mismatch: {path}")
    expected_hashed = with_content_sha256(expected)
    if canonical_json_bytes(actual) != canonical_json_bytes(expected_hashed):
        raise AssertionError(f"tracked hardening artifact is stale: {path}")
    return actual


def verify_compatibility() -> dict[str, Any]:
    matrix = _assert_tracked_document(
        REPRO / "sidscope_1_6_compatibility_matrix.json",
        build_compatibility_matrix(),
    )
    if [row["axis"] for row in matrix["axes"]] != [
        "product_package",
        "adapter_sdk",
        "canonical_schema",
        "conformance_profile",
        "native_trace_payload",
        "evidence_bundle",
    ]:
        raise AssertionError("compatibility axes changed")
    metadata = verify_release_metadata()
    active_version = metadata["package_version"]
    if re.fullmatch(r"1\.(?:6|7|8|9)\.0\.dev0", active_version) is None:
        raise AssertionError(
            f"1.6 historical hardening replay is unsupported on {active_version}"
        )

    legacy = load_adapter_capabilities(
        ROOT / "examples" / "canonical_pipeline_fixture" / "adapter_capabilities.json"
    )
    current = load_adapter_capabilities(
        ROOT / "examples" / "native_trace_payload_fixtures" / "adapter_capabilities.v1.json"
    )
    invalid_sdk = current.to_dict()
    invalid_sdk["sdk_compatibility"] = {
        "minimum": "0.1.0",
        "maximum_exclusive": "0.2.0",
    }
    try:
        validate_adapter_capabilities(invalid_sdk)
    except AdapterSDKError as error:
        if error.code != "sdk_version_incompatible":
            raise AssertionError(error.code) from error
    else:
        raise AssertionError("incompatible SDK interval passed")

    contracts = load_contract_registry(repository_root=ROOT)
    if len(contracts.contracts) != 11:
        raise AssertionError("canonical contract count changed")
    legacy_profiles = load_profile_registry()
    governed_profiles = load_profile_catalog()
    try:
        compose_profiles(["unknown.1.6.profile"])
    except ProfileCompositionError as error:
        if error.code != "unknown_profile":
            raise AssertionError(error.code) from error
    else:
        raise AssertionError("unknown profile passed")

    payloads = load_native_payload_registry()
    for descriptor in payloads:
        load_native_payload(ROOT / descriptor.canonical_fixture)
    invalid_payload = _read_json(
        ROOT / "examples" / "native_trace_payload_fixtures" / "masked_diffusion.json"
    )
    invalid_payload["schema"] = "sidscope.trace_payload.unknown.v1"
    invalid_payload = with_content_sha256(invalid_payload)
    try:
        validate_native_payload(invalid_payload)
    except NativePayloadValidationError as error:
        if error.code != "unregistered_payload_schema":
            raise AssertionError(error.code) from error
    else:
        raise AssertionError("unregistered payload passed")

    left = _read_json(FIXTURES / "parallel_graph_bundle.json")
    right = _read_json(FIXTURES / "masked_diffusion_bundle.json")
    if compare_evidence_bundles(left, right)["status"] != "compatible":
        raise AssertionError("positive bundle compatibility failed")
    incompatible = copy.deepcopy(right)
    incompatible["compatibility"]["dataset_identity_sha256"] = "f" * 64
    incompatible = with_content_sha256(incompatible)
    comparison = compare_evidence_bundles(left, incompatible)
    reasons = comparison["contract_compatibility"]["reasons"]
    if comparison["status"] != "incompatible" or [row["code"] for row in reasons] != [
        "dataset_identity_mismatch"
    ]:
        raise AssertionError(comparison)
    return {
        "axis_count": len(matrix["axes"]),
        "typed_negative_count": len(matrix["axes"]),
        "legacy_sdk_schema": legacy.schema,
        "current_sdk_schema": current.schema,
        "contract_count": len(contracts.contracts),
        "legacy_profile_count": len(legacy_profiles),
        "governed_profile_count": len(governed_profiles),
        "payload_family_count": len(payloads),
    }


def verify_migration() -> dict[str, Any]:
    expected_records, expected_index = build_migration_records()
    records = _assert_tracked_document(
        REPRO / "sidscope_1_6_legacy_migration_records.json", expected_records
    )
    index = _assert_tracked_document(
        REPRO / "sidscope_1_6_legacy_status_index.json", expected_index
    )
    if records["record_count"] != 15 or len(index["entries"]) != 15:
        raise AssertionError("legacy route count changed")
    replayable = sum(
        row["migration_state"] == "canonical_replay_retained"
        for row in records["records"]
    )
    historical = records["record_count"] - replayable
    return {
        "record_count": records["record_count"],
        "canonical_replay_count": replayable,
        "immutable_historical_record_count": historical,
        "status_index_sha256": index["content_sha256"],
        "legacy_status_parity": "pass",
    }


def verify_adoption() -> dict[str, Any]:
    guide = (ROOT / "docs" / "CONTRIBUTING_ADAPTERS.md").read_text(encoding="utf-8")
    for token in (
        "examples/reference_adapter_plugin",
        "sidscope plugin list",
        "sidscope plugin preflight",
        "without core edits",
    ):
        if token not in guide:
            raise AssertionError(f"public onboarding guide missing: {token}")
    before = _tree_sha256(ROOT / "src" / "sidinspector")
    result = verify_ecosystem()
    after = _tree_sha256(ROOT / "src" / "sidinspector")
    if before != after:
        raise AssertionError("external onboarding modified SIDScope core")
    return {
        "external_adapter_id": result["external_reference_plugin"],
        "entry_point_group": result["entry_point_group"],
        "core_sha256_before": before,
        "core_sha256_after": after,
        "public_documentation_replay": "pass",
    }


def verify_comparison() -> dict[str, Any]:
    expected_left, expected_right = build_cross_family_fixtures()
    left = _assert_tracked_document(
        FIXTURES / "parallel_graph_bundle.json", expected_left
    )
    right = _assert_tracked_document(FIXTURES / "masked_diffusion_bundle.json", expected_right)
    result = compare_evidence_bundles(left, right)
    if result["status"] != "compatible":
        raise AssertionError(result)
    if left["subject"]["method_family"] == right["subject"]["method_family"]:
        raise AssertionError("comparison does not span method families")
    return {
        "status": result["status"],
        "left_family": left["subject"]["method_family"],
        "right_family": right["subject"]["method_family"],
        "shared_contract": result["contract_compatibility"]["shared_contract"],
        "metric_deltas": result["method_difference"]["overall_metrics"],
    }


def verify_api() -> dict[str, Any]:
    inventory = _read_json(REPRO / "sidscope_1_6_public_api_inventory.json")
    if not verify_content_sha256(inventory):
        raise AssertionError("1.6 public API inventory content hash mismatch")
    if inventory.get("product_version") != PRODUCT_VERSION:
        raise AssertionError("1.6 public API inventory version mismatch")
    observed_modules = [row["module"] for row in inventory["python_modules"]]
    if observed_modules != list(PUBLIC_MODULES):
        raise AssertionError("historical 1.6 Python module inventory changed")
    dependency = _read_json(REPRO / "sidscope_module_dependencies.json")
    wrappers = inventory["compatibility_wrappers"]
    if [row["module"] for row in wrappers] != dependency["legacy_compatibility_modules"]:
        raise AssertionError("compatibility wrapper inventory mismatch")
    for row in wrappers:
        if row["owner"] != WRAPPER_OWNER[row["module"]] or not row[
            "retirement_or_archive_decision"
        ]:
            raise AssertionError(f"unowned compatibility wrapper: {row}")
    return {
        "public_module_count": len(observed_modules),
        "public_symbol_count": sum(len(row["public_symbols"]) for row in inventory["python_modules"]),
        "cli_leaf_command_count": len(inventory["cli"]["leaf_commands"]),
        "owned_wrapper_count": len(wrappers),
    }


GATES: dict[str, Callable[[], dict[str, Any]]] = {
    "compatibility": verify_compatibility,
    "migration": verify_migration,
    "adoption": verify_adoption,
    "comparison": verify_comparison,
    "api": verify_api,
}


def verify(gate: str = "all") -> dict[str, Any]:
    selected = GATES if gate == "all" else {gate: GATES[gate]}
    return {
        "schema": "sidscope.1_6_hardening_verification.v1",
        "status": "pass",
        "product_version": PRODUCT_VERSION,
        "gate": gate,
        "gpu_required": False,
        "sections": {name: function() for name, function in selected.items()},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=("all", *GATES), default="all")
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args.gate)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
