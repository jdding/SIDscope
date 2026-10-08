#!/usr/bin/env python3
"""Build a release-clean SIDScope reviewer package archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

try:
    from tools.verify_sidscope_resource_package import (
        ROOT,
        check_forbidden_public_content,
        check_forbidden_tracked,
        expand_public_manifest_paths,
        tracked_files,
        validate_release_manifest,
    )
except ModuleNotFoundError:
    from verify_sidscope_resource_package import (
        ROOT,
        check_forbidden_public_content,
        check_forbidden_tracked,
        expand_public_manifest_paths,
        tracked_files,
        validate_release_manifest,
    )

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.version import PRODUCT_VERSION

try:
    from tools.sidscope_release_profiles import (
        DEFAULT_PROFILE_REGISTRY,
        PROFILE_IDS,
        PROFILE_RECEIPT_PATH,
        build_profile_receipt,
        canonical_json_bytes,
        resolve_release_profile,
    )
except ModuleNotFoundError:
    from sidscope_release_profiles import (
        DEFAULT_PROFILE_REGISTRY,
        PROFILE_IDS,
        PROFILE_RECEIPT_PATH,
        build_profile_receipt,
        canonical_json_bytes,
        resolve_release_profile,
    )


DEFAULT_MANIFEST = ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"
DEFAULT_OUTPUT = Path("/tmp") / f"sidscope-v{PRODUCT_VERSION}-runtime.zip"
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = 0o100644


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_archive(
    *,
    manifest_path: Path,
    output_path: Path,
    profile_id: str = "runtime",
    profile_registry_path: Path = DEFAULT_PROFILE_REGISTRY,
) -> dict[str, Any]:
    release_manifest = validate_release_manifest(manifest_path)
    tracked = tracked_files()
    public_paths = expand_public_manifest_paths(manifest_path, tracked)
    profile, package_paths = resolve_release_profile(
        profile_id,
        public_paths=public_paths,
        registry_path=profile_registry_path,
    )
    forbidden = check_forbidden_tracked(package_paths)
    if forbidden:
        formatted = "\n".join(f"  - {path}" for path in forbidden[:50])
        raise RuntimeError(f"forbidden files would enter release archive:\n{formatted}")
    public_content_findings = check_forbidden_public_content(package_paths)
    if public_content_findings:
        formatted = "\n".join(f"  - {finding}" for finding in public_content_findings[:50])
        raise RuntimeError(f"forbidden content would enter release archive:\n{formatted}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    # Receipt and ZIP must describe the very same byte snapshot, even when the
    # source checkout is dirty. Do not re-read files after computing digests.
    contents = {path: (ROOT / path).read_bytes() for path in sorted(package_paths)}
    content_hashes = {path: hashlib.sha256(data).hexdigest() for path, data in contents.items()}
    receipt = build_profile_receipt(
        profile=profile,
        content_paths=package_paths,
        registry_path=profile_registry_path,
        source_manifest_path=manifest_path,
        product_version=PRODUCT_VERSION,
        content_hashes=content_hashes,
    )
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"

    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for rel_path in sorted(package_paths):
            info = zipfile.ZipInfo(rel_path, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = FIXED_FILE_MODE << 16
            archive.writestr(
                info,
                contents[rel_path],
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
        receipt_info = zipfile.ZipInfo(PROFILE_RECEIPT_PATH, date_time=FIXED_ZIP_TIMESTAMP)
        receipt_info.compress_type = zipfile.ZIP_DEFLATED
        receipt_info.create_system = 3
        receipt_info.external_attr = FIXED_FILE_MODE << 16
        archive.writestr(
            receipt_info,
            receipt_bytes,
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        )

    return {
        "schema": "sidscope.release_candidate_archive.v2",
        "status": "pass",
        "gpu_required": False,
        "archive_path": str(output_path),
        "archive_sha256": file_sha256(output_path),
        "archive_size_bytes": output_path.stat().st_size,
        "profile_id": profile.profile_id,
        "profile_receipt": receipt,
        "profile_registry_path": str(profile_registry_path.relative_to(ROOT)),
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest": release_manifest,
        "included_files": len(package_paths) + 1,
        "content_files": len(package_paths),
        "forbidden_findings": forbidden,
        "forbidden_public_content_findings": public_content_findings,
        "boundary": (
            "Deterministic release profile built as a strict subset of git-tracked "
            "public_package=yes manifest paths, plus one generated hash-bound profile receipt; "
            "public URL, tag, and G8 remain separate gates."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a SIDScope release-candidate reviewer archive.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", choices=PROFILE_IDS, default="runtime")
    parser.add_argument("--profile-registry", type=Path, default=DEFAULT_PROFILE_REGISTRY)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_archive(
        manifest_path=args.manifest.resolve(),
        output_path=args.output.resolve(),
        profile_id=args.profile,
        profile_registry_path=args.profile_registry.resolve(),
    )
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
