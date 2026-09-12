#!/usr/bin/env python3
"""Verify the frozen 2.0 engineering candidate without inventing F09 acceptance."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from sidinspector.sdk import ADAPTER_SDK_VERSION, PLUGIN_API_VERSION
from tools.sidscope_release_profiles import PROFILE_IDS, load_release_profiles
from tools.verify_sidscope_1_7_stabilization import verify as verify_surface
from tools.verify_sidscope_release_metadata import verify_release_metadata
from tools.verify_sidscope_sdlc_hardening import verify as verify_sdlc


def verify(*, require_clean: bool = False) -> dict:
    surface = verify_surface()
    metadata = verify_release_metadata()
    sdlc = verify_sdlc()
    default_profile, profiles = load_release_profiles()
    version = metadata["package_version"]
    stage = "development" if version == "1.7.0.dev0" else "rc" if re.fullmatch(r"2\.0\.0rc[1-9][0-9]*", version) else None
    if stage is None:
        raise AssertionError("unsupported candidate version/stage")
    if stage == "rc" and not sdlc["certification_ready"]:
        raise AssertionError("RC requires completed certification readiness")
    if (ADAPTER_SDK_VERSION, PLUGIN_API_VERSION) != ("1.0.0", "1.0"):
        raise AssertionError("stable adapter extension boundary drift")
    if default_profile != "runtime" or tuple(profiles) != PROFILE_IDS:
        raise AssertionError("additive release profile boundary drift")
    if set(sdlc["blocking_requirements"]) - {"F09"}:
        raise AssertionError(f"unexpected certification blockers: {sdlc['blocking_requirements']}")
    if sdlc["certification_ready"] and (sdlc["blocking_requirements"] or sdlc["pending_acceptance"]):
        raise AssertionError("inconsistent certification state")
    if sdlc["engineering_blocking_requirements"]:
        raise AssertionError(f"engineering blockers remain: {sdlc['engineering_blocking_requirements']}")
    if sdlc["candidate_requirements"] != ["N09", "N10"]:
        raise AssertionError("deferred candidate boundary drift")
    clean = None
    if require_clean:
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
        clean = not status.strip()
        if not clean:
            raise AssertionError("candidate source tree is not clean")
    return {
        "schema": "sidscope.2_0_candidate_verification.v1",
        "status": "pass",
        "package_version": metadata["package_version"],
        "candidate_stage": stage,
        "adapter_sdk_version": ADAPTER_SDK_VERSION,
        "plugin_api_version": PLUGIN_API_VERSION,
        "public_schema_count": surface["schema_count"],
        "public_schema_resource_count": surface["schema_resource_count"],
        "cli_result_schema_count": surface["cli_result_schema_count"],
        "python_facade_symbol_count": surface["python_facade_symbol_count"],
        "release_profiles": list(PROFILE_IDS),
        "engineering_ready": sdlc["engineering_ready"],
        "certification_ready": sdlc["certification_ready"],
        "certification_blockers": sdlc["blocking_requirements"],
        "pending_acceptance": sdlc["pending_acceptance"],
        "excluded_candidates": sdlc["candidate_requirements"],
        "clean_source_required": require_clean,
        "clean_source": clean,
        "release_authorized": False,
        "boundary": "Engineering closure is not F09 acceptance, an RC version, or public-release authorization.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-engineering-ready", action="store_true")
    parser.add_argument("--require-certification-ready", action="store_true")
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify(require_clean=args.require_clean)
    except (AssertionError, OSError, ValueError) as error:
        print(json.dumps({"status": "fail", "code": type(error).__name__, "detail": str(error)}, sort_keys=True))
        return 2
    blocked = ((args.require_engineering_ready and not result["engineering_ready"])
               or (args.require_certification_ready and not result["certification_ready"]))
    if blocked:
        result["status"] = "blocked"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
