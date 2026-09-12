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
    if any(value > threshold for value in ratios.values()):
        return "performance_review_required", ratios
    state = "environment_review_required" if baseline["environment"] != current["environment"] else "pass"
    return state, ratios


def delivery_gate(baseline: dict, current: dict) -> dict:
    """Apply a narrow, deterministic delivery policy without rewriting the baseline."""
    observation_status, ratios = classify(baseline, current)
    changed = sorted(key for key in set(baseline["environment"]) | set(current["environment"])
                     if baseline["environment"].get(key) != current["environment"].get(key))
    disposition = "same_environment_within_threshold" if observation_status == "pass" else None
    if observation_status == "environment_review_required" and changed == ["platform"] and ratios:
        disposition = "platform_version_variance_within_frozen_threshold"
    status = "pass" if disposition is not None else "blocked"
    return {"status": status, "observation_status": observation_status,
            "disposition": disposition, "changed_environment_fields": changed,
            "median_ratios": ratios,
            "policy": "Only a platform-version-only variance may be accepted when every frozen workload remains within threshold."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=OUTPUT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-delivery", action="store_true")
    args = parser.parse_args()
    if args.output is not None and (args.output.resolve() == ROOT or ROOT in args.output.resolve().parents):
        parser.error("performance_output_must_be_outside_repository")
    baseline_bytes = args.baseline.read_bytes()
    baseline = json.loads(baseline_bytes)
    current = measure()
    state, ratios = classify(baseline, current)
    gate = delivery_gate(baseline, current)
    payload = {
        "status": state, "product_version": PRODUCT_VERSION,
        "gpu_required": False, "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "environment": current["environment"], "commands": current["commands"],
        "median_ratios": ratios, "review_threshold_percent": baseline["policy"]["review_threshold_percent"],
        "delivery_gate": gate,
        "boundary": "Fresh in-process fixture workload only; not scale, cold-start, GPU, or user acceptance. Observation status is never relabeled; a narrow delivery disposition is recorded separately.",
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    print(serialized, end="")
    return 0 if (gate["status"] == "pass" if args.require_delivery else state == "pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
