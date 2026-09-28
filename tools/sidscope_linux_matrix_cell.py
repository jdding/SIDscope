#!/usr/bin/env python3
"""Assemble one Linux matrix cell from executed step outputs (in-container).

The committed companion `tools/run_sidscope_linux_matrix_cell.sh` executes the
fixed required commands, writes each step's stdout/stderr and exit code to the
steps directory, and then runs this assembler. It computes the mounted tree's
source manifest with the shared rule, builds the combined log (per-step marker
appended only for exit-0 steps), and writes the cell JSON next to the log.
It executes nothing and decides nothing about acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sidscope_linux_matrix_cells import REQUIRED_STEPS, cell_log_filename
from tools.sidscope_source_manifest import tree_manifest_digest

STEP_FILES = {"pytest": "tests", "metadata": "tools/verify_sidscope_release_metadata.py",
              "architecture": "tools/verify_sidscope_architecture_inventory.py",
              "sdlc_acceptance": "tools/verify_sidscope_sdlc_acceptance.py",
              "sdlc_hardening": "tools/verify_sidscope_sdlc_hardening.py",
              "profiles": "tools/verify_sidscope_release_profiles.py",
              "resource": "tools/verify_sidscope_resource_package.py"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--steps-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-manifest", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--public-snapshot-digest", required=True)
    args = parser.parse_args()

    manifest = tree_manifest_digest(args.workspace)
    steps = []
    combined = []
    worst = 0
    for name in REQUIRED_STEPS:
        step_dir = args.steps_dir / name
        exit_code = int((step_dir / "exitcode").read_text().strip())
        output = (step_dir / "output.log").read_bytes()
        combined.append(f"=== step {name} exit {exit_code} ===".encode())
        combined.append(output)
        worst = max(worst, exit_code)
        marker = f"STEP-OK {name} {args.python_version}"
        entry = {"name": name, "exit_code": exit_code, "passed_count": None,
                 "log_marker": marker}
        if name == "pytest":
            tail = [line for line in output.decode(errors="replace").splitlines() if line.strip()]
            match = re.search(rb"(\d+) passed", output) if not tail else None
            if tail:
                match = re.search(r"(\d+) passed", tail[-1])
            entry["passed_count"] = int(match.group(1)) if match else None
        if exit_code == 0:
            combined.append(marker.encode())
        steps.append(entry)
    log_path = args.output_dir / cell_log_filename(args.python_version)
    log_path.write_bytes(b"\n".join(combined))
    cell = {
        "python": args.python_version,
        # Identity recorded from this live runtime; the shared validator
        # cross-checks these against the claimed version and OS so a cell
        # assembled on a different machine/interpreter can never pass.
        "python_full": platform.python_version(),
        "raw_platform": platform.platform(),
        "image": args.image,
        "os": f"Linux {platform.release()} {platform.machine()}",
        "arch": platform.machine(),
        "interpreter": sys.executable,
        "source_manifest_sha256": manifest,
        "source_check": {"head": args.head, "public_snapshot_digest": args.public_snapshot_digest,
                         "clean": manifest == args.expected_manifest},
        "status": "pass" if worst == 0 and manifest == args.expected_manifest else "failed",
        "exit_code": worst,
        "head": args.head,
        "steps": steps,
        "log": {"path": log_path.name, "sha256": hashlib.sha256(log_path.read_bytes()).hexdigest()},
    }
    (args.output_dir / f"cell-{args.python_version}.json").write_text(
        json.dumps(cell, sort_keys=True, indent=1) + "\n")
    print(json.dumps({"cell": args.python_version, "status": cell["status"],
                      "manifest_match": manifest == args.expected_manifest}))
    return 0 if cell["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
