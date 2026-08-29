#!/usr/bin/env python3
"""Verify the ISD source audit and bounded decoder-overlay contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.adapters.isd import (  # noqa: E402
    ISDContractError,
    run_deterministic_overlay_fixture,
)


AUDIT = ROOT / "docs/reproducibility/isd_source_audit.json"
FIXTURE = ROOT / "examples/isd_decoder_overlay_fixture/manifest.json"
OFFICIAL_SMOKE = ROOT / "docs/reproducibility/isd_official_source_smoke.json"
STATUS = ROOT / "docs/reproducibility/isd_adapter_status.json"
SNAPSHOT_ID = "ISD-CF7C"
UNIFIED_SHA256 = "c4f7a2593ce819171c368be1af5a5a3e8cfc7821831d6eb0f42f2cc94af66421"
PROVIDER_SHA256 = "055b263e5f7fd9e4b35aea30ec9297b09e36363924f0907bcdf97b6392439586"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _trace_sha256(trace: MappingLike) -> str:
    payload = (json.dumps(trace, indent=2, sort_keys=True) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


MappingLike = dict[str, Any]


def verify() -> dict[str, Any]:
    failures: list[str] = []
    audit = _read_json(AUDIT)
    fixture = _read_json(FIXTURE)
    smoke = _read_json(OFFICIAL_SMOKE)
    status = _read_json(STATUS)

    source = audit.get("source", {})
    if audit.get("schema") != "sidscope.generator_source_audit.v1":
        failures.append("source audit schema mismatch")
    if source.get("snapshot_id") != SNAPSHOT_ID or source.get("revision") is not None:
        failures.append("source audit must retain snapshot-only revision boundary")
    if source.get("license_identifier") != "NOASSERTION":
        failures.append("source audit must retain absent code-license boundary")
    if source.get("license_files_found") != []:
        failures.append("source audit incorrectly claims a root license")
    consistency = audit.get("snapshot_consistency", {})
    if consistency.get("root_readme_title") != "Causal Representation for Recommendation":
        failures.append("source audit lost the root README mismatch")
    assets = audit.get("asset_audit", {})
    for field in (
        "checkpoint_found",
        "semantic_id_cache_found",
        "processed_dataset_found",
        "generated_trace_found",
        "training_log_found",
    ):
        if assets.get(field) is not False:
            failures.append(f"source audit must not claim released {field}")

    fixture_source = fixture.get("source", {})
    if fixture_source.get("snapshot_id") != SNAPSHOT_ID:
        failures.append("fixture is not bound to the audited snapshot ID")
    try:
        trace = run_deterministic_overlay_fixture(fixture)
    except Exception as exc:
        trace = {}
        failures.append(f"positive CPU fixture failed: {type(exc).__name__}: {exc}")
    else:
        if trace.get("decode_state_kind") != "autoregressive_base_beam_with_item_support_overlay":
            failures.append("fixture lost the decoder-overlay state kind")
        survivor_ids = [
            step.get("survivor_ids") for step in trace.get("base_decoder_steps", [])
        ]
        if survivor_ids != [["a1", "b1"], ["a2", "c2"], ["a3", "c3"]]:
            failures.append("fixture prefix-survival export mismatch")
        ranked_ids = [row.get("normalized_item_id") for row in trace.get("ranked_items", [])]
        if ranked_ids != ["1", "3", "5"]:
            failures.append("fixture final ranked-item export mismatch")
        if "2" in ranked_ids:
            failures.append("provider-only item was inserted into final ranking")
        if trace.get("ambiguity", {}).get("catalog_collision_count") != 1:
            failures.append("fixture did not preserve full-SID collision")
        invariants = trace.get("invariants", {})
        if invariants.get("provider_only_items_inserted") is not False:
            failures.append("fixture lost the non-insertion invariant")

    expected = fixture.get("expected_failure", {})
    invalid = copy.deepcopy(fixture)
    invalid["declared_final_item_ids"].append(expected.get("provider_only_item_id"))
    observed_failure = None
    try:
        run_deterministic_overlay_fixture(invalid)
    except ISDContractError as exc:
        observed_failure = exc.label
    if observed_failure != expected.get("failure_label"):
        failures.append(
            "expected-failure mismatch: "
            f"expected={expected.get('failure_label')!r} observed={observed_failure!r}"
        )

    if smoke.get("schema") != "sidscope.isd_official_source_smoke.v1":
        failures.append("official-source smoke schema mismatch")
    if smoke.get("status") != "pass" or smoke.get("source_snapshot_id") != SNAPSHOT_ID:
        failures.append("official-source smoke snapshot/status mismatch")
    if smoke.get("source_revision") is not None:
        failures.append("official-source smoke must not invent a Git revision")
    smoke_hashes = smoke.get("source_sha256", {})
    if smoke_hashes.get("eval_sid_route_unified_tiger_liger_v1.py") != UNIFIED_SHA256:
        failures.append("official unified evaluator hash mismatch")
    if smoke_hashes.get("eval_sid_route_sasrec_isd_v1.py") != PROVIDER_SHA256:
        failures.append("official provider evaluator hash mismatch")
    outputs = smoke.get("outputs", {})
    if outputs.get("selected_prefixes") != [[1], [2]]:
        failures.append("official prefix selection output mismatch")
    if outputs.get("final_ranked_item_indices") != [0, 2, 3]:
        failures.append("official final RRF output mismatch")

    gates = {
        "G0": "partial_content_addressed_anonymous_snapshot_no_immutable_repository_revision",
        "G1": "bounded_fixture_only_official_item_roundtrip_pending",
        "G2": "bounded_overlay_state_and_exact_official_function_smoke_pass",
        "G3": "bounded_support_validity_ambiguity_pruning_and_noninsertion_failure_pass",
        "G4": "bounded_trace_and_ranked_item_export_pass_real_trace_pending",
        "G5": "partial_cpu_fixture_and_official_pure_function_smoke_pass_checkpoint_data_pending",
    }
    input_sha256 = {
        "source_audit": _sha256(AUDIT),
        "fixture_manifest": _sha256(FIXTURE),
        "official_source_smoke": _sha256(OFFICIAL_SMOKE),
    }
    trace_sha256 = _trace_sha256(trace) if trace else None
    if status.get("schema") != "sidscope.isd_adapter_status.v2":
        failures.append("adapter status schema mismatch")
    if status.get("gates") != gates:
        failures.append("adapter status G0-G5 fields differ from executable verifier")
    if status.get("input_sha256") != input_sha256:
        failures.append("adapter status hashes differ from current evidence")
    if status.get("verified_outputs", {}).get("trace_sha256") != trace_sha256:
        failures.append("adapter status trace hash differs from deterministic replay")
    promotion = status.get("promotion", {})
    if promotion.get("named_adapter") is not False or promotion.get("decision") != "close_named_adapter":
        failures.append("adapter promotion boundary mismatch")

    return {
        "schema": "sidscope.isd_adapter_verification.v1",
        "status": "pass" if not failures else "fail",
        "route_id": "isd",
        "source_snapshot_id": SNAPSHOT_ID,
        "source_revision": None,
        "gates": gates,
        "fixture": {
            "trace_schema": trace.get("schema"),
            "trace_sha256": trace_sha256,
            "ranked_item_ids": [
                row.get("normalized_item_id") for row in trace.get("ranked_items", [])
            ],
            "catalog_collision_count": trace.get("ambiguity", {}).get(
                "catalog_collision_count"
            ),
            "expected_failure_label": observed_failure,
        },
        "official_source_smoke": {
            "status": smoke.get("status"),
            "runtime": smoke.get("runtime"),
            "boundary": smoke.get("boundary"),
        },
        "promotion": {
            "named_adapter": False,
            "reason": (
                "The content-addressed anonymous snapshot has no immutable repository revision, "
                "released assets, official-data round-trip, or real model-backed trace. The "
                "license remains a non-redistribution marker rather than a technical gate."
            ),
        },
        "input_sha256": input_sha256,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
