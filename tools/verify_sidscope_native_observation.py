#!/usr/bin/env python3
"""Offline checks of authorized native observations and complete mapping joins.

Does not execute source code or load private runtime assets. The receipt is an
observation acceptance record, NOT a canonical EvidenceBundle or training proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from sidinspector.contracts import canonical_sha256, with_content_sha256
from sidinspector.contracts.json_io import loads_json
from tools.project_sidscope_native_export import project_export, compare_exports, fail


DATASETS = {"rpg": "AmazonReviews2014.Beauty", "psid": "VideoGames.rigor_original_test.selected"}


def validate_observed_inputs(native, selected, observation, inputs, *, native_sha256, preflight_sha256):
    method = observation.get("method")
    if method not in DATASETS or native.get("method", "").lower() != method:
        fail("native_observation_method_mismatch", "method")
    if observation.get("native_sha256") != native_sha256 or observation.get("preflight_sha256") != preflight_sha256:
        fail("native_observation_binding_mismatch", "native/preflight bytes")
    if observation.get("checkpoint_sha256") != native["evidence"]["checkpoint_sha256"]:
        fail("native_observation_binding_mismatch", "checkpoint")
    if observation.get("native_execution") != "cpu_frozen_checkpoint_no_training" or observation.get("environment", {}).get("device") != "cpu":
        fail("native_observation_execution_scope", "CPU inference observation required")
    expected_mapping = [{"item_id": r["normalized_item_id"],
        "sid": r["semantic_codes" if method == "rpg" else "ordered_model_vocabulary_tokens"]}
        for r in native["target_universe"]["rows"]]
    if sorted(inputs["mapping"], key=lambda r: r["item_id"]) != sorted(expected_mapping, key=lambda r: r["item_id"]):
        fail("native_observation_mapping_mismatch", "native universe and preflight mapping")
    rows = observation.get("selection")
    measurements = observation.get("measurements")
    if not isinstance(rows, list) or not isinstance(measurements, list) or len(rows) != len(native["episodes"]) or len(measurements) != len(rows):
        fail("native_observation_population_mismatch", "one measurement per exported episode")
    if [{k: v for k, v in row.items() if k != "split_row_index"} for row in rows] != selected["rows"]:
        fail("native_observation_selection_mismatch", "exact labels and order")
    test_rows = [r for r in inputs["splits"] if r["split"] == "test"]
    if len(inputs["targets"]) != len(rows):
        fail("native_observation_target_mismatch", "exact selected target count")
    targets = {r["episode_id"]: r for r in inputs["targets"]}
    for row, ep, measurement in zip(rows, native["episodes"], measurements):
        index = row.get("split_row_index")
        if type(index) is not int or not 0 <= index < len(test_rows):
            fail("native_observation_split_mismatch", "split row index")
        split = test_rows[index]
        target = targets.get(row["episode_id"], {})
        if row["episode_id"] != ep["trace_id"] or split["episode_id"] != row["episode_id"] or split["target_item_id"] != row["target_normalized_item_id"] or target.get("target_item_id") != row["target_normalized_item_id"] or target.get("split") != "test":
            fail("native_observation_target_mismatch", "episode/split/target join")
        if not isinstance(measurement, dict) or set(measurement) != {"nfe", "forward_calls", "candidate_count", "latency_ms"}:
            fail("invalid_native_measurement", "exact measured fields required")
        if any(type(measurement[k]) is not int or measurement[k] < 1 for k in ("nfe", "forward_calls", "candidate_count")):
            fail("invalid_native_measurement", "positive observed counts required")
        latency = measurement["latency_ms"]
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency <= 0 or measurement["nfe"] != measurement["forward_calls"]:
            fail("invalid_native_measurement", "finite latency and declared NFE definition")
        candidates = sum(p["candidate_count"] for p in ep["propagation"]) if method == "rpg" else sum(len(a["final_beams"]) for a in ep["attempts"])
        if measurement["candidate_count"] != candidates:
            fail("native_candidate_count_mismatch", row["episode_id"])
    return method


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
