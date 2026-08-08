#!/usr/bin/env python3
"""Run the final public URL/tag smoke for a SIDScope reviewer release."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any


DEFAULT_RESULT_JSON = Path("/tmp/sidscope_public_url_smoke.json")


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


def clone_command(repo_url: str, ref: str, target_dir: Path) -> list[str]:
    return ["git", "clone", "--depth", "1", "--branch", ref, repo_url, str(target_dir)]


def smoke_commands(py: Path, archive_path: Path) -> list[list[str]]:
    return [
        [str(py), "-m", "pip", "install", "-e", ".", "--no-deps"],
        [str(py), "tools/verify_sidscope_resource_package.py"],
        [
            str(py),
            "tools/build_sidscope_release_candidate_archive.py",
            "--output",
            str(archive_path),
        ],
        [str(py), "tools/smoke_sidscope_release_candidate_archive.py", str(archive_path)],
        [str(py), "tools/run_sidscope_g8_fresh_env_smoke.py", "--archive", str(archive_path)],
        [
            str(py),
            "tools/run_sidscope_sampled_regeneration.py",
            "--output-dir",
            str(archive_path.parent / "sampled_regeneration"),
        ],
    ]


def run_public_url_smoke(repo_url: str, ref: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sidscope-public-url-smoke-") as tmp:
        tmp_root = Path(tmp).resolve()
        package_root = tmp_root / "checkout"
        venv_dir = tmp_root / "venv"
        archive_path = tmp_root / "sidscope-v1-release-candidate.zip"

        commands = [run(clone_command(repo_url, ref, package_root), cwd=tmp_root)]
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=package_root,
            text=True,
        ).strip()

        venv.EnvBuilder(with_pip=True, system_site_packages=True, clear=True).create(venv_dir)
        py = venv_python(venv_dir)
        for command in smoke_commands(py, archive_path):
            commands.append(run(command, cwd=package_root))

        archive_sha256 = None
        if archive_path.exists():
            import hashlib

            digest = hashlib.sha256()
            with archive_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            archive_sha256 = digest.hexdigest()

    return {
        "schema": "sidscope.public_url_smoke.v1",
        "status": "pass",
        "gpu_required": False,
        "repo_url": repo_url,
        "ref": ref,
        "commit": commit,
        "archive_sha256": archive_sha256,
        "commands": commands,
        "boundary": (
            "Final public/reviewer-accessible URL smoke. This is the gate that "
            "can close public URL/tag accessibility after the release surface exists."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SIDScope public URL/tag smoke.")
    parser.add_argument("--repo-url", required=True, help="Reviewer-accessible repository URL.")
    parser.add_argument("--ref", required=True, help="Release tag or branch to clone.")
    parser.add_argument("--result-json", type=Path, default=DEFAULT_RESULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_public_url_smoke(args.repo_url, args.ref)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
