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
    from tools.sidscope_release_profiles import PROFILE_IDS
    from tools.smoke_sidscope_release_candidate_archive import read_archive_profile, safe_extract_zip
    from tools.verify_sidscope_resource_package import ROOT
except ModuleNotFoundError:
    from build_sidscope_release_candidate_archive import DEFAULT_OUTPUT, build_archive
    from sidscope_release_profiles import PROFILE_IDS
    from smoke_sidscope_release_candidate_archive import read_archive_profile, safe_extract_zip
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


def ensure_archive(archive_path: Path, *, expected_profile: str | None) -> dict[str, Any]:
    if archive_path.exists():
        profile_id = read_archive_profile(archive_path, expected_profile=expected_profile)
        return {
            "schema": "sidscope.release_candidate_archive.v2",
            "status": "existing",
            "archive_path": str(archive_path),
            "profile_id": profile_id,
            "boundary": "Using existing archive supplied to G8 smoke.",
        }
    profile_id = expected_profile or "runtime"
    return build_archive(
        manifest_path=ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
        output_path=archive_path,
        profile_id=profile_id,
    )


def fresh_env_install_commands(py: Path) -> list[list[str]]:
    """Return the isolated install sequence used by the local G8 smoke.

    Apple Command Line Tools Python 3.9 can seed a venv with pip 21.2, whose
    editable-install fallback invokes ``setup.py develop`` and then loses pip
    inside its PEP 517 subprocess. Upgrade pip before the editable install so
    the same standards-based path is exercised locally and by the public URL
    smoke.
    """

    return [
        [str(py), "-m", "pip", "install", "--upgrade", "pip>=21.3"],
        [str(py), "-m", "pip", "install", "-e", "."],
    ]


def run_fresh_env_smoke(
    archive_path: Path, *, expected_profile: str | None = None
) -> dict[str, Any]:
    archive_result = ensure_archive(archive_path, expected_profile=expected_profile)
    profile_id = str(archive_result["profile_id"])

    with tempfile.TemporaryDirectory(prefix="sidscope-g8-fresh-env-") as tmp:
        tmp_root = Path(tmp).resolve()
        package_root = tmp_root / "package"
        venv_dir = tmp_root / "venv"
        package_root.mkdir()
        safe_extract_zip(archive_path, package_root)

        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        py = venv_python(venv_dir)
        commands = [run(command, cwd=package_root) for command in fresh_env_install_commands(py)]
        if profile_id == "runtime":
            commands.append(run([str(py), "tools/verify_sidscope_runtime_release.py"], cwd=package_root))
        elif profile_id == "conformance":
            commands.extend(
                [
                    run([str(py), "tools/verify_sidscope_runtime_release.py"], cwd=package_root),
                    run([str(py), "tools/verify_sidscope_1_3_plugin_ecosystem.py"], cwd=package_root),
                    run([str(py), "tools/verify_sidscope_1_5_conformance_ecosystem.py"], cwd=package_root),
                ]
            )
        else:
            commands.extend(
                [
                    run([str(py), "tools/verify_sidscope_resource_package.py"], cwd=package_root),
                    run(
                        [
                            str(py),
                            "tools/build_sidscope_release_candidate_archive.py",
                            "--profile",
                            "evidence-full",
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
                            "--profile",
                            "evidence-full",
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
            )

    return {
        "schema": "sidscope.g8_fresh_env_smoke.v1",
        "status": "pass",
        "gpu_required": False,
        "archive_path": str(archive_path),
        "profile_id": profile_id,
        "archive_result": archive_result,
        "commands": commands,
        "install_boundary": (
            "Local clean-extract smoke with a temporary isolated venv that installs the selected "
            "release profile and its declared dependencies; public URL/tag accessibility remains a separate gate."
        ),
        "boundary": "G8 local fresh-environment evidence; does not verify public URL, release tag, or hosted archive access.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SIDScope G8 local fresh-environment smoke.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", choices=PROFILE_IDS, default=None)
    parser.add_argument("--result-json", type=Path, default=DEFAULT_RESULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_fresh_env_smoke(args.archive.resolve(), expected_profile=args.profile)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
