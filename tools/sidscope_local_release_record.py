#!/usr/bin/env python3
"""Bind local test execution and candidate bytes outside the delivered archive.

This is not a signature policy or public-release authorization. A receiver pins
the digest obtained from their trusted local build before loading the record.
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from sidinspector.contracts import canonical_json_bytes, with_content_sha256, load_json
from tools.build_sidscope_release_candidate_archive import build_archive, DEFAULT_MANIFEST
from tools.verify_sidscope_resource_package import tracked_files, expand_public_manifest_paths
from tools.smoke_sidscope_release_candidate_archive import smoke_archive, verify_archive_digest, read_archive_profile


class ReleaseRecordError(ValueError):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()
    unknown = [name for name in git("ls-files", "--others", "--exclude-standard", "--", "src", "tests", "tools").splitlines() if Path(name).name != ".DS_Store"]
    if unknown:
        raise ReleaseRecordError("unregistered_source_input", "register intended source files before verification")
    files = expand_public_manifest_paths(DEFAULT_MANIFEST, tracked_files())
    return with_content_sha256({"head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"), "dirty": bool(git("status", "--porcelain")), "public_files": {name: sha(ROOT / name) for name in files}})


def verify_record(record_path: Path, *, expected_record_sha256: str, archive_path: Path, profile: str):
    verify_archive_digest(record_path, expected_record_sha256)
    record = load_json(record_path)
    if record.get("format") != "sidscope.local_release_record.v1" or record.get("status") != "pass":
        raise ReleaseRecordError("invalid_release_record", "format/status")
    candidates = [row for row in record["archives"] if row["profile"] == profile]
    if len(candidates) != 1:
        raise ReleaseRecordError("release_record_profile_mismatch", profile)
    entry = candidates[0]
    verify_archive_digest(archive_path, entry["archive_sha256"])
    read_archive_profile(archive_path, expected_profile=profile)
    if not record["tests"] or any(row["returncode"] != 0 or row["source_snapshot_sha256"] != record["source"]["content_sha256"] for row in record["tests"]):
        raise ReleaseRecordError("unbound_release_test_evidence", "tests")
    return entry


def build_record(output: Path, interpreters=None):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ReleaseRecordError("record_output_inside_source", "use a separate temporary directory")
    output.mkdir(parents=True, exist_ok=False)
    before = source_snapshot()
    tests = []
    commands = [[sys.executable, "-m", "pytest", "-q"], [sys.executable, "tools/verify_sidscope_resource_package.py"], [sys.executable, "tools/verify_sidscope_release_profiles.py"]]
    matrix_command = [sys.executable, "tools/verify_sidscope_distribution_install.py", "--output-dir", str(output / "distribution")]
    for interpreter in interpreters or [sys.executable]:
        matrix_command.extend(["--python", interpreter])
    commands.append(matrix_command)
    for index, command in enumerate(commands):
        run = subprocess.run(command, cwd=ROOT, capture_output=True)
        log = output / f"test-{index}.log"
        log.write_bytes(run.stdout + run.stderr)
        tests.append({"command": command[1:], "returncode": run.returncode, "output_sha256": sha(log), "source_snapshot_sha256": before["content_sha256"]})
        if run.returncode:
            raise ReleaseRecordError("candidate_test_failed", log.name)
    archives = []
    for profile in ("runtime", "conformance", "evidence-full"):
        path = output / (profile + ".zip")
        built = build_archive(manifest_path=DEFAULT_MANIFEST, output_path=path, profile_id=profile)
        # The expected digest comes from the trusted source-side builder, not
        # from the archive that is about to execute code.
        smoke = smoke_archive(path, expected_profile=profile, expected_sha256=built["archive_sha256"])
        (output / (profile+"-smoke.json")).write_text(json.dumps(smoke, sort_keys=True)+"\n")
        archives.append({"profile": profile, "archive_sha256": built["archive_sha256"], "source_snapshot_sha256": built["profile_receipt"]["source_snapshot_sha256"], "smoke": smoke["status"]})
        command = [sys.executable, "tools/run_sidscope_g8_fresh_env_smoke.py", "--archive", str(path), "--profile", profile, "--expected-sha256", built["archive_sha256"], "--result-json", str(output / (profile+"-g8.json"))]
        run = subprocess.run(command, cwd=ROOT, capture_output=True)
        log = output / (profile+"-g8.log")
        log.write_bytes(run.stdout + run.stderr)
        tests.append({"command": ["G8", profile], "returncode": run.returncode, "output_sha256": sha(log), "source_snapshot_sha256": before["content_sha256"]})
        if run.returncode:
            raise ReleaseRecordError("candidate_g8_failed", log.name)
    if source_snapshot() != before:
        raise ReleaseRecordError("source_changed_during_verification", "rerun on a stable snapshot")
    record = with_content_sha256({"format": "sidscope.local_release_record.v1", "status": "pass", "source": before, "tests": tests, "archives": archives, "distribution_matrix_sha256": sha(output / "distribution/result.json"), "build_environment": {"python": platform.python_version(), "platform": platform.platform()}, "release_authorized": False, "independent_user_acceptance": "not_established_by_automated_tests"})
    path = output / "release-record.json"
    path.write_bytes(canonical_json_bytes(record)+b"\n")
    return {"status": "pass", "record_sha256": sha(path), "source_snapshot_sha256": before["content_sha256"], "dirty": before["dirty"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build"); build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--python", action="append", default=[])
    verify = commands.add_parser("verify")
    verify.add_argument("--record", type=Path, required=True); verify.add_argument("--expected-record-sha256", required=True)
    verify.add_argument("--archive", type=Path, required=True); verify.add_argument("--profile", required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_record(args.output_dir, args.python)
    else:
        result = verify_record(args.record, expected_record_sha256=args.expected_record_sha256, archive_path=args.archive, profile=args.profile)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
