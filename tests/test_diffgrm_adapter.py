from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.diffgrm import (
    DiffGRMContractError,
    canonical_sha256,
    model_vocabulary_tokens,
    validate_episode_selection,
    validate_prepared_dataset,
    validate_sid_compatibility,
    validate_trace_bundle,
)
from tools.preflight_diffgrm_adapter import inspect_source
from tools.verify_diffgrm_adapter import verify


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/diffgrm_masked_diffusion_fixture"


def read_fixture(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_official_position_disjoint_tokens() -> None:
    assert model_vocabulary_tokens([1, 2, 3, 4]) == (4, 261, 518, 775)


def test_rpg_opq32_identity_is_rejected_without_crop() -> None:
    with pytest.raises(DiffGRMContractError) as raised:
        validate_sid_compatibility(
            n_digit=32,
            codebook_size=256,
            pad_token=0,
            bos_token=1,
            eos_token=2,
            mask_token=-1,
            sid_offset=3,
        )
    assert raised.value.label == "incompatible_sid_contract"


def test_prepared_and_selection_are_dataset_neutral_and_hash_bound() -> None:
    prepared = read_fixture("prepared_dataset.json")
    selection = read_fixture("episode_selection.json")
    prepared_result = validate_prepared_dataset(prepared)
    selection_result = validate_episode_selection(selection, prepared)
    assert prepared_result["catalog_collision_count"] == 1
    assert selection_result["episode_count"] == 1
    assert selection["prepared_dataset_contract_sha256"] == canonical_sha256(prepared)
    assert selection["first_n_fallback_allowed"] is False


def test_native_masked_trace_preserves_noising_ancestry_and_resolution() -> None:
    result = validate_trace_bundle(
        read_fixture("trained_trace_fixture.json"),
        read_fixture("prepared_dataset.json"),
        read_fixture("episode_selection.json"),
    )
    assert result["status"] == "pass"
    assert result["projection_semantics"] == "projection_not_applicable"
    assert result["hit_at_10"] == 1.0
    assert result["ndcg_at_10"] == 1.0


def test_invalid_raw_tuple_cannot_be_promoted_by_resolution() -> None:
    prepared = read_fixture("prepared_dataset.json")
    selection = read_fixture("episode_selection.json")
    trace = read_fixture("trained_trace_fixture.json")
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
    with pytest.raises(DiffGRMContractError) as raised:
        validate_trace_bundle(trace, prepared, selection)
    assert raised.value.label == "invalid_raw_marked_success"


def test_exact_rank_without_published_row_is_rejected() -> None:
    prepared = read_fixture("prepared_dataset.json")
    selection = read_fixture("episode_selection.json")
    trace = read_fixture("trained_trace_fixture.json")
    episode = trace["episodes"][0]
    episode["ranked_items"] = [
        {"rank": 1, "normalized_item_id": "n2", "score": -0.9}
    ]
    episode["target_rank"] = 2
    with pytest.raises(DiffGRMContractError) as raised:
        validate_trace_bundle(trace, prepared, selection)
    assert raised.value.label == "unsupported_exact_rank_claim"


def test_duplicate_episode_selection_is_typed() -> None:
    prepared = read_fixture("prepared_dataset.json")
    selection = read_fixture("episode_selection.json")
    selection["episodes"].append(copy.deepcopy(selection["episodes"][0]))
    selection["episodes"][1]["selection_ordinal"] = 2
    with pytest.raises(DiffGRMContractError) as raised:
        validate_episode_selection(selection, prepared)
    assert raised.value.label == "duplicate_episode_selection"


def test_staged_preflight_does_not_execute_source_and_keeps_license_as_marker() -> None:
    result = inspect_source()
    assert result["status"] == "pass"
    assert result["source_code_imported"] is False
    assert result["source_code_executed"] is False
    assert result["execution_authorized"] is True
    assert result["redistribution_authorized"] is False


def test_full_adapter_verifier_passes_and_keeps_promotion_evidence_bound() -> None:
    result = verify()
    assert result["status"] == "pass"
    assert result["promotion"]["named_adapter"] is False
    assert result["promotion"]["execution_authorized"] is True
    assert result["upstream_source_executed"] is False
    assert result["gpu_used"] is False
    assert set(result["expected_failures"].values()) == {
        "incompatible_sid_contract",
        "duplicate_episode_selection",
        "missing_selected_episode",
        "selected_episode_out_of_split",
        "selection_target_mismatch",
        "selection_target_outside_catalog",
        "autoregressive_field_forbidden",
        "unknown_parent_beam",
        "invalid_raw_marked_success",
        "unsupported_exact_rank_claim",
    }
