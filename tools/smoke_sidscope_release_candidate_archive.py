#!/usr/bin/env python3
"""Smoke-test a SIDScope release-candidate archive after extraction."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

try:
    from tools.sidscope_release_profiles import (
        PROFILE_IDS,
        PROFILE_RECEIPT_PATH,
        ReleaseProfileError,
        validate_profile_receipt,
    )
except ModuleNotFoundError:
    from sidscope_release_profiles import (
        PROFILE_IDS,
        PROFILE_RECEIPT_PATH,
        ReleaseProfileError,
        validate_profile_receipt,
    )


def safe_extract_zip(archive_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (target_dir / member.filename).resolve()
            if target != target_dir and target_dir not in target.parents:
                raise ValueError(f"Unsafe archive member path: {member.filename}")
        archive.extractall(target_dir)


def run(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "archive smoke command failed:\n"
            f"command: {' '.join(cmd)}\n"
            f"cwd: {cwd}\n"
            f"stdout_tail:\n{completed.stdout[-4000:]}"
        )
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
    }


def read_archive_profile(archive_path: Path, *, expected_profile: str | None = None) -> str:
    with zipfile.ZipFile(archive_path) as archive:
        names = sorted(archive.namelist())
        if len(names) != len(set(names)):
            raise ReleaseProfileError("duplicate_archive_member", "archive")
        if sum(info.file_size for info in archive.infolist()) > 64 * 1024 * 1024:
            raise ReleaseProfileError("archive_size_budget_exceeded", "archive")
        if any(info.file_size > 8 * 1024 * 1024 for info in archive.infolist()):
            raise ReleaseProfileError("archive_member_size_budget_exceeded", "archive")
        if PROFILE_RECEIPT_PATH not in names:
            raise ReleaseProfileError("missing_profile_receipt", str(archive_path))
        receipt = json.loads(archive.read(PROFILE_RECEIPT_PATH))
        hashes = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in names if name != PROFILE_RECEIPT_PATH}
    profile_id = validate_profile_receipt(
        receipt,
        content_paths=[name for name in names if name != PROFILE_RECEIPT_PATH],
        content_hashes=hashes,
    )
    if expected_profile is not None and profile_id != expected_profile:
        raise ReleaseProfileError(
            "unexpected_release_profile", f"expected={expected_profile} observed={profile_id}"
        )
    return profile_id


def verify_archive_digest(archive_path: Path, expected_sha256: str | None = None) -> str:
    if expected_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ReleaseProfileError("invalid_expected_archive_digest", "expected SHA-256")
    digest = hashlib.sha256()
    with archive_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if expected_sha256 is not None and actual != expected_sha256:
        raise ReleaseProfileError("archive_digest_mismatch", "archive")
    return actual


def smoke_archive(archive_path: Path, *, expected_profile: str | None = None, expected_sha256: str | None = None) -> dict[str, Any]:
    digest = verify_archive_digest(archive_path, expected_sha256)
    profile_id = read_archive_profile(archive_path, expected_profile=expected_profile)
    with tempfile.TemporaryDirectory(prefix="sidscope-archive-smoke-") as tmp:
        root = Path(tmp).resolve()
        safe_extract_zip(archive_path, root)
        if profile_id == "runtime":
            commands = [run([sys.executable, "tools/verify_sidscope_runtime_release.py"], cwd=root)]
        elif profile_id == "conformance":
            commands = [
                run([sys.executable, "tools/verify_sidscope_runtime_release.py"], cwd=root),
                run([sys.executable, "tools/verify_sidscope_1_3_plugin_ecosystem.py"], cwd=root),
                run([sys.executable, "tools/verify_sidscope_1_5_conformance_ecosystem.py"], cwd=root),
            ]
        else:
            commands = [
                run([sys.executable, "tools/verify_sidscope_resource_package.py"], cwd=root),
                run(
                    [
                        sys.executable,
                        "tools/run_sidscope_sampled_regeneration.py",
                        "--output-dir",
                        str(root / "_smoke_sampled_regeneration"),
                    ],
                    cwd=root,
                ),
            ]

    return {
        "schema": "sidscope.release_archive_smoke.v1",
        "status": "pass",
        "gpu_required": False,
        "archive_path": str(archive_path),
        "archive_sha256": digest,
        "expected_digest_supplied": expected_sha256 is not None,
        "profile_id": profile_id,
        "commands": commands,
        "boundary": (
            "Smoke test extracts the release archive without .git, verifies its hash-bound "
            "profile receipt, and runs the profile-specific CPU smoke suite."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test a SIDScope release-candidate archive.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--profile", choices=PROFILE_IDS, default=None)
    parser.add_argument("--expected-sha256", default=None, help="Digest obtained through a separately trusted channel.")
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = smoke_archive(args.archive.resolve(), expected_profile=args.profile, expected_sha256=args.expected_sha256)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
