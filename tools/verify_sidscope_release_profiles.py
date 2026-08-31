#!/usr/bin/env python3
"""Verify the additive SIDScope 1.7 runtime/conformance/evidence release profiles."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

try:
    from tools.build_sidscope_release_candidate_archive import build_archive
    from tools.sidscope_release_profiles import (
        DEFAULT_PROFILE_REGISTRY,
        PROFILE_IDS,
        PROFILE_RECEIPT_PATH,
        load_release_profiles,
        validate_profile_receipt,
    )
    from tools.verify_sidscope_resource_package import ROOT
except ModuleNotFoundError:
    from build_sidscope_release_candidate_archive import build_archive
    from sidscope_release_profiles import (
        DEFAULT_PROFILE_REGISTRY,
        PROFILE_IDS,
        PROFILE_RECEIPT_PATH,
        load_release_profiles,
        validate_profile_receipt,
    )
    from verify_sidscope_resource_package import ROOT


MANIFEST = ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"
LARGE_TRACE_PATHS = {
    "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json",
    "examples/latte_psid_trained_trace_real_smoke/latte_amazon_vg_1_per_bucket_s2024.json",
    "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json",
}


def _archive_inventory(path: Path) -> tuple[set[str], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        receipt = json.loads(archive.read(PROFILE_RECEIPT_PATH))
    content = sorted(names - {PROFILE_RECEIPT_PATH})
    validate_profile_receipt(receipt, content_paths=content)
    return names, receipt


def _extension_counts(paths: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        suffix = Path(path).suffix.lower() or "[none]"
        counts[suffix] = counts.get(suffix, 0) + 1
    return dict(sorted(counts.items()))


def verify_release_profiles() -> dict[str, Any]:
    default_profile, registry = load_release_profiles(DEFAULT_PROFILE_REGISTRY)
    if tuple(registry) != PROFILE_IDS:
        raise AssertionError(tuple(registry))
    inventories: dict[str, set[str]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="sidscope-release-profiles-") as tmp:
        for profile_id in PROFILE_IDS:
            archive_path = Path(tmp) / f"{profile_id}.zip"
            result = build_archive(
                manifest_path=MANIFEST,
                output_path=archive_path,
                profile_id=profile_id,
            )
            names, receipt = _archive_inventory(archive_path)
            if receipt["profile_id"] != profile_id or result["profile_id"] != profile_id:
                raise AssertionError(f"profile identity mismatch: {profile_id}")
            inventories[profile_id] = names
            summaries[profile_id] = {
                "archive_size_bytes": archive_path.stat().st_size,
                "file_count": len(names),
                "extension_counts": _extension_counts(names),
            }

    if not inventories["runtime"] < inventories["conformance"]:
        raise AssertionError("runtime must be a strict subset of conformance")
    if not inventories["conformance"] < inventories["evidence-full"]:
        raise AssertionError("conformance must be a strict subset of evidence-full")
    if any(
        path.startswith(("examples/", "tests/"))
        or (path.startswith("docs/reproducibility/") and path != "docs/reproducibility/sidscope_release_profiles.v1.json")
        for path in inventories["runtime"]
    ):
        raise AssertionError("runtime profile leaked fixtures, tests, or tracked evidence")
    if LARGE_TRACE_PATHS & inventories["conformance"]:
        raise AssertionError("conformance profile contains trained real traces")
    if not LARGE_TRACE_PATHS <= inventories["evidence-full"]:
        raise AssertionError("evidence-full profile lost trained real traces")
    if summaries["runtime"]["archive_size_bytes"] >= summaries["conformance"]["archive_size_bytes"]:
        raise AssertionError("runtime archive is not smaller than conformance")
    if summaries["conformance"]["archive_size_bytes"] >= summaries["evidence-full"]["archive_size_bytes"]:
        raise AssertionError("conformance archive is not smaller than evidence-full")
    return {
        "schema": "sidscope.release_profile_verification.v1",
        "status": "pass",
        "gpu_required": False,
        "product_version": "1.7.0.dev0",
        "default_profile": default_profile,
        "profile_order": list(PROFILE_IDS),
        "profiles": summaries,
        "trained_trace_policy": "evidence-full-only",
        "typed_negative_codes": [
            "missing_required_profile_path",
            "profile_path_binding_mismatch",
            "unexpected_release_profile",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify SIDScope 1.7 release profiles.")
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_release_profiles()
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
