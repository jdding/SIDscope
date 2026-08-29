#!/usr/bin/env python3
"""Verify the staged DiffGRM contracts without executing upstream code."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.adapters.diffgrm import (  # noqa: E402
    DiffGRMContractError,
    canonical_sha256,
    validate_prepared_dataset,
    validate_trace_bundle,
)
from tools.preflight_diffgrm_adapter import inspect_source  # noqa: E402


FIXTURE = ROOT / "examples/diffgrm_masked_diffusion_fixture"
SOURCE_AUDIT = ROOT / "docs/reproducibility/diffgrm_www2026_source_audit.json"
STAGED_PREFLIGHT = ROOT / "docs/reproducibility/diffgrm_www2026_staged_preflight.json"
STATUS = ROOT / "docs/reproducibility/diffgrm_www2026_adapter_status.json"
TRAINED_EVIDENCE = ROOT / "docs/reproducibility/diffgrm_www2026_trained_trace_evidence.json"
STEAM_TRAINED_EVIDENCE = ROOT / "docs/reproducibility/diffgrm_steam_trained_trace_evidence.json"
REAL_BUNDLE_VERIFIER = ROOT / "tools/verify_diffgrm_trained_trace_bundle.py"
ADAPTER_CORE = ROOT / "src/sidinspector/adapters/diffgrm.py"
PINNED_REVISION = "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c"
GATES = {
    "G0": "pass_publication_revision_source_identity_license_noassertion_marker_nonredistribution",
    "G1": "pass_real_vg_and_steam_opq4_item_sid_vocabulary_roundtrip_and_explicit_five_bucket_selection",
    "G2": "pass_real_checkpoint_bound_native_noising_adaptive_denoising_and_beam_ancestry",
    "G3": "pass_real_raw_validity_duplicate_collision_resolution_and_typed_failure",
    "G4": "pass_real_vg_and_steam_five_episode_and_external_250_episode_ranked_item_and_censoring_exports",
    "G5": "pass_vg_and_steam_recoverable_training_checkpoint_smoke_typed_failure_external_diagnostic_and_verifiers",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mutate(
    mutation: str,
    prepared: dict[str, Any],
    selection: dict[str, Any],
    trace: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    prepared = copy.deepcopy(prepared)
    selection = copy.deepcopy(selection)
    trace = copy.deepcopy(trace)
    target = "trace"
    if mutation == "sid_n_digit_32":
        prepared["sid_contract"]["n_digit"] = 32
        target = "prepared"
    elif mutation == "duplicate_selection":
        duplicate = copy.deepcopy(selection["episodes"][0])
        duplicate["selection_ordinal"] = 2
        selection["episodes"].append(duplicate)
        target = "selection"
    elif mutation == "missing_selected_episode":
        selection["episodes"][0]["episode_id"] = "missing-episode"
        target = "selection"
    elif mutation == "selection_out_of_split":
        prepared["episode_index"][0]["split"] = "validation"
        selection["episodes"][0]["split"] = "validation"
        selection["prepared_dataset_contract_sha256"] = canonical_sha256(prepared)
        target = "selection"
    elif mutation == "selection_target_mismatch":
        selection["episodes"][0]["target_normalized_item_id"] = "n2"
        target = "selection"
    elif mutation == "selection_catalog_unreachable":
        prepared["episode_index"][0]["catalog_reachable"] = False
        selection["prepared_dataset_contract_sha256"] = canonical_sha256(prepared)
        target = "selection"
    elif mutation == "add_prefix_depth":
        trace["episodes"][0]["prefix_depth"] = 1
    elif mutation == "replace_step2_parent":
        trace["episodes"][0]["attempts"][0]["steps"][1]["expanded_candidates"][0][
            "parent_beam_id"
        ] = "missing-parent"
    elif mutation == "invalid_raw_marked_success":
        final = trace["episodes"][0]["attempts"][0]["steps"][3]["expanded_candidates"][0]
        final["selected_codebook_token_id"] = 55
        final["post_codes"] = [1, 55, 3, 4]
        final["per_position_topk"][0]["candidates"][0]["codebook_token_id"] = 55
        raw = trace["episodes"][0]["attempts"][0]["raw_final_beams"][0]
        raw.update(
            {
                "semantic_codes": [1, 55, 3, 4],
                "raw_validity": "invalid_raw_tuple",
                "resolved_normalized_item_ids": [],
                "resolution_state": "unresolved",
                "raw_generation_success": True,
            }
        )
    elif mutation == "unsupported_exact_rank":
        episode = trace["episodes"][0]
        episode["ranked_items"] = [
            {"rank": 1, "normalized_item_id": "n2", "score": -0.9}
        ]
        episode["target_rank"] = 2
        episode["target_rank_state"] = "observed_exact"
    else:
        raise ValueError(f"unknown mutation {mutation!r}")
    return target, prepared, selection, trace


def verify() -> dict[str, Any]:
    failures: list[str] = []
    source_audit = _read(SOURCE_AUDIT)
    staged = _read(STAGED_PREFLIGHT)
    status = _read(STATUS)
    trained_evidence = _read(TRAINED_EVIDENCE)
    steam_evidence = _read(STEAM_TRAINED_EVIDENCE)
    prepared = _read(FIXTURE / "prepared_dataset.json")
    selection = _read(FIXTURE / "episode_selection.json")
    trace = _read(FIXTURE / "trained_trace_fixture.json")
    expected_failures = _read(FIXTURE / "expected_failures.json")

    source = source_audit.get("source", {})
    promotion = source_audit.get("promotion_boundary", {})
    if source.get("revision") != PINNED_REVISION:
        failures.append("source revision mismatch")
    if source.get("license_identifier") != "NOASSERTION" or source.get(
        "license_files_found"
    ) != []:
        failures.append("source audit must preserve the no-license boundary")
    if promotion.get("named_adapter") is not False:
        failures.append("source audit prematurely promotes a named adapter")
    if promotion.get("upstream_execution_allowed") is not True:
        failures.append("source audit must keep the license marker separate from execution")
    if promotion.get("redistribution_allowed") is not False:
        failures.append("source audit must retain the non-redistribution boundary")

    replayed_preflight = inspect_source()
    if staged != replayed_preflight:
        failures.append("staged preflight is not reproducible from the pinned audit")
    if staged.get("execution_authorized") is not True or staged.get(
        "source_code_executed"
    ) is not False:
        failures.append("staged preflight identity must pass without executing source")
    if staged.get("redistribution_authorized") is not False:
        failures.append("staged preflight must not authorize redistribution")

    try:
        positive = validate_trace_bundle(trace, prepared, selection)
    except Exception as exc:
        positive = {}
        failures.append(f"positive fixture failed: {type(exc).__name__}: {exc}")

    observed_failures: dict[str, str | None] = {}
    for case in expected_failures.get("cases", []):
        target, invalid_prepared, invalid_selection, invalid_trace = _mutate(
            str(case["mutation"]), prepared, selection, trace
        )
        observed = None
        try:
            if target == "prepared":
                validate_prepared_dataset(invalid_prepared)
            elif target == "selection":
                from sidinspector.adapters.diffgrm import validate_episode_selection

                validate_episode_selection(invalid_selection, invalid_prepared)
            else:
                validate_trace_bundle(invalid_trace, invalid_prepared, invalid_selection)
        except DiffGRMContractError as exc:
            observed = exc.label
        observed_failures[str(case["case_id"])] = observed
        if observed != case.get("expected_failure_label"):
            failures.append(
                f"expected failure mismatch for {case.get('case_id')}: "
                f"expected={case.get('expected_failure_label')!r} observed={observed!r}"
            )

    evidence_paths = {
        "source_audit": SOURCE_AUDIT,
        "staged_preflight": STAGED_PREFLIGHT,
        "prepared_dataset": FIXTURE / "prepared_dataset.json",
        "episode_selection": FIXTURE / "episode_selection.json",
        "trace_fixture": FIXTURE / "trained_trace_fixture.json",
        "expected_failures": FIXTURE / "expected_failures.json",
    }
    input_sha256 = {name: _sha256(path) for name, path in evidence_paths.items()}
    input_sha256["trained_trace_evidence"] = _sha256(TRAINED_EVIDENCE)
    input_sha256["steam_trained_trace_evidence"] = _sha256(STEAM_TRAINED_EVIDENCE)
    if status.get("schema") != "sidscope.diffgrm_adapter_status.v4":
        failures.append("adapter status schema mismatch")
    if status.get("gates") != GATES:
        failures.append("adapter status gates differ from executable verifier")
    if status.get("input_sha256") != input_sha256:
        failures.append("adapter status hashes differ from current evidence")
    status_promotion = status.get("promotion", {})
    if (
        status_promotion.get("named_adapter") is not True
        or status_promotion.get("decision") != "named_adapter"
        or status_promotion.get("execution_authorized") is not True
        or status_promotion.get("redistribution_authorized") is not False
    ):
        failures.append("adapter promotion boundary mismatch")

    if trained_evidence.get("schema") != "sidscope.diffgrm_trained_trace_evidence.v1":
        failures.append("trained trace evidence schema mismatch")
    if trained_evidence.get("status") != "pass":
        failures.append("trained trace evidence status mismatch")
    if trained_evidence.get("source", {}).get("revision") != PINNED_REVISION:
        failures.append("trained trace source revision mismatch")
    diagnostic = trained_evidence.get("external_balanced_diagnostic", {})
    if diagnostic.get("episodes") != 250 or diagnostic.get("five_bucket_counts") != {
        "short": 50,
        "30-90d": 50,
        "90-180d": 50,
        "180-365d": 50,
        ">365d": 50,
    }:
        failures.append("trained diagnostic episode boundary mismatch")
    if diagnostic.get("verification_status") != "pass":
        failures.append("trained diagnostic verification status mismatch")
    smoke = trained_evidence.get("external_checkpoint_smoke", {})
    if (
        smoke.get("episodes") != 5
        or smoke.get("expected_failure_label") != "unknown_parent_beam"
        or smoke.get("positive_verification_status") != "pass"
        or smoke.get("negative_verification_status")
        != "typed_unknown_parent_beam_rejected"
    ):
        failures.append("trained checkpoint smoke boundary mismatch")
    verification = trained_evidence.get("verification", {})
    if verification.get("adapter_core_sha256") != _sha256(ADAPTER_CORE):
        failures.append("trained evidence adapter core hash mismatch")
    if verification.get("real_bundle_verifier_sha256") != _sha256(
        REAL_BUNDLE_VERIFIER
    ):
        failures.append("trained evidence real-bundle verifier hash mismatch")
    steam_diagnostic = steam_evidence.get("balanced_diagnostic", {})
    if (
        steam_evidence.get("status") != "pass"
        or steam_evidence.get("source_revision") != PINNED_REVISION
        or steam_diagnostic.get("episodes") != 250
        or steam_diagnostic.get("five_bucket_counts") != {
            "short": 50, "30-90d": 50, "90-180d": 50,
            "180-365d": 50, ">365d": 50,
        }
        or steam_diagnostic.get("official_top10_equivalence") is not True
    ):
        failures.append("Steam trained diagnostic evidence boundary mismatch")

    return {
        "schema": "sidscope.diffgrm_adapter_verification.v1",
        "status": "pass" if not failures else "fail",
        "route_id": "diffgrm_www2026",
        "source_revision": PINNED_REVISION,
        "venue": "The Web Conference 2026 research track",
        "gates": GATES,
        "positive_fixture": positive,
        "expected_failures": observed_failures,
        "upstream_source_executed": False,
        "gpu_used": False,
        "promotion": {
            "named_adapter": True,
            "execution_authorized": True,
            "redistribution_authorized": False,
            "reason": "The configuration-bound VG and Steam checkpoint smokes and external 250-episode native v2 diagnostics pass; the license remains a non-redistribution marker.",
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
