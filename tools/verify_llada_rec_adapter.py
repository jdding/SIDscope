#!/usr/bin/env python3
"""Verify the LLaDA-Rec source audit and bounded diffusion contract."""

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

from sidinspector.adapters.llada_rec import (  # noqa: E402
    LLaDARecContractError,
    run_deterministic_diffusion_fixture,
)


AUDIT = ROOT / "docs/reproducibility/llada_rec_source_audit.json"
FIXTURE = ROOT / "examples/llada_rec_diffusion_fixture/manifest.json"
OFFICIAL_SMOKE = ROOT / "docs/reproducibility/llada_rec_official_source_smoke.json"
STATUS = ROOT / "docs/reproducibility/llada_rec_adapter_status.json"
PINNED_REVISION = "83dbcd6061da9266adcd8f68b16d1de7cc2612f3"
PINNED_MODEL_SHA256 = "280b0332e1bef6ee3ae40011a9e481102f158a55e02118a492e8f1087f681133"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict[str, Any]:
    failures: list[str] = []
    audit = _read_json(AUDIT)
    fixture = _read_json(FIXTURE)
    smoke = _read_json(OFFICIAL_SMOKE)
    status = _read_json(STATUS)

    source = audit.get("source", {})
    if audit.get("schema") != "sidscope.generator_source_audit.v1":
        failures.append("source audit schema mismatch")
    if source.get("revision") != PINNED_REVISION:
        failures.append("source audit revision mismatch")
    if source.get("license_status") != "no_license_detected":
        failures.append("source audit must preserve the absent code-license boundary")
    if source.get("license_identifier") != "NOASSERTION":
        failures.append("source audit license identifier must be NOASSERTION")
    if source.get("license_files_found") != [] or source.get("github_api_license") is not None:
        failures.append("source audit incorrectly claims a code license")
    assets = audit.get("asset_audit", {})
    for field in (
        "checkpoint_found",
        "semantic_id_cache_found",
        "processed_dataset_found",
        "training_log_found",
    ):
        if assets.get(field) is not False:
            failures.append(f"source audit must not claim released {field}")
    inference = audit.get("inference_contract", {})
    if inference.get("remasking_observed_in_pinned_source") is not False:
        failures.append("source audit must not claim inference remasking")

    if fixture.get("source", {}).get("revision") != PINNED_REVISION:
        failures.append("fixture is not bound to the pinned source revision")
    try:
        trace = run_deterministic_diffusion_fixture(fixture)
    except Exception as exc:
        trace = {}
        failures.append(f"positive CPU fixture failed: {type(exc).__name__}: {exc}")
    else:
        if trace.get("decode_state_kind") != "masked_parallel_adaptive_unmasking":
            failures.append("fixture lost the method-specific masked state")
        if trace.get("initial_mask_state") != [18, 18, 18, 18]:
            failures.append("fixture initial state is not all-mask")
        if trace.get("generation_policy", {}).get("remasking_supported_by_pinned_source") is not False:
            failures.append("fixture incorrectly enables remasking")
        if trace.get("remasking", {}).get("observed_transition_count") != 0:
            failures.append("fixture contains an undeclared remasking transition")
        if [row.get("normalized_item_id") for row in trace.get("ranked_items", [])] != [
            "1",
            "2",
        ]:
            failures.append("fixture ranked-item export mismatch")
        if trace.get("ambiguity", {}).get("catalog_collision_count") != 1:
            failures.append("fixture did not preserve semantic-ID ambiguity")
        if "prefix_depth" in json.dumps(trace, sort_keys=True):
            failures.append("diffusion fixture must not expose autoregressive prefix depth")

    expected = fixture.get("expected_failure", {})
    invalid = copy.deepcopy(fixture)
    transition = invalid["steps"][int(expected["refinement_step"]) - 1]["transitions"][
        int(expected["transition_index"])
    ]
    transition["remasked_positions"] = expected["remasked_positions"]
    observed_failure = None
    try:
        run_deterministic_diffusion_fixture(invalid)
    except LLaDARecContractError as exc:
        observed_failure = exc.label
    if observed_failure != expected.get("failure_label"):
        failures.append(
            "expected-failure mismatch: "
            f"expected={expected.get('failure_label')!r} observed={observed_failure!r}"
        )

    if smoke.get("schema") != "sidscope.llada_rec_official_source_smoke.v1":
        failures.append("official-source smoke schema mismatch")
    if smoke.get("status") != "pass" or smoke.get("source_revision") != PINNED_REVISION:
        failures.append("official-source smoke revision/status mismatch")
    if smoke.get("source_sha256", {}).get("model") != PINNED_MODEL_SHA256:
        failures.append("official-source model hash mismatch")
    outputs = smoke.get("outputs", {})
    if outputs.get("first_confidence_selected_positions") != [[2], [3]]:
        failures.append("official confidence-selected position output mismatch")
    if outputs.get("filled_position_excluded_next_selection") != [[0]]:
        failures.append("official source did not exclude a filled position")
    semantics = smoke.get("inference_semantics", {})
    if semantics.get("filled_positions_remasked") is not False:
        failures.append("official-source smoke incorrectly claims remasking")

    gates = {
        "G0": "blocked_no_source_license_and_no_released_assets",
        "G1": "bounded_fixture_only_official_data_roundtrip_pending",
        "G2": "bounded_masked_adaptive_unmasking_state_and_official_method_smoke_pass",
        "G3": "bounded_validity_ambiguity_resolution_and_remasking_failure_contract_pass",
        "G4": "bounded_trace_and_ranked_item_export_pass_real_trained_trace_pending",
        "G5": "partial_cpu_fixture_and_official_class_method_smoke_pass_checkpoint_pending",
    }
    input_sha256 = {
        "source_audit": _sha256(AUDIT),
        "fixture_manifest": _sha256(FIXTURE),
        "official_source_smoke": _sha256(OFFICIAL_SMOKE),
    }
    if status.get("schema") != "sidscope.llada_rec_adapter_status.v1":
        failures.append("adapter status schema mismatch")
    if status.get("gates") != gates:
        failures.append("adapter status G0-G5 fields differ from the executable verifier")
    if status.get("input_sha256") != input_sha256:
        failures.append("adapter status hashes differ from current evidence")
    promotion = status.get("promotion", {})
    if promotion.get("named_adapter") is not False or promotion.get("decision") != "close_named_adapter":
        failures.append("adapter promotion boundary mismatch")

    return {
        "schema": "sidscope.llada_rec_adapter_verification.v1",
        "status": "pass" if not failures else "fail",
        "route_id": "llada_rec",
        "source_revision": PINNED_REVISION,
        "gates": gates,
        "fixture": {
            "trace_schema": trace.get("schema"),
            "ranked_item_ids": [
                row.get("normalized_item_id") for row in trace.get("ranked_items", [])
            ],
            "generation_orders": [
                row.get("generation_order") for row in trace.get("ranked_items", [])
            ],
            "catalog_collision_count": trace.get("ambiguity", {}).get(
                "catalog_collision_count"
            ),
            "remasking_transition_count": trace.get("remasking", {}).get(
                "observed_transition_count"
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
            "reason": "The source has no detected code license or released assets, and no real trained trace has passed G1-G5.",
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
