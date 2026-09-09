#!/usr/bin/env python3
"""Run a local G8-style fresh-environment smoke over a release archive."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any

try:
    from tools.build_sidscope_release_candidate_archive import DEFAULT_OUTPUT, build_archive
    from tools.sidscope_release_profiles import PROFILE_IDS
    from tools.smoke_sidscope_release_candidate_archive import read_archive_profile, safe_extract_zip, verify_archive_digest
    from tools.verify_sidscope_resource_package import ROOT
except ModuleNotFoundError:
    from build_sidscope_release_candidate_archive import DEFAULT_OUTPUT, build_archive
    from sidscope_release_profiles import PROFILE_IDS
    from smoke_sidscope_release_candidate_archive import read_archive_profile, safe_extract_zip, verify_archive_digest
    from verify_sidscope_resource_package import ROOT


DEFAULT_RESULT_JSON: Path | None = None


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

    Upgrade old seeded pip, then exercise a regular wheel-backed installation.
    Editable installation cannot prove that installed package resources work.
    """

    return [
        [str(py), "-m", "pip", "install", "--upgrade", "pip>=21.3"],
        [str(py), "-m", "pip", "install", "."],
    ]


def run_fresh_env_smoke(
    archive_path: Path, *, expected_profile: str | None = None, expected_sha256: str | None = None
) -> dict[str, Any]:
    if archive_path.exists() and expected_sha256 is not None:
        verify_archive_digest(archive_path, expected_sha256)
    archive_result = ensure_archive(archive_path, expected_profile=expected_profile)
    digest = verify_archive_digest(archive_path, expected_sha256)
    profile_id = str(archive_result["profile_id"])

    with tempfile.TemporaryDirectory(prefix="sidscope-g8-fresh-env-") as tmp:
        tmp_root = Path(tmp).resolve()
        package_root = tmp_root / "package"
        venv_dir = tmp_root / "venv"
        package_root.mkdir()
        safe_extract_zip(archive_path, package_root)

        install_root = tmp_root / "install-source"
        shutil.copytree(package_root, install_root)

        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        py = venv_python(venv_dir)
        commands = [run(command, cwd=install_root) for command in fresh_env_install_commands(py)]
        commands.append(run([str(py), "-I", "-c", "import pathlib, sidscope; p = pathlib.Path(sidscope.__file__).resolve(); assert 'site-packages' in p.parts, p; print(p)"], cwd=tmp_root))
        demo_root = tmp_root / "runtime-demo"
        commands.append(run([str(py), "-I", "-m", "sidinspector.runtime_demo", "--output-dir", str(demo_root)], cwd=tmp_root))
        commands.append(run([str(py), "-I", "-m", "sidinspector.cli", "contract", "validate", "--type", "source-identity", "--input", str(demo_root / "source_identity.json")], cwd=tmp_root))
        commands.append(run([str(py), "-m", "pip", "freeze"], cwd=tmp_root))
        commands.append(run([str(py), "-I", "-c",
            "import json; from pathlib import Path; from sidscope.workflows import main,evaluate,compare; p=Path('own-mapping.csv'); p.write_text('item_id,sid_level_0,sid_level_1\\n1,0,1\\n2,0,1\\n'); assert main(['audit','--input',str(p),'--output','own-audit.json'])==0; assert json.loads(Path('own-audit.json').read_text())['findings'][0]['normalized_items']==[1,2]; r=evaluate([{'episode_id':'a','ranked_items':[None,2]}],[{'episode_id':'a','target_item_id':2,'slice':'cold'}],dataset='consumer',cutoff=2); assert r['records'][0]['rank']==2; assert compare(r,r)['status']=='qualified'; print('public workflow consumer: pass')"], cwd=tmp_root))
        commands.append(run([str(py), "-I", "-c",
            "from pathlib import Path; from sidscope.workflows import evaluate; from sidscope.regression import compare_runs; from sidscope.diagnostic_review import write_review; labels=[{'episode_id':str(i),'target_item_id':i,'slice':'test'} for i in range(4)]; r=evaluate([{'episode_id':str(i),'ranked_items':[i]} for i in range(4)],labels,dataset='installed',cutoff=1); a={'run_id':'left','pair_id':'p','seed':1,'controls':{'fixture':'synthetic'},'report':r}; b=dict(a,run_id='right'); d=compare_runs([a],[b],clusters={str(i):str(i) for i in range(4)},degradation_budget={'hit_at_cutoff':0,'ndcg_at_cutoff':0},replicates=200); assert d['results'][0]['metrics']['hit_at_cutoff']['interval_unavailable']=='insufficient_paired_runs'; write_review(Path('offline-review'),r); assert Path('offline-review/index.html').is_file(); print('installed regression and review: pass')"], cwd=tmp_root))
        if profile_id == "runtime":
            commands.append(run([str(py), "tools/verify_sidscope_runtime_release.py"], cwd=package_root))
        elif profile_id == "conformance":
            fixture = package_root / "examples" / "canonical_pipeline_fixture"
            submission_root = tmp_root / "recomputed-submission"
            commands.append(run([
                str(py), "-I", "-m", "sidinspector.submission.recomputed",
                "--source", str(package_root / "examples/conformance_ecosystem_fixture/submission/positive"),
                "--trace", str(fixture / "trace_envelope.json"),
                "--selection", str(fixture / "episode_selection.json"),
                "--output", str(submission_root),
            ], cwd=tmp_root))
            commands.append(run([str(py), "-I", "-c",
                "import sys; from pathlib import Path; from sidinspector.submission.checker import validate_submission_package; from sidinspector.submission.indexes import generate_status_index, generate_result_index; p=validate_submission_package(Path(sys.argv[1])); assert generate_status_index([p])['entries'][0]['status_label']=='diagnostics_verified'; assert generate_result_index([p])['entries'][0]['result_card']==p.evidence_bundle.result_card; print('computed admission and indexes: pass')", str(submission_root)], cwd=tmp_root))
            commands.append(run([
                str(py), "-I", "-m", "sidinspector.cli", "verify",
                "--report", str(fixture / "conformance_report.json"),
                "--diagnostic", str(fixture / "diagnostic_report.json"),
                "--trace", str(fixture / "trace_envelope.json"),
                "--selection", str(fixture / "episode_selection.json"),
            ], cwd=tmp_root))
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
        "archive_sha256": digest,
        "expected_digest_supplied": expected_sha256 is not None,
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
    parser.add_argument("--expected-sha256", default=None, help="Digest obtained through a separately trusted channel.")
    parser.add_argument(
        "--result-json",
        type=Path,
        default=DEFAULT_RESULT_JSON,
        help=(
            "Optional result path. By default the report is printed only and "
            "the source tree is not modified."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_fresh_env_smoke(args.archive.resolve(), expected_profile=args.profile, expected_sha256=args.expected_sha256)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
