import copy
import json
from pathlib import Path

import pytest

from tests import local_test_bootstrap  # noqa: F401
from tools.rpg_non_ar_bridge import (
    BridgeFailure,
    canonical_hash,
    load_prepared_rows,
    validate_episode_selection,
    validate_prepared_dataset,
)
from tools.verify_rpg_trained_trace_bundle import Failure, verify


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/rpg_non_ar_bridge_fixture"


def read(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


PREPARED = read("prepared_dataset.json")
SELECTION = read("episode_selection.json")
BUNDLE = read("trained_trace_v2.json")


def test_prepared_dataset_hashes_every_runtime_artifact() -> None:
    result = validate_prepared_dataset(PREPARED)
    loaded = load_prepared_rows(PREPARED, FIXTURE)

    assert result["contract_sha256"] == canonical_hash(PREPARED)
    assert len(loaded["mapping"]) == 4
    assert [len(loaded["splits"][name]) for name in ("train", "validation", "test")] == [2, 1, 2]


def test_explicit_selection_and_v2_trace_produce_compact_handoff() -> None:
    selected = validate_episode_selection(SELECTION, PREPARED)
    result = verify(BUNDLE, PREPARED, SELECTION)
    handoff = result["downstream_handoff"]

    assert selected["episode_count"] == 1
    assert result["schema"] == "sidscope.rpg_trained_trace_verification.v2"
    assert result["target_universe_rows"] == 4
    assert handoff["episode_count"] == 1
    assert handoff["evaluator_side_join_fields"] == ["dormant_gap_bucket", "target_label"]
    assert handoff["rows"][0] == {
        "episode_id": "test-b",
        "selection_order": 0,
        "catalog_reachable": True,
        "target_generated": True,
        "target_reached": True,
        "resolution_loss": False,
        "target_rank": 1,
        "hit_at_10": True,
        "ndcg_at_10": 1.0,
        "valid_candidate_count": 3,
        "unique_candidate_count": 3,
        "candidate_duplication_count": 0,
        "visited_item_node_count": 3,
        "parallel_score_count": 8,
        "graph_candidate_score_count": 3,
    }


def test_duplicate_selection_fixture_fails_with_typed_policy() -> None:
    expected_failure = read("expected_failure_duplicate_selection.json")

    with pytest.raises(BridgeFailure, match=expected_failure["expected_failure_label"]):
        validate_episode_selection(expected_failure, PREPARED)


def test_v2_never_falls_back_to_first_n_or_accepts_target_mismatch() -> None:
    with pytest.raises(Failure, match="missing_external_contract"):
        verify(BUNDLE)

    changed = copy.deepcopy(BUNDLE)
    changed["episodes"][0]["target_normalized_item_id"] = 1
    with pytest.raises(Failure, match="episode_target_mismatch"):
        verify(changed, PREPARED, SELECTION)


def test_v2_rejects_autoregressive_or_evaluator_side_generation_fields() -> None:
    prefix = copy.deepcopy(BUNDLE)
    prefix["episodes"][0]["beam_parent"] = 0
    prefix["episodes"][0]["prefix_depth"] = 1
    with pytest.raises(Failure, match="identity_or_method_leak"):
        verify(prefix, PREPARED, SELECTION)

    selection = copy.deepcopy(SELECTION)
    selection["rows"][0]["dormant_gap_bucket"] = "fixture-only"
    with pytest.raises(BridgeFailure, match="evaluator_join_leak"):
        validate_episode_selection(selection, PREPARED)
