#!/usr/bin/env python3
"""CPU-only local-input scale acceptance, one fresh process per measured cell.

Synthetic workload ceilings govern this test, not the product's allowed inputs.
No baseline is overwritten and no upstream training or native NFE is invented.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import importlib.metadata
import json
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sidscope.workflows import audit, evaluate, compare
from sidinspector.contracts.json_io import load_json


def source_hashes():
    names = ["src/sidscope/workflows.py", "src/sidinspector/contracts/json_io.py", "src/sidinspector/metrics.py", "src/sidinspector/contracts/report_contracts.py", "tools/benchmark_sidscope_local_workflows.py"]
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def worker(rows, kind):
    clock = time.perf_counter
    phase = {}
    with tempfile.TemporaryDirectory(prefix="sidscope-scale-input-") as directory:
        root = Path(directory)
        started = clock()
        if kind == "evaluate":
            inputs = {"predictions": [{"episode_id": str(i), "ranked_items": [None, i]} for i in range(rows)], "targets": [{"episode_id": str(i), "target_item_id": i, "slice": "slice-"+str(i % 4)} for i in range(rows)], "dataset": "synthetic-scale", "cutoff": 2}
            path = root / "evaluation.json"
            path.write_text(json.dumps(inputs))
            del inputs
        else:
            path = root / ("mapping."+kind)
            if kind == "json":
                items = [{"item_id": i, "sid": [i // 4096, (i // 256) % 16, i % 256, 0]} for i in range(rows)]
                path.write_text(json.dumps(items))
                del items
            else:
                import numpy as np
                import pandas as pd
                ids = np.arange(rows)
                frame = pd.DataFrame({"item_id": ids, "sid_level_0": ids // 4096, "sid_level_1": (ids // 256) % 16, "sid_level_2": ids % 256, "sid_level_3": np.zeros(rows, dtype="int64")})
                if kind == "csv":
                    frame.to_csv(path, index=False)
                else:
                    frame.to_parquet(path, index=False)
                del frame, ids
        phase["fixture_generation_s"] = clock() - started
        input_bytes = path.stat().st_size
        expanded = None
        if kind == "parquet":
            import pyarrow.parquet as pq
            metadata = pq.read_metadata(path)
            expanded = sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups))
        gc.collect()
        started = clock()
        if kind == "evaluate":
            inputs = load_json(path, max_bytes=None)
            phase["load_s"] = clock() - started
            started = clock()
            report = evaluate(**inputs)
            assert report["metrics"]["overall"]["episodes"] == rows
            assert report["metrics"]["overall"]["hit_at_cutoff"] == 1.0
            assert len(report["metrics"]["slices"]) == min(rows, 4)
            phase["evaluate_s"] = clock() - started
            del inputs
            started = clock()
            difference = compare(report, report)
            assert difference["overall_delta"]["hit_at_cutoff"] == 0
            phase["comparison_recomputation_s"] = clock() - started
        else:
            report = audit(path)
            assert report["metrics"]["D1_utilization"][0]["items"] == rows
            assert report["metrics"]["D2_aliasing"][0]["full_collision_items"] == 0
            phase["load_and_audit_s"] = clock() - started
        started = clock()
        payload = json.dumps(report, sort_keys=True, allow_nan=False).encode()
        phase["serialize_s"] = clock() - started
        output_bytes = len(payload)
        output_sha = hashlib.sha256(payload).hexdigest()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = int(rss if sys.platform == "darwin" else rss * 1024)
    return {"status": "pass", "kind": kind, "rows": rows, "input_bytes": input_bytes, "parquet_metadata_bytes": expanded, "output_bytes": output_bytes, "output_sha256": output_sha, "phase_seconds": phase, "process_peak_rss_bytes": peak_bytes, "nfe": None, "nfe_reason": "No native execution is represented by this synthetic mapping/ranking workload"}


def run_matrix(output, sizes, kinds, timeout, rss_mib):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    # Capture platform metadata before launching/mocking measured subprocesses.
    # On Linux platform.platform() may invoke uname through subprocess.run.
    platform_id = "-".join((platform.system(), platform.release(), platform.machine()))
    environment = {"python": platform.python_version(), "platform": platform_id,
        "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "pyarrow")}}
    cells = []
    for rows in sizes:
        for kind in kinds:
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--rows", str(rows), "--kind", kind]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                (output / f"{kind}-{rows}.log").write_text(result.stdout + result.stderr)
                cell = json.loads(result.stdout) if result.returncode == 0 else {"status": "fail", "kind": kind, "rows": rows, "returncode": result.returncode}
            except subprocess.TimeoutExpired:
                cell = {"status": "fail", "kind": kind, "rows": rows, "reason": "benchmark_timeout"}
            if cell.get("process_peak_rss_bytes", 0) > rss_mib * 1024 * 1024:
                cell.update(status="fail", reason="benchmark_rss_budget_exceeded")
            cells.append(cell)
            print(json.dumps({"kind": kind, "rows": rows, "status": cell["status"]}), flush=True)
            if cell["status"] != "pass":
                break
        if cells[-1]["status"] != "pass":
            break
    result = {"format": "sidscope.local_workflow_scale.v1", "status": "pass" if len(cells) == len(sizes)*len(kinds) and all(c["status"] == "pass" for c in cells) and before == source_hashes() else "fail", "source_files": before, "environment": environment, "benchmark_policy": {"sizes": sizes, "kinds": kinds, "timeout_seconds_per_cell": timeout, "post_run_peak_rss_mib_ceiling": rss_mib, "repeats": 1}, "cells": cells, "boundary": "Synthetic correctness and resource smoke, not a steady-state SLO, real adapter acceptance, total-machine memory cap or a new product input limit. Peak RSS includes fixture generation and imports; subprocess timeout is enforced. No GPU or native NFE measurement."}
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("profile_output"))
    parser.add_argument("--sizes", type=int, nargs="+", default=[10000, 100000, 1000000])
    parser.add_argument("--kinds", nargs="+", choices=["json", "csv", "parquet", "evaluate"], default=["json", "csv", "parquet", "evaluate"])
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--rss-mib", type=int, default=4096)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--rows", type=int)
    parser.add_argument("--kind", choices=["json", "csv", "parquet", "evaluate"])
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.rows, args.kind), sort_keys=True))
        return 0
    if any(size < 1 for size in args.sizes) or args.timeout <= 0 or args.rss_mib <= 0:
        parser.error("sizes and benchmark budgets must be positive")
    return 0 if run_matrix(args.output_dir, args.sizes, args.kinds, args.timeout, args.rss_mib)["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
