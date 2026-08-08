#!/usr/bin/env python3
"""Run bounded SIDScope reviewer-package regeneration checks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "examples" / "sidscope_sampled_regeneration_output"


def run(cmd: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
    }


def require(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SIDScope sampled regeneration checks.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    quickstart_out = out / "reviewer_quickstart"
    commands = [
        run(
            [
                sys.executable,
                "examples/run_reviewer_quickstart.py",
                "--output-dir",
                str(quickstart_out),
            ]
        ),
        run([sys.executable, "tools/verify_reproducibility_matrix.py"]),
    ]

    expected_outputs = [
        require(quickstart_out / "preflight_summary.json"),
        require(quickstart_out / "diagnostics" / "d1_utilization.csv"),
        require(quickstart_out / "diagnostics" / "d2_collision.csv"),
        require(quickstart_out / "diagnostics" / "d3_alignment.csv"),
        require(quickstart_out / "diagnostics" / "d4_head_tail.csv"),
        require(quickstart_out / "diagnostics" / "d5a_deployment_cost.csv"),
        require(ROOT / "docs" / "reproducibility_matrix.csv"),
        require(ROOT / "docs" / "reproducibility" / "sidscope_sampled_regeneration_manifest.csv"),
    ]

    result = {
        "schema": "sidscope.sampled_regeneration.v1",
        "status": "pass",
        "gpu_required": False,
        "evidence_level": "fully_runnable_quickstart_plus_tracked_snapshot_validation",
        "output_dir": str(out),
        "commands": commands,
        "expected_outputs": expected_outputs,
        "boundary": "Does not regenerate raw upstream tokenizer artifacts or full paper tables.",
    }

    result_path = args.result_json or out / "sampled_regeneration_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
