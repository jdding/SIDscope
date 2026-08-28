import copy
import json
import math
from pathlib import Path

import pytest

from tests import local_test_bootstrap  # noqa: F401
from tools.rpg_non_ar_bridge import canonical_hash
from tools.verify_rpg_trained_trace_bundle import (
    Failure,
    verify,
    verify_target_rank_claim,
)


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_FIXTURE = ROOT / "examples/rpg_non_ar_bridge_fixture"
CLAIM_FIXTURE = ROOT / "examples/rpg_rank_depth_fixture/target_rank_claims.json"


def read_bridge(name: str) -> dict:
    return json.loads((BRIDGE_FIXTURE / name).read_text(encoding="utf-8"))


def test_rank_claim_fixture_covers_metric_deep_censored_and_resolution_states() -> None:
    fixture = json.loads(CLAIM_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema"] == "sidscope.rpg_rank_depth_claim_fixture.v1"
    observed = {}
    for case in fixture["cases"]:
        if "expected_failure" in case:
            with pytest.raises(Failure, match=case["expected_failure"]):
                verify_target_rank_claim(
                    case["episode"],
                    case["ranked_rows"],
                    published_rank_depth=fixture["published_rank_depth"],
                    trace_id=case["case_id"],
                )
            continue
        rank, state, _ = verify_target_rank_claim(
            case["episode"],
            case["ranked_rows"],
            published_rank_depth=fixture["published_rank_depth"],
            trace_id=case["case_id"],
        )
        observed[case["case_id"]] = (rank, state)
        assert rank == case["expected_rank"]
        assert state == case["expected_state"]

    assert observed["exact_rank_10"][0] == 10
    assert observed["exact_rank_11"][0] == 11
    assert observed["exact_rank_100"][0] == 100
    assert observed["absent_beyond_published_depth"] == (
        None,
        "target_not_in_published_depth",
    )


def test_v2_rank_depth_extension_preserves_legacy_bindings_and_metric_cutoff() -> None:
    prepared = read_bridge("prepared_dataset.json")
    selection = read_bridge("episode_selection.json")
    bundle = read_bridge("trained_trace_v2.json")
    extended = copy.deepcopy(bundle)
    extended["ranking_diagnostic"] = {
        "schema": "sidscope.rpg_rank_depth_diagnostic.v1",
        "evaluation_cutoff": 2,
        "requested_published_rank_depth": 100,
        "published_rank_depth": 2,
        "available_resolved_rank_depth": 2,
        "publication_scope": "complete_resolved_final_frontier",
        "absent_target_rank_state": "target_not_in_published_depth",
        "censoring": "right",
    }
    extended["episodes"][0].update(
        {
            "target_rank_state": "observed_exact",
            "target_rank_lower_bound": None,
        }
    )
    extended["summary"].update(
        {
            "ndcg_at_rank_cutoff": 1.0,
            "exact_target_rank_count": 1,
            "deeper_than_evaluation_cutoff_count": 0,
            "right_censored_target_rank_count": 0,
            "resolution_failure_within_published_depth_count": 0,
        }
    )

    result = verify(extended, prepared, selection)

    assert result["status"] == "pass"
    assert result["hit_at_rank_cutoff"] == bundle["summary"]["hit_at_rank_cutoff"]
    assert result["recall_at_rank_cutoff"] == bundle["summary"]["recall_at_rank_cutoff"]
    assert math.isclose(result["ndcg_at_rank_cutoff"], 1.0)
    assert result["prepared_dataset_contract_sha256"] == canonical_hash(prepared)
    assert result["episode_selection_manifest_sha256"] == canonical_hash(selection)
    handoff = result["downstream_handoff"]["rows"][0]
    assert handoff["published_rank_depth"] == 2
    assert handoff["target_rank_state"] == "observed_exact"
    assert handoff["target_rank_right_censored"] is False


def test_v2_rejects_exact_rank_without_supporting_ordered_row() -> None:
    prepared = read_bridge("prepared_dataset.json")
    selection = read_bridge("episode_selection.json")
    bundle = read_bridge("trained_trace_v2.json")
    bundle["ranking_diagnostic"] = {
        "schema": "sidscope.rpg_rank_depth_diagnostic.v1",
        "evaluation_cutoff": 2,
        "requested_published_rank_depth": 2,
        "published_rank_depth": 2,
        "available_resolved_rank_depth": 2,
        "publication_scope": "complete_resolved_final_frontier",
        "absent_target_rank_state": "target_not_in_published_depth",
        "censoring": "right",
    }
    bundle["episodes"][0].update(
        {
            "target_rank": 2,
            "target_rank_state": "observed_exact",
            "target_rank_lower_bound": None,
        }
    )

    with pytest.raises(Failure, match="unsupported_exact_rank_claim"):
        verify(bundle, prepared, selection)
