#!/usr/bin/env python3
"""Run and validate the SIDScope reviewer tutorial path for R509."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(tempfile.gettempdir()) / "sidscope_realistic_tutorial"
DEFAULT_RESULT = ROOT / "experiments" / "v1_evidence_chain" / "runs" / "R509_sidscope_realistic_tutorial.json"


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


def require_file(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)


def require_columns(frame: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise RuntimeError(f"{path} missing columns: {missing}")


def validate_tutorial_output(output_dir: Path) -> dict[str, Any]:
    normalized = output_dir / "normalized"
    diagnostics = output_dir / "diagnostics"
    preflight_path = output_dir / "preflight_summary.json"

    expected_outputs = [
        require_file(normalized / "sid_assignments.parquet"),
        require_file(normalized / "item_metadata.parquet"),
        require_file(normalized / "interactions.parquet"),
        require_file(preflight_path),
        require_file(diagnostics / "d1_utilization.csv"),
        require_file(diagnostics / "d2_collision.csv"),
        require_file(diagnostics / "d3_alignment.csv"),
        require_file(diagnostics / "d4_head_tail.csv"),
        require_file(diagnostics / "d5a_deployment_cost.csv"),
    ]

    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("status") != "passed":
        raise RuntimeError(f"preflight did not pass: {preflight.get('status')}")

    sid = pd.read_parquet(normalized / "sid_assignments.parquet")
    metadata = pd.read_parquet(normalized / "item_metadata.parquet")
    interactions = pd.read_parquet(normalized / "interactions.parquet")
    require_columns(sid, {"item_id", "sid_level_1", "sid_level_2"}, normalized / "sid_assignments.parquet")
    sid_level_columns = [col for col in sid.columns if col.startswith("sid_level_")]
    if len(sid_level_columns) < 2:
        raise RuntimeError("tutorial SID assignments must include at least two sid_level_* columns")
    require_columns(metadata, {"item_id"}, normalized / "item_metadata.parquet")
    require_columns(interactions, {"user_id", "item_id"}, normalized / "interactions.parquet")
    if len(sid) < 10 or len(metadata) < 10 or len(interactions) < 10:
        raise RuntimeError("tutorial data is too small to exercise adapter/preflight/metric flow")

    d1 = pd.read_csv(diagnostics / "d1_utilization.csv")
    d2 = pd.read_csv(diagnostics / "d2_collision.csv")
    d3 = pd.read_csv(diagnostics / "d3_alignment.csv")
    d4 = pd.read_csv(diagnostics / "d4_head_tail.csv")
    d5 = pd.read_csv(diagnostics / "d5a_deployment_cost.csv")

    for path, frame in {
        "d1_utilization.csv": d1,
        "d2_collision.csv": d2,
        "d3_alignment.csv": d3,
        "d4_head_tail.csv": d4,
        "d5a_deployment_cost.csv": d5,
    }.items():
        if frame.empty:
            raise RuntimeError(f"empty tutorial diagnostic output: {path}")

    require_columns(d2, {"prefix_depth", "full_collision_rate"}, diagnostics / "d2_collision.csv")
    require_columns(d3, {"prefix_depth", "weighted_collab_prefix_recall"}, diagnostics / "d3_alignment.csv")
    require_columns(d4, {"bucket", "sid_unique_ratio"}, diagnostics / "d4_head_tail.csv")
    require_columns(d5, {"sid_length", "unique_sid", "prefix_counts"}, diagnostics / "d5a_deployment_cost.csv")

    d2_full = d2[d2["prefix_depth"] == int(d5.iloc[0]["sid_length"])]
    if d2_full.empty:
        raise RuntimeError("D2 output has no full-depth row matching D5 sid_length")
    d3_depth1 = d3[d3["prefix_depth"] == 1]
    if d3_depth1.empty:
        raise RuntimeError("D3 output has no depth-1 row")

    return {
        "expected_outputs": expected_outputs,
        "input_rows": {
            "sid_assignments": int(len(sid)),
            "item_metadata": int(len(metadata)),
            "interactions": int(len(interactions)),
        },
        "diagnostic_rows": {
            "d1": int(len(d1)),
            "d2": int(len(d2)),
            "d3": int(len(d3)),
            "d4": int(len(d4)),
            "d5": int(len(d5)),
        },
        "summary_metrics": {
            "sid_length": int(d5.iloc[0]["sid_length"]),
            "unique_sid": int(d5.iloc[0]["unique_sid"]),
            "d2_full_collision_rate": float(d2_full.iloc[0]["full_collision_rate"]),
            "d3_depth1_weighted_collab_prefix_recall": float(d3_depth1.iloc[0]["weighted_collab_prefix_recall"]),
            "d5_prefix_counts": str(d5.iloc[0]["prefix_counts"]),
        },
    }


def run_tutorial(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    command = run([sys.executable, "examples/run_reviewer_quickstart.py", "--output-dir", str(output_dir)])
    validation = validate_tutorial_output(output_dir)
    return {
        "schema": "sidscope.realistic_tutorial.v1",
        "run_id": "R509",
        "status": "pass",
        "gpu_required": False,
        "output_dir": str(output_dir),
        "commands": [command],
        "validation": validation,
        "boundary": "CPU reviewer tutorial only; validates realistic adapter/preflight/D1-D5 flow, not full paper-table regeneration.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and validate the SIDScope R509 reviewer tutorial.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result-json", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_tutorial(args.output_dir)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
