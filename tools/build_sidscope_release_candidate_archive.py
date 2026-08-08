#!/usr/bin/env python3
"""Build a release-clean SIDScope reviewer package archive."""

from __future__ import annotations

import argparse
import hashlib
import json
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


DEFAULT_MANIFEST = ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"
DEFAULT_OUTPUT = Path("/tmp") / "sidscope-v1-release-candidate.zip"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_archive(*, manifest_path: Path, output_path: Path) -> dict[str, Any]:
    release_manifest = validate_release_manifest(manifest_path)
    tracked = tracked_files()
    package_paths = expand_public_manifest_paths(manifest_path, tracked)
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

    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel_path in package_paths:
            archive.write(ROOT / rel_path, arcname=rel_path)

    return {
        "schema": "sidscope.release_candidate_archive.v1",
        "status": "pass",
        "gpu_required": False,
        "archive_path": str(output_path),
        "archive_sha256": file_sha256(output_path),
        "archive_size_bytes": output_path.stat().st_size,
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest": release_manifest,
        "included_files": len(package_paths),
        "forbidden_findings": forbidden,
        "forbidden_public_content_findings": public_content_findings,
        "boundary": "Release-clean archive built from git-tracked public_package=yes manifest paths; public URL, tag, and G8 remain separate gates.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a SIDScope release-candidate reviewer archive.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_archive(manifest_path=args.manifest.resolve(), output_path=args.output.resolve())
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
