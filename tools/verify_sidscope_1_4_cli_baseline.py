#!/usr/bin/env python3
"""Verify coverage and policy for the SIDScope 1.4 evidence CLI baseline."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs" / "reproducibility" / "sidscope_1_4_cli_cpu_baseline.json"
REQUIRED = {
    "evidence_bundle_build",
    "evidence_bundle_verify",
    "registry_add",
    "registry_list",
    "registry_compare",
    "registry_rebuild",
}


def main() -> None:
    value = json.loads(PATH.read_text(encoding="utf-8"))
    if value.get("schema") != "sidscope.cli_cpu_baseline.v1" or value.get("status") != "pass":
        raise ValueError("invalid CPU baseline identity")
    if value.get("product_version") != "1.4.0.dev0":
        raise ValueError("CPU baseline product version mismatch")
    if set(value.get("commands", {})) != REQUIRED:
        raise ValueError("evidence CLI baseline coverage mismatch")
    if value.get("policy", {}).get("review_threshold_percent") != 20:
        raise ValueError("CPU regression review threshold drift")
    if value.get("policy", {}).get("gpu_required") is not False:
        raise ValueError("evidence CLI baseline must remain CPU-only")
    for name, measurement in value["commands"].items():
        if measurement.get("repeats", 0) < 5 or measurement.get("median_ms", 0) <= 0:
            raise ValueError(f"invalid CPU baseline measurement: {name}")
    print(
        json.dumps(
            {
                "schema": "sidscope.cli_cpu_baseline_verification.v1",
                "status": "pass",
                "product_version": value["product_version"],
                "command_count": len(REQUIRED),
                "review_threshold_percent": 20,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
