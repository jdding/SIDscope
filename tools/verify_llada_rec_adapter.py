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
TOKENIZER_SMOKE = ROOT / "docs/reproducibility/llada_rec_vg_tokenizer_smoke.json"
FORMAL_TOKENIZER = ROOT / "docs/reproducibility/llada_rec_vg_tokenizer_formal_evidence.json"
TRAINED_EVIDENCE = ROOT / "docs/reproducibility/llada_rec_vg_trained_trace_evidence.json"
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
    tokenizer_smoke = _read_json(TOKENIZER_SMOKE)
    formal_tokenizer = _read_json(FORMAL_TOKENIZER)
    trained_evidence = _read_json(TRAINED_EVIDENCE)
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

    if tokenizer_smoke.get("schema") != "sidscope.llada_rec_project_tokenizer_smoke.v1":
        failures.append("project tokenizer smoke schema mismatch")
    if tokenizer_smoke.get("status") != "pass":
        failures.append("project tokenizer smoke status mismatch")
    if tokenizer_smoke.get("source_revision") != PINNED_REVISION:
        failures.append("project tokenizer smoke revision mismatch")
    if tokenizer_smoke.get("scope") != (
        "two_epoch_engineering_smoke_not_formal_tokenizer_or_generator_evidence"
    ):
        failures.append("project tokenizer smoke promotion boundary mismatch")
    tokenizer_config = tokenizer_smoke.get("configuration", {})
    if tokenizer_config.get("catalog_rows") != 17396:
        failures.append("project tokenizer smoke catalog-row mismatch")
    if tokenizer_config.get("semantic_positions") != 4:
        failures.append("project tokenizer smoke semantic-position mismatch")
    if tokenizer_config.get("codebook_size_per_position") != 256:
        failures.append("project tokenizer smoke codebook-size mismatch")
    tokenizer_outputs = tokenizer_smoke.get("outputs", {})
    if tokenizer_outputs.get("completed_epochs") != 2:
        failures.append("project tokenizer smoke epoch-count mismatch")
    if tokenizer_outputs.get("checkpoint_reloaded_strict") is not True:
        failures.append("project tokenizer smoke did not strictly reload checkpoint")
    if tokenizer_outputs.get("unique_semantic_ids") != 17345:
        failures.append("project tokenizer smoke unique-SID count mismatch")
    if tokenizer_outputs.get("collision_excess") != 51:
        failures.append("project tokenizer smoke collision count mismatch")
    privacy = tokenizer_smoke.get("privacy", {})
    if any(
        privacy.get(field) is not False
        for field in (
            "contains_source_item_ids",
            "contains_embeddings",
            "contains_checkpoint",
            "contains_private_paths",
        )
    ):
        failures.append("project tokenizer smoke violates compact-evidence privacy boundary")

    if (
        formal_tokenizer.get("schema")
        != "sidscope.llada_rec_project_tokenizer_evidence.v1"
        or formal_tokenizer.get("status") != "pass"
        or formal_tokenizer.get("source_revision") != PINNED_REVISION
        or formal_tokenizer.get("configuration", {}).get("target_epochs") != 10000
        or formal_tokenizer.get("outputs", {}).get("unique_semantic_ids_after_collision_resolution") != 17344
        or formal_tokenizer.get("recoverability", {}).get("resumed") is not True
        or formal_tokenizer.get("recoverability", {}).get("checkpoint_reloaded_strict") is not True
    ):
        failures.append("formal tokenizer evidence boundary mismatch")

    diagnostic = trained_evidence.get("balanced_diagnostic", {})
    checkpoint_smoke = trained_evidence.get("checkpoint_smoke", {})
    training = trained_evidence.get("training", {})
    verification = trained_evidence.get("verification", {})
    if (
        trained_evidence.get("schema")
        != "sidscope.llada_rec_vg_trained_trace_evidence.v1"
        or trained_evidence.get("status") != "pass"
        or trained_evidence.get("source_revision") != PINNED_REVISION
        or training.get("completed_steps") != 10000
        or training.get("resumed") is not True
        or training.get("checkpoint_reloaded_strict") is not True
        or checkpoint_smoke.get("episodes") != 5
        or checkpoint_smoke.get("verification_status") != "pass"
        or checkpoint_smoke.get("expected_failure_label") != "unknown_parent_beam"
        or checkpoint_smoke.get("typed_negative_status") != "pass"
        or diagnostic.get("episodes") != 250
        or diagnostic.get("five_bucket_counts") != {
            "short": 50, "30-90d": 50, "90-180d": 50,
            "180-365d": 50, ">365d": 50,
        }
        or diagnostic.get("verification_status") != "pass"
        or verification.get("trace_exporter_sha256")
        != _sha256(ROOT / "tools/export_llada_rec_trained_trace.py")
        or verification.get("real_bundle_verifier_sha256")
        != _sha256(ROOT / "tools/verify_llada_rec_trained_trace_bundle.py")
    ):
        failures.append("formal trained trace evidence boundary mismatch")

    gates = {
        "G0": "pass_source_revision_method_identity_license_noassertion_marker_nonredistribution",
        "G1": "pass_formal_vg_tokenizer_item_sid_position_vocabulary_roundtrip_and_explicit_selection",
        "G2": "pass_checkpoint_bound_native_four_action_adaptive_unmasking_and_beam_ancestry",
        "G3": "pass_raw_tuple_validity_collision_preserving_resolution_and_typed_failure",
        "G4": "pass_five_episode_and_external_250_episode_dense_rank_censoring_and_per_bucket_handoff",
        "G5": "pass_recoverable_10000_step_training_strict_checkpoint_reload_smoke_diagnostic_and_verifiers",
    }
    input_sha256 = {
        "source_audit": _sha256(AUDIT),
        "fixture_manifest": _sha256(FIXTURE),
        "official_source_smoke": _sha256(OFFICIAL_SMOKE),
        "project_tokenizer_smoke": _sha256(TOKENIZER_SMOKE),
        "formal_tokenizer_evidence": _sha256(FORMAL_TOKENIZER),
        "trained_trace_evidence": _sha256(TRAINED_EVIDENCE),
    }
    if status.get("schema") != "sidscope.llada_rec_adapter_status.v4":
        failures.append("adapter status schema mismatch")
    if status.get("gates") != gates:
        failures.append("adapter status G0-G5 fields differ from the executable verifier")
    if status.get("input_sha256") != input_sha256:
        failures.append("adapter status hashes differ from current evidence")
    promotion = status.get("promotion", {})
    if (
        promotion.get("named_adapter") is not True
        or promotion.get("decision") != "named_adapter"
        or promotion.get("execution_authorized") is not True
        or promotion.get("redistribution_authorized") is not False
    ):
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
        "project_tokenizer_smoke": {
            "status": tokenizer_smoke.get("status"),
            "scope": tokenizer_smoke.get("scope"),
            "catalog_rows": tokenizer_config.get("catalog_rows"),
            "unique_semantic_ids": tokenizer_outputs.get("unique_semantic_ids"),
            "collision_excess": tokenizer_outputs.get("collision_excess"),
            "checkpoint_reloaded_strict": tokenizer_outputs.get(
                "checkpoint_reloaded_strict"
            ),
        },
        "formal_tokenizer": {
            "status": formal_tokenizer.get("status"),
            "completed_epochs": formal_tokenizer.get("configuration", {}).get("target_epochs"),
            "unique_semantic_ids": formal_tokenizer.get("outputs", {}).get(
                "unique_semantic_ids_after_collision_resolution"
            ),
        },
        "trained_trace": {
            "status": trained_evidence.get("status"),
            "completed_steps": training.get("completed_steps"),
            "checkpoint_smoke_episodes": checkpoint_smoke.get("episodes"),
            "balanced_diagnostic_episodes": diagnostic.get("episodes"),
            "hit_at_10": diagnostic.get("metrics", {}).get("hit_at_10"),
            "ndcg_at_10": diagnostic.get("metrics", {}).get("ndcg_at_10"),
        },
        "promotion": {
            "named_adapter": True,
            "redistribution_authorized": False,
            "reason": "The configuration-bound frozen VG tokenizer, recoverable 10000-step generator, native five-episode smoke, external 250 diagnostic, typed failure, and verifiers pass G0-G5; the license remains a non-redistribution marker.",
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
