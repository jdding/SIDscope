#!/usr/bin/env python3
"""Verify the checked-in shared-command CPU baseline and regression policy."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs/reproducibility/sidscope_1_2_cli_cpu_baseline.json"
REQUIRED = {"adapter_preflight", "contract_validate", "trace_validate", "evaluate", "verify", "evidence_package"}


def main() -> None:
    value = json.loads(PATH.read_text(encoding="utf-8"))
    if value.get("schema") != "sidscope.cli_cpu_baseline.v1" or value.get("status") != "pass":
        raise ValueError("invalid CPU baseline identity")
    if set(value.get("commands", {})) != REQUIRED:
        raise ValueError("CPU baseline command coverage mismatch")
    if value.get("policy", {}).get("review_threshold_percent") != 20:
        raise ValueError("CPU regression review threshold drift")
    for name, measurement in value["commands"].items():
        if measurement.get("repeats", 0) < 5 or measurement.get("median_ms", 0) <= 0:
            raise ValueError(f"invalid CPU baseline measurement: {name}")
    print(json.dumps({
        "schema": "sidscope.cli_cpu_baseline_verification.v1",
        "status": "pass",
        "command_count": len(REQUIRED),
        "review_threshold_percent": 20,
        "comparison_state": value["policy"]["comparison_state"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
