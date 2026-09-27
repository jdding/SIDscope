#!/usr/bin/env python3
"""Offline checks of authorized native observations and complete mapping joins.

Does not execute source code or load private runtime assets. The receipt is an
observation acceptance record, NOT a canonical EvidenceBundle or training proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from sidinspector.contracts import canonical_sha256, with_content_sha256
from sidinspector.contracts.json_io import loads_json
from sidscope.native_bridge import (
    DATASETS,
    compare_exports,
    fail,
    project_export,
    validate_observed_inputs,
)


def verify_observation(source, output):
    source, output = Path(source), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    blobs = {name: (source / (name + ".json")).read_bytes() for name in ("native", "selection", "observations", "preflight")}
    docs = {name: loads_json(blob, max_bytes=None) for name, blob in blobs.items()}
    hashes = {name: hashlib.sha256(blob).hexdigest() for name, blob in blobs.items()}
    projection = project_export(source / "native.json", selection=source / "selection.json")
    method = validate_observed_inputs(docs["native"], docs["selection"], docs["observations"], docs["preflight"],
        native_sha256=hashes["native"], preflight_sha256=hashes["preflight"])
    from sidscope.mapping_check import preflight
    started = time.perf_counter()
    inputs = dict(docs["preflight"])
    original_dataset = inputs["dataset"]
    inputs["dataset"] = DATASETS[method]
    report = preflight(**inputs)
    seconds = time.perf_counter() - started
    comparison = compare_exports(source / "native.json", source / "native.json",
        left_selection=source / "selection.json", right_selection=source / "selection.json")
    # Reject concurrent replacement of input files; do not bless mixed snapshots.
    if any(hashlib.sha256((source / (name + ".json")).read_bytes()).hexdigest() != digest for name, digest in hashes.items()):
        fail("native_observation_input_changed", "input changed during verification")
    receipt = with_content_sha256({"format": "sidscope.native_observation_receipt.v1", "status": "pass",
        "method": method, "input_sha256": hashes, "dataset_identity_conversion": {"from": original_dataset, "to": DATASETS[method]},
        "projection_sha256": projection["content_sha256"], "mapping_report_sha256": report["content_sha256"],
        "mapping_checks": report["checks"], "unavailable_mapping_checks": report["unavailable"],
        "metrics": projection["metrics"], "measurements": docs["observations"]["measurements"],
        "measurement_scope": docs["observations"]["compute_scope"],
        "preflight_elapsed_seconds": seconds, "verifier_peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "verifier_platform": sys.platform,
        "comparison_kind": comparison["comparison_kind"], "comparison_sha256": comparison["content_sha256"],
        "verification_scope": "supplied_native_export_labels_measurement_consistency_and_mapping_joins",
        "unverified": ["training_reproducibility", "independent_runtime_authenticity", "cross_run_or_seed_improvement", "canonical_bundle_admission", "independent_user_acceptance"]})
    output.mkdir(parents=True, exist_ok=False)
    for name, doc in (("mapping-report", report), ("projection", projection), ("comparison", comparison), ("complete", receipt)):
        with (output / (name + ".json")).open("x") as handle:
            json.dump(doc, handle, sort_keys=True, allow_nan=False)
            handle.write("\n")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = verify_observation(args.input, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps({"status": "pass", "content_sha256": receipt["content_sha256"], "mapping_checks": receipt["mapping_checks"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
