#!/usr/bin/env python3
"""Measure current CPU commands against an immutable baseline; never bless drift."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.benchmark_sidscope_1_2_cli import ROOT, OUTPUT, measure
except ModuleNotFoundError:
    from benchmark_sidscope_1_2_cli import ROOT, OUTPUT, measure
from sidinspector.version import PRODUCT_VERSION


def classify(baseline: dict, current: dict) -> tuple[str, dict]:
    if baseline["environment"] != current["environment"]:
        return "environment_review_required", {}
    if set(baseline["commands"]) != set(current["commands"]):
        return "workload_review_required", {}
    ratios = {}
    for name, sample in current["commands"].items():
        before = baseline["commands"][name]["median_ms"]
        after = sample["median_ms"]
        if before <= 0 or after <= 0:
            return "invalid_measurement", {}
        ratios[name] = round(after / before, 4)
    threshold = 1 + baseline["policy"]["review_threshold_percent"] / 100
    state = "performance_review_required" if any(value > threshold for value in ratios.values()) else "pass"
    return state, ratios


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=OUTPUT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and (args.output.resolve() == ROOT or ROOT in args.output.resolve().parents):
        parser.error("performance_output_must_be_outside_repository")
    baseline_bytes = args.baseline.read_bytes()
    baseline = json.loads(baseline_bytes)
    current = measure()
    state, ratios = classify(baseline, current)
    payload = {
        "status": state, "product_version": PRODUCT_VERSION,
        "gpu_required": False, "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "environment": current["environment"], "commands": current["commands"],
        "median_ratios": ratios, "review_threshold_percent": baseline["policy"]["review_threshold_percent"],
        "boundary": "Fresh in-process fixture workload only; not scale, cold-start, GPU, or user acceptance. Review required never means pass.",
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    print(serialized, end="")
    return 0 if state == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
