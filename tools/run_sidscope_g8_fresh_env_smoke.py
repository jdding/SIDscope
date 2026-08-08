#!/usr/bin/env python3
"""Run a local G8-style fresh-environment smoke over a release archive."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any

try:
    from tools.build_sidscope_release_candidate_archive import DEFAULT_OUTPUT, build_archive
    from tools.smoke_sidscope_release_candidate_archive import safe_extract_zip
    from tools.verify_sidscope_resource_package import ROOT
except ModuleNotFoundError:
    from build_sidscope_release_candidate_archive import DEFAULT_OUTPUT, build_archive
    from smoke_sidscope_release_candidate_archive import safe_extract_zip
    from verify_sidscope_resource_package import ROOT


DEFAULT_RESULT_JSON = ROOT / "experiments" / "v1_evidence_chain" / "runs" / "R603_sidscope_g8_fresh_env_smoke.json"


def run(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    record = {
        "command": cmd,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
    }
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(record, indent=2, sort_keys=True))
    return record


def venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_archive(archive_path: Path) -> dict[str, Any]:
    if archive_path.exists():
        return {
            "schema": "sidscope.release_candidate_archive.v1",
            "status": "existing",
            "archive_path": str(archive_path),
            "boundary": "Using existing archive supplied to G8 smoke.",
        }
    return build_archive(
        manifest_path=ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
        output_path=archive_path,
    )


def run_fresh_env_smoke(archive_path: Path) -> dict[str, Any]:
    archive_result = ensure_archive(archive_path)

    with tempfile.TemporaryDirectory(prefix="sidscope-g8-fresh-env-") as tmp:
        tmp_root = Path(tmp).resolve()
        package_root = tmp_root / "package"
        venv_dir = tmp_root / "venv"
        package_root.mkdir()
        safe_extract_zip(archive_path, package_root)

        venv.EnvBuilder(with_pip=True, system_site_packages=True, clear=True).create(venv_dir)
        py = venv_python(venv_dir)
        commands = [
            run([str(py), "-m", "pip", "install", "-e", ".", "--no-deps"], cwd=package_root),
            run([str(py), "tools/verify_sidscope_resource_package.py"], cwd=package_root),
            run(
                [
                    str(py),
                    "tools/build_sidscope_release_candidate_archive.py",
                    "--output",
                    str(tmp_root / "rebuilt-sidscope-v1-release-candidate.zip"),
                ],
                cwd=package_root,
            ),
            run(
                [
                    str(py),
                    "tools/smoke_sidscope_release_candidate_archive.py",
                    str(tmp_root / "rebuilt-sidscope-v1-release-candidate.zip"),
                ],
                cwd=package_root,
            ),
            run(
                [
                    str(py),
                    "tools/run_sidscope_sampled_regeneration.py",
                    "--output-dir",
                    str(tmp_root / "sampled_regeneration"),
                ],
                cwd=package_root,
            ),
        ]

    return {
        "schema": "sidscope.g8_fresh_env_smoke.v1",
        "status": "pass",
        "gpu_required": False,
        "archive_path": str(archive_path),
        "archive_result": archive_result,
        "commands": commands,
        "install_boundary": (
            "Local clean-extract smoke with a temporary venv using system site packages; "
            "public URL/tag accessibility and dependency download from a blank machine remain separate gates."
        ),
        "boundary": "G8 local fresh-environment evidence; does not verify public URL, release tag, or hosted archive access.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SIDScope G8 local fresh-environment smoke.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result-json", type=Path, default=DEFAULT_RESULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_fresh_env_smoke(args.archive.resolve())
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
