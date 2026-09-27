#!/usr/bin/env python3
"""Measure current CPU commands against an immutable baseline; never bless drift."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.benchmark_sidscope_1_2_cli import ROOT, OUTPUT, measure
    from tools.sidscope_performance_policy import (
        PerformancePolicyError,
        environment_comparability,
        explain_environment_extras,
        measurement_validity,
        median_ratios,
        threshold_value,
    )
except ModuleNotFoundError:
    from benchmark_sidscope_1_2_cli import ROOT, OUTPUT, measure
    from sidscope_performance_policy import (
        PerformancePolicyError,
        environment_comparability,
        explain_environment_extras,
        measurement_validity,
        median_ratios,
        threshold_value,
    )
from sidinspector.version import PRODUCT_VERSION


def classify(baseline: dict, current: dict) -> tuple[str, dict]:
    try:
        measurement_validity(baseline.get("commands"), current.get("commands"))
        ratios = median_ratios(baseline["commands"], current["commands"])
    except PerformancePolicyError as error:
        if error.code == "workload_command_set_mismatch":
            return "workload_review_required", {}
        return "invalid_measurement", {}
    if any(ratio > threshold_value(baseline["policy"]) for ratio in ratios.values()):
        return "performance_review_required", ratios
    state = "environment_review_required" if baseline["environment"] != current["environment"] else "pass"
    return state, ratios


def delivery_gate(baseline: dict, current: dict) -> dict:
    """Apply a narrow, deterministic delivery policy without rewriting the baseline."""
    observation_status, ratios = classify(baseline, current)
    threshold = threshold_value(baseline["policy"])
    within_threshold = bool(ratios) and all(ratio <= threshold for ratio in ratios.values())
    detail = environment_comparability(baseline.get("environment"), current.get("environment"))
    detail.update(explain_environment_extras(baseline.get("environment"), current.get("environment")))
    disposition = None
    if observation_status == "pass" and detail.get("code") == "same_environment":
        disposition = "same_environment_within_threshold"
    elif observation_status == "environment_review_required":
        if not detail.get("comparable"):
            disposition = None
        elif detail["code"] == "platform_version_only" and within_threshold:
            disposition = "platform_version_variance_within_frozen_threshold"
    status = "pass" if disposition is not None else "blocked"
    return {"status": status, "observation_status": observation_status,
            "disposition": disposition,
            "environment_comparison": {key: value for key, value in detail.items() if key != "comparable"},
            "comparison_code": detail.get("code"),
            "changed_environment_fields": detail.get("changed_environment_fields", []),
            "median_ratios": ratios,
            "policy": "Only a platform-version-only variance on identical OS family, architecture, bitness, Python version, implementation and processor may be accepted, and only when every frozen workload remains within threshold; unparseable or incomplete identity blocks."}


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
