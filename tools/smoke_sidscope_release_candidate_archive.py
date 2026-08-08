#!/usr/bin/env python3
"""Smoke-test a SIDScope release-candidate archive after extraction."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


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


def smoke_archive(archive_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sidscope-archive-smoke-") as tmp:
        root = Path(tmp).resolve()
        safe_extract_zip(archive_path, root)
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
        "commands": commands,
        "boundary": "Smoke test extracts the release archive without .git and runs verifier plus sampled regeneration from the extracted package.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test a SIDScope release-candidate archive.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = smoke_archive(args.archive.resolve())
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
