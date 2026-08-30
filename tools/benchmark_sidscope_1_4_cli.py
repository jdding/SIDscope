#!/usr/bin/env python3
"""Measure the CPU baseline for SIDScope 1.4 evidence command families."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.cli import main as cli_main


FIXTURE = ROOT / "examples" / "evidence_system_fixture"
OUTPUT = ROOT / "docs" / "reproducibility" / "sidscope_1_4_cli_cpu_baseline.json"


def timed(factory: Callable[[int], list[str]], repeats: int = 7) -> dict[str, object]:
    samples: list[float] = []
    for index in range(repeats):
        argv = factory(index)
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


def main() -> None:
    public = FIXTURE / "public_conformance_summary.json"
    public_sha = hashlib.sha256(public.read_bytes()).hexdigest()
    baseline = FIXTURE / "baseline_bundle.json"
    correction = FIXTURE / "correction_bundle.json"
    hashes = {
        name: json.loads((FIXTURE / name).read_text(encoding="utf-8"))["content_sha256"]
        for name in ("baseline_bundle.json", "correction_bundle.json")
    }
    with tempfile.TemporaryDirectory(prefix="sidscope-1-4-cli-benchmark-") as tmp:
        root = Path(tmp)
        shared = root / "shared-store"
        with contextlib.redirect_stdout(io.StringIO()):
            cli_main(
                [
                    "registry", "add", "--store", str(shared), "--bundle", str(baseline),
                    "--artifact", f"{public_sha}={public}",
                ]
            )
            cli_main(
                [
                    "registry", "supersede", "--store", str(shared),
                    "--prior", hashes["baseline_bundle.json"], "--bundle", str(correction),
                ]
            )
        commands = {
            "evidence_bundle_build": timed(
                lambda index: [
                    "evidence", "bundle", "build",
                    "--spec", str(FIXTURE / "baseline_bundle_spec.json"),
                    "--output", str(root / f"built-{index}.json"),
                ]
            ),
            "evidence_bundle_verify": timed(
                lambda _index: [
                    "evidence", "bundle", "verify", "--input", str(baseline)
                ]
            ),
            "registry_add": timed(
                lambda index: [
                    "registry", "add", "--store", str(root / f"add-{index}"),
                    "--bundle", str(baseline), "--artifact", f"{public_sha}={public}",
                ]
            ),
            "registry_list": timed(
                lambda _index: ["registry", "list", "--store", str(shared)]
            ),
            "registry_compare": timed(
                lambda _index: [
                    "registry", "compare", "--store", str(shared),
                    "--left", hashes["baseline_bundle.json"],
                    "--right", hashes["correction_bundle.json"],
                ]
            ),
            "registry_rebuild": timed(
                lambda _index: ["registry", "rebuild", "--store", str(shared)]
            ),
        }
    payload = {
        "schema": "sidscope.cli_cpu_baseline.v1",
        "status": "pass",
        "product_version": "1.4.0.dev0",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
        },
        "policy": {
            "review_threshold_percent": 20,
            "comparison_state": "evidence_command_baseline_established",
            "gpu_required": False,
        },
        "commands": commands,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
