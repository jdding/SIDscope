#!/usr/bin/env python3
"""Verify the local SIDScope reviewer-resource package contract."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "src/sidinspector/__init__.py",
    "src/sidinspector/metrics.py",
    "src/sidinspector/preflight.py",
    "src/sidinspector/d7_trace.py",
    "src/sidinspector/conformance.py",
    "examples/minimal_adapter.py",
    "examples/run_toy_diagnostic.py",
    "examples/run_reviewer_quickstart.py",
    "examples/sample_data/sid_codes.csv",
    "examples/sample_data/item_metadata.csv",
    "examples/sample_data/interactions.csv",
    "examples/reviewer_quickstart_data/sid_codes.csv",
    "examples/reviewer_quickstart_data/item_metadata.csv",
    "examples/reviewer_quickstart_data/interactions.csv",
    "docs/ADAPTER_TEMPLATE.md",
    "docs/ADAPTER_CONFORMANCE.md",
    "docs/DIAGNOSTICS.md",
    "docs/PROBE_INTERPRETATION.md",
    "docs/REPRODUCIBILITY_MATRIX.md",
    "docs/SIDSCOPE_RESOURCE_PACKAGE.md",
    "docs/SIDSCOPE_USAGE_DEMO.md",
    "docs/SIDSCOPE_DATASHEET.md",
    "docs/SIDSCOPE_LIMITATIONS.md",
    "docs/SIDSCOPE_MAINTENANCE.md",
    "docs/SIDSCOPE_CHANGELOG.md",
    "docs/SIDSCOPE_RELEASE_CHECKLIST.md",
    "docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md",
    "docs/RESOT_RESOURCE_WALKTHROUGH.md",
    "docs/reproducibility_matrix.csv",
    "docs/reproducibility/sidscope_sampled_regeneration_manifest.csv",
    "docs/reproducibility/sidscope_release_candidate_manifest.csv",
    "docs/reproducibility/sidscope_paper_protocol_config.json",
    "docs/reproducibility/g14_usage_demo_decisions.csv",
    "docs/reproducibility/g14_usage_demo_summary.json",
    "docs/reproducibility/d7_labeled_trace_rows.csv.gz",
    "docs/reproducibility/d7_labeled_trace_release.json",
    "docs/reproducibility/sidscope_source_license_config_inventory.csv",
    "docs/reproducibility/conformance/adapter_manifest.schema.json",
    "docs/reproducibility/conformance/resot_instruments_manifest.json",
    "docs/reproducibility/conformance/resot_instruments_report.json",
    "docs/reproducibility/conformance/resid_gaoq_video_manifest.json",
    "docs/reproducibility/conformance/resid_gaoq_video_report.json",
    "docs/reproducibility/conformance/grid_p5_beauty_manifest.json",
    "docs/reproducibility/conformance/grid_p5_beauty_report.json",
    "docs/reproducibility/conformance/card_p5_beauty_manifest.json",
    "docs/reproducibility/conformance/card_p5_beauty_report.json",
    "docs/reproducibility/conformance/diger_beauty_manifest.json",
    "docs/reproducibility/conformance/diger_beauty_report.json",
    "docs/reproducibility/conformance/diger_yelp_manifest.json",
    "docs/reproducibility/conformance/diger_yelp_report.json",
    "docs/reproducibility/conformance/letter_instruments_manifest.json",
    "docs/reproducibility/conformance/letter_instruments_report.json",
    "docs/reproducibility/conformance/lcrec_instruments_manifest.json",
    "docs/reproducibility/conformance/lcrec_instruments_report.json",
    "docs/reproducibility/resot_walkthrough_sources.json",
    "docs/reproducibility/resot_resource_walkthrough.json",
    "examples/conformance_failure_fixture/manifest.json",
    "examples/conformance_failure_fixture/conformance_report.json",
    "tools/build_sidscope_release_candidate_archive.py",
    "tools/build_sidscope_paper_tables.py",
    "tools/verify_sidscope_claim_ledger.py",
    "tools/verify_sidscope_paper_tables.py",
    "tools/run_sidscope_realistic_tutorial.py",
    "tools/run_sidscope_usage_demo.py",
    "tools/run_sidscope_sampled_regeneration.py",
    "tools/smoke_sidscope_release_candidate_archive.py",
    "tools/run_sidscope_g8_fresh_env_smoke.py",
    "tools/run_sidscope_public_url_smoke.py",
    "tools/verify_reproducibility_matrix.py",
    "tools/check_adapter_conformance.py",
    "tools/verify_adapter_conformance_assets.py",
    "tools/verify_sidscope_source_inventory.py",
    "tools/verify_sidscope_d7_labeled_trace_release.py",
    "tools/build_resot_resource_walkthrough.py",
    "tools/verify_resot_resource_walkthrough.py",
    "tools/run_v1_gate2_cross_dataset_utility.py",
    "tools/run_v1_gate10_independent_utility.py",
    "tools/run_v1_gate12b_sequence_generator_anchor.py",
    "tests/__init__.py",
    "tests/local_test_bootstrap.py",
]


FORBIDDEN_TRACKED_PATTERNS = [
    ".aris/",
    ".codex/",
    ".agents/",
    ".codegraph/",
    "experiments/v1_evidence_chain/upstreams/",
    "experiments/v1_evidence_chain/raw_hf_resid/",
    "experiments/v1_evidence_chain/autodl/payloads/",
    "experiments/v1_evidence_chain/autodl/returned/",
    "experiments/v1_evidence_chain/archive/invalid_downloads/",
]


FORBIDDEN_TRACKED_SUFFIXES = (
    ".pt",
    ".ckpt",
    ".parquet",
    ".pkl",
    ".npy",
    ".tgz",
    ".sha256",
)


PACKAGE_SCAN_EXCLUDED_PARTS = {
    ".git",
    ".aris",
    ".codex",
    ".agents",
    ".codegraph",
    ".pytest_cache",
    "__pycache__",
}

PACKAGE_SCAN_EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}

PUBLIC_CONTENT_FORBIDDEN_TOKENS = (
    "/Users/",
    "/Volumes/",
    "/private/",
    "root@",
    "connect.west",
    "autodl-tmp",
    "Codex",
    "Claude",
    "ChatGPT",
)

PUBLIC_CONTENT_TOKEN_DECLARATION_ALLOWLIST = {
    "tools/verify_sidscope_claim_ledger.py",
    "tools/verify_sidscope_resource_package.py",
}


RELEASE_MANIFEST_REQUIRED_COLUMNS = {
    "component",
    "path",
    "release_role",
    "evidence_level",
    "public_package",
    "gate_status",
    "notes",
}

ALLOWED_EVIDENCE_LEVELS = {
    "fully_runnable",
    "tracked_snapshot",
    "provenance_only",
    "documentation",
    "excluded",
}

ALLOWED_GATE_STATUSES = {
    "pass_local",
    "pending_public_release",
    "pending_g8",
    "appendix_provenance",
    "excluded",
}


def run(cmd: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    record = {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
    }
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(record, indent=2, sort_keys=True))
    return record


def require_file(path: str) -> None:
    if not (ROOT / path).is_file():
        raise FileNotFoundError(path)


def tracked_files() -> list[str]:
    try:
        result = subprocess.check_output(
            ["git", "ls-files"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        paths = [line for line in result.splitlines() if line]
        if paths:
            return paths
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return scanned_package_files()


def scanned_package_files() -> list[str]:
    paths: list[str] = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part in PACKAGE_SCAN_EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.is_dir():
            continue
        if path.suffix in PACKAGE_SCAN_EXCLUDED_SUFFIXES:
            continue
        paths.append(rel.as_posix())
    return sorted(paths)


def check_forbidden_tracked(paths: list[str]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if path.endswith(FORBIDDEN_TRACKED_SUFFIXES):
            findings.append(path)
            continue
        if any(path.startswith(pattern) for pattern in FORBIDDEN_TRACKED_PATTERNS):
            findings.append(path)
    return findings


def is_text_content(path: Path) -> bool:
    try:
        chunk = path.read_bytes()
    except OSError:
        return False
    if b"\0" in chunk[:4096]:
        return False
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def is_allowed_safety_token_declaration(rel_path: str, line: str, token: str) -> bool:
    if rel_path not in PUBLIC_CONTENT_TOKEN_DECLARATION_ALLOWLIST:
        return False
    stripped = line.strip()
    quoted = {f'"{token}"', f"'{token}'"}
    return any(value in stripped for value in quoted)


def check_forbidden_public_content(paths: list[str]) -> list[str]:
    findings: list[str] = []
    for rel_path in paths:
        path = ROOT / rel_path
        if not path.is_file() or not is_text_content(path):
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for token in PUBLIC_CONTENT_FORBIDDEN_TOKENS:
                if token not in line:
                    continue
                if is_allowed_safety_token_declaration(rel_path, line, token):
                    continue
                findings.append(f"{rel_path}:{line_number}: forbidden public-package token {token!r}")
    return findings


def validate_release_manifest(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise RuntimeError(f"release manifest has no rows: {path}")

    columns = set(rows[0])
    missing_columns = sorted(RELEASE_MANIFEST_REQUIRED_COLUMNS - columns)
    if missing_columns:
        raise RuntimeError(f"release manifest missing columns: {missing_columns}")

    public_rows = 0
    pending_rows = 0
    for index, row in enumerate(rows, start=2):
        rel_path = row["path"].strip()
        evidence_level = row["evidence_level"].strip()
        gate_status = row["gate_status"].strip()
        public_package = row["public_package"].strip().lower()

        if evidence_level not in ALLOWED_EVIDENCE_LEVELS:
            raise RuntimeError(f"invalid evidence_level at manifest line {index}: {evidence_level}")
        if gate_status not in ALLOWED_GATE_STATUSES:
            raise RuntimeError(f"invalid gate_status at manifest line {index}: {gate_status}")
        if public_package not in {"yes", "no"}:
            raise RuntimeError(f"invalid public_package at manifest line {index}: {public_package}")
        if rel_path.startswith("/") or ".." in Path(rel_path).parts:
            raise RuntimeError(f"non-package-relative manifest path at line {index}: {rel_path}")
        if public_package == "yes":
            public_rows += 1
            if rel_path.startswith(tuple(FORBIDDEN_TRACKED_PATTERNS)) or rel_path.endswith(FORBIDDEN_TRACKED_SUFFIXES):
                raise RuntimeError(f"forbidden public-package manifest path at line {index}: {rel_path}")
            if not (ROOT / rel_path).exists():
                raise FileNotFoundError(f"release manifest row points to missing package path: {rel_path}")

        if gate_status.startswith("pending_"):
            pending_rows += 1

    return {
        "rows": len(rows),
        "public_package_rows": public_rows,
        "pending_rows": pending_rows,
    }


def public_manifest_paths(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [row["path"].strip() for row in rows if row.get("public_package", "").strip().lower() == "yes"]


def expand_public_manifest_paths(manifest_path: Path, tracked: list[str]) -> list[str]:
    public_roots = public_manifest_paths(manifest_path)
    included: set[str] = set()
    for rel_path in public_roots:
        if rel_path in tracked:
            included.add(rel_path)
            continue

        prefix = rel_path.rstrip("/") + "/"
        matches = [path for path in tracked if path.startswith(prefix)]
        if matches:
            included.update(matches)
            continue

        if not (ROOT / rel_path).exists():
            raise FileNotFoundError(f"release manifest public path is missing: {rel_path}")
        raise RuntimeError(f"release manifest public path is not tracked: {rel_path}")

    return sorted(included)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify SIDScope reviewer-resource package contract.")
    parser.add_argument("--skip-sampled-regeneration", action="store_true")
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path in REQUIRED_FILES:
        require_file(path)

    tracked = tracked_files()
    forbidden = check_forbidden_tracked(tracked)
    if forbidden:
        formatted = "\n".join(f"  - {path}" for path in forbidden[:50])
        raise RuntimeError(f"forbidden package-boundary files are tracked:\n{formatted}")

    release_manifest = validate_release_manifest(
        ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"
    )
    public_package_paths = expand_public_manifest_paths(
        ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
        tracked,
    )
    public_content_findings = check_forbidden_public_content(public_package_paths)
    if public_content_findings:
        formatted = "\n".join(f"  - {finding}" for finding in public_content_findings[:50])
        raise RuntimeError(f"forbidden content in public-package files:\n{formatted}")

    claim_ledger_command = [
        sys.executable,
        "tools/verify_sidscope_claim_ledger.py",
        "--package-mode",
        "--result-json",
        "/tmp/sidscope_claim_ledger_verification.json",
    ]

    commands = [
        run([sys.executable, "-c", "import sidinspector; print(sidinspector.__name__)"]),
        run([sys.executable, "tools/verify_reproducibility_matrix.py"]),
        run([sys.executable, "tools/verify_sidscope_paper_tables.py"]),
        run([sys.executable, "tools/verify_sidscope_source_inventory.py"]),
        run([sys.executable, "tools/verify_adapter_conformance_assets.py"]),
        run([sys.executable, "tools/verify_resot_resource_walkthrough.py"]),
        run([sys.executable, "tools/verify_sidscope_d7_labeled_trace_release.py"]),
        run(claim_ledger_command),
    ]

    if not args.skip_sampled_regeneration:
        with tempfile.TemporaryDirectory(prefix="sidscope-package-") as tmp:
            commands.append(
                run(
                    [
                        sys.executable,
                        "tools/run_sidscope_sampled_regeneration.py",
                        "--output-dir",
                        str(Path(tmp) / "sampled"),
                    ]
                )
            )

    result = {
        "schema": "sidscope.resource_package_verification.v1",
        "status": "pass",
        "gpu_required": False,
        "required_files_checked": len(REQUIRED_FILES),
        "release_manifest": release_manifest,
        "tracked_files_checked": len(tracked),
        "forbidden_tracked_findings": forbidden,
        "public_package_files_checked": len(public_package_paths),
        "forbidden_public_content_findings": public_content_findings,
        "sampled_regeneration": "skipped" if args.skip_sampled_regeneration else "passed",
        "commands": commands,
        "boundary": "Local G8 package contract verifier. Local clean-extract and public URL smoke are recorded separately by R603/R708 for the active reviewer package tag.",
    }

    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
