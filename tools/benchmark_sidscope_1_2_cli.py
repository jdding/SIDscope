#!/usr/bin/env python3
"""Measure the first reproducible CPU baseline for shared SIDScope 1.2 commands."""

from __future__ import annotations

import contextlib
import io
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.cli import main as cli_main


FIXTURE = ROOT / "examples/canonical_pipeline_fixture"
OUTPUT = ROOT / "docs/reproducibility/sidscope_1_2_cli_cpu_baseline.json"


def timed(argv: list[str], repeats: int = 11) -> dict[str, object]:
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter_ns()
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli_main(argv)
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        if code != 0:
            raise RuntimeError(f"CLI failed ({code}): {argv}")
        samples.append(elapsed)
    return {
        "median_ms": round(statistics.median(samples), 6),
        "min_ms": round(min(samples), 6),
        "max_ms": round(max(samples), 6),
        "repeats": repeats,
    }


def measure() -> dict[str, object]:
    """Execute the shared workload without changing its frozen baseline."""
    with tempfile.TemporaryDirectory(prefix="sidscope-cli-benchmark-") as tmp:
        tmp_path = Path(tmp)
        artifacts = [
            "source_identity.json", "dataset_identity.json", "sid_space_identity.json",
            "prepared_dataset.json", "episode_selection.json", "run_identity.json",
            "checkpoint_binding.json", "trace_envelope.json", "diagnostic_report.json",
            "conformance_report.json",
        ]
        commands = {
            "adapter_preflight": ["adapter", "preflight", "--descriptor", str(FIXTURE / "adapter_capabilities.json")],
            "contract_validate": ["contract", "validate", "--type", "run-identity", "--input", str(FIXTURE / "run_identity.json")],
            "trace_validate": ["trace", "validate", "--input", str(FIXTURE / "trace_envelope.json")],
            "evaluate": ["evaluate", "--trace", str(FIXTURE / "trace_envelope.json"), "--selection", str(FIXTURE / "episode_selection.json"), "--output", str(tmp_path / "diagnostic.json")],
            "verify": ["verify", "--report", str(FIXTURE / "conformance_report.json")],
            "evidence_package": ["evidence", "package", "--index-id", "benchmark:index", "--output", str(tmp_path / "evidence.json"), *sum((["--artifact", str(FIXTURE / name)] for name in artifacts), [])],
        }
        measurements = {name: timed(argv) for name, argv in commands.items()}
    payload = {
        "schema": "sidscope.cli_cpu_baseline.v1",
        "status": "pass",
        "product_version": "1.2.0.dev0",
        "adapter_sdk_version": "0.1.0",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
        },
        "policy": {
            "review_threshold_percent": 20,
            "comparison_state": "baseline_established_no_prior_shared_command_baseline",
            "gpu_required": False,
        },
        "commands": measurements,
    }
    return payload


def main() -> None:
    payload = measure()
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
