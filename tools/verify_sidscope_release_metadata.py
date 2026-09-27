#!/usr/bin/env python3
"""Verify package, CLI, version-governance, and release-template consistency."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parents[1] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sidinspector.contracts import load_contract_registry
from sidinspector.conformance_core import load_profile_catalog
from sidinspector.sdk import ADAPTER_SDK_VERSION
from sidinspector.version import PRODUCT_VERSION


ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = "sidscope.release_metadata_verification.v1"


def _quoted_value(text: str, key: str) -> str:
    match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise ValueError(f"cannot find {key}")
    return match.group(1)


def verify_release_metadata(root: Path = ROOT) -> dict[str, Any]:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    project = pyproject.split("[project]", 1)[1].split("[", 1)[0]
    setup = (root / "setup.py").read_text(encoding="utf-8")
    project_name = _quoted_value(project, "name")
    project_version = _quoted_value(project, "version")
    setup_name = _quoted_value(setup, "name")
    setup_version = _quoted_value(setup, "version")
    if (project_name, project_version) != (setup_name, setup_version):
        raise ValueError(
            "pyproject/setup metadata mismatch: "
            f"{project_name}=={project_version} != {setup_name}=={setup_version}"
        )
    if project_version != PRODUCT_VERSION:
        raise ValueError(
            f"runtime/package version mismatch: {PRODUCT_VERSION} != {project_version}"
        )
    if 'sidscope = "sidinspector.cli:main"' not in pyproject:
        raise ValueError("pyproject missing the sidscope console facade")
    if '"sidscope=sidinspector.cli:main"' not in setup:
        raise ValueError("setup.py missing the sidscope console facade")
    if 'sidinspector = ["schemas/*.json"]' not in pyproject:
        raise ValueError("pyproject missing bundled JSON schemas")
    if 'package_data={"sidinspector": ["schemas/*.json"]}' not in setup:
        raise ValueError("setup.py missing bundled JSON schemas")

    required_docs = {
        "docs/SIDSCOPE_SDLC_HARDENING.md": ["diagnostics_verified", "baseline", "sidscope_sdlc_requirements.csv", "no maintainer sign-off", "diagnostics_from_supplied_trace"],
        "docs/adr/0016-quarantine-unverified-admission.md": ["independent_gate_verification_required", "## Exit and rollback", "structure_only"],
        "README.md": ["docs/VERSIONING.md", "docs/COMPATIBILITY.md"],
        "docs/VERSIONING.md": ["five independent compatibility axes", "GitHub Release"],
        "docs/COMPATIBILITY.md": [
            project_version,
            "sidscope.source_identity.v1",
            "sidscope.dataset_identity.v1",
            "sidscope.sid_space_identity.v1",
            "sidscope.prepared_dataset.v1",
            "1.0.0",
            "sidscope.trace_payload.masked_diffusion.v1",
        ],
        "docs/SIDSCOPE_RELEASE_TEMPLATE.md": ["Adapter SDK version:", "archive SHA-256:"],
        "docs/SIDSCOPE_RELEASE_CHECKLIST.md": ["docs/SIDSCOPE_RELEASE_TEMPLATE.md"],
        "docs/CONFORMANCE_AND_SUBMISSION_ECOSYSTEM.md": [
            "sidscope.dataset_profile_descriptor.v1",
            "sidscope.profile_conformance_report.v1",
            "sidscope.evidence_submission.v1",
            "sidscope submission check",
        ],
        "docs/CONFORMANCE_PROFILE_GOVERNANCE.md": [
            "Semantic Versioning",
            "Status Derivation",
        ],
        "docs/CODE_OWNERSHIP.md": [
            "Canonical contracts and schemas",
            "Conformance profiles and reports",
            "Release manifests",
        ],
        "docs/SIDSCOPE_1_6_HARDENING.md": [
            "sidscope_1_6_compatibility_matrix.json",
            "sidscope_1_6_legacy_migration_records.json",
            "sidscope_1_6_public_api_inventory.json",
            "without core edits",
        ],
        "docs/SIDSCOPE_1_7_STABILIZATION.md": [
            "sidscope schema validate",
            "sidscope_1_7_public_surface.json",
            "Draft 2020-12",
            "Python semantic",
        ],
        "docs/SIDSCOPE_RELEASE_PROFILES.md": [
            "runtime < conformance < evidence-full",
            "sidscope-release-profile.json",
            "A profile change is a release-surface change inside 1.7",
        ],
        "docs/adr/0014-tiered-release-profiles.md": [
            "one repository",
            "generated deterministic",
            "Rollback",
        ],
        "docs/adr/0015-separate-public-maintenance-development-and-tois-lines.md": [
            "public GitHub `main` is the 1.1.x maintenance line",
            "Local commits do not imply publication",
            "future authorized TOIS revision",
        ],
        "docs/MIGRATING_1_X_TO_2_0.md": [
            "immutable_historical_record",
            "canonical_replay_retained",
            "Never modify frozen TOIS software",
        ],
        "docs/ADAPTER_SDK.md": [
            "Adapter SDK `1.0.0`",
            "sdk_compatibility",
            "including `2.0.0`",
            "never ignores `maximum_exclusive`",
        ],
        "docs/SIDSCOPE_SID_REFRESH.md": [
            "parallel_positions",
            "same-input controls",
            "not a before/after refresh experiment",
        ],
        "docs/SIDSCOPE_2_0_CANDIDATE_FREEZE.md": [
            "engineering candidate only",
            "independent_user_actual_use excluded from current gates",
            "No RC, tag, push or release authorized",
        ],
        "docs/SIDSCOPE_2_0_RC_PACKET.md": [
            "RC transition gated on same-source delivery evidence",
            "Linux CPython 3.9, 3.10, 3.11 and 3.12",
            "No public action is authorized",
        ],
        "docs/adr/0025-remove-independent-user-acceptance-gate.md": [
            "independent_user_actual_use",
            "scope_policy_missing",
            "Rollback",
        ],
        "docs/adr/0023-stabilize-adapter-sdk-1-0.md": [
            "Adapter SDK at 1.0",
            "honor declared intervals exactly",
            "Rollback",
        ],
        "docs/adr/0024-freeze-2-0-engineering-candidate.md": [
            "Engineering completion and certification",
            "certification_ready",
            "Rollback",
        ],
    }
    for rel_path, tokens in required_docs.items():
        text = (root / rel_path).read_text(encoding="utf-8")
        missing = [token for token in tokens if token not in text]
        if missing:
            raise ValueError(f"{rel_path} missing release-governance tokens: {missing}")

    registry = load_contract_registry(repository_root=root)
    if len(registry.contracts) != 11:
        raise ValueError("SIDScope 1.2 requires eleven canonical contracts")
    profiles = load_profile_catalog()
    if [profile.profile_id for profile in profiles] != [
        "generator_g0_g5",
        "overlay_g0_g5",
        "release_local",
        "static_mapping_c0_c5",
    ]:
        raise ValueError("SIDScope 1.5 governed profile catalog mismatch")
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass",
        "distribution": project_name,
        "package_version": project_version,
        "python_import": "sidinspector",
        "console_command": "sidscope",
        "adapter_sdk_version": ADAPTER_SDK_VERSION,
        "canonical_schemas": [
            f"{item.schema_id}@{item.schema_revision}" for item in registry.contracts
        ],
        "contract_registry": "sidscope.contract_registry.v1@1.0.0",
        "governed_profile_count": len(profiles),
        "governance_documents_checked": len(required_docs),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_release_metadata()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
