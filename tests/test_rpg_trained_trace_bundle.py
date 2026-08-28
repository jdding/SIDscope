import copy
import json
from pathlib import Path

import pytest

from tests import local_test_bootstrap  # noqa: F401
from tools.verify_rpg_trained_trace_bundle import Failure, verify


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = json.loads(
    (
        ROOT
        / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"
    ).read_text(encoding="utf-8")
)


def test_real_trained_rpg_smoke_preserves_parallel_graph_contract() -> None:
    result = verify(BUNDLE)

    assert result["status"] == "pass"
    assert result["episodes"] == 5
    assert result["target_universe_rows"] == 12101
    assert result["published_target_rows"] == 43
    assert result["target_universe_visibility"] == "bounded_rows_full_universe_hash_bound"


@pytest.mark.parametrize("forbidden_key", ["source_item_id", "prefix_depth"])
def test_real_trained_rpg_smoke_rejects_identity_or_prefix_leaks(forbidden_key: str) -> None:
    changed = copy.deepcopy(BUNDLE)
    changed["episodes"][0][forbidden_key] = "forbidden"

    with pytest.raises(Failure, match="identity_or_method_leak"):
        verify(changed)


def test_real_trained_rpg_smoke_rejects_rank_score_tampering() -> None:
    changed = copy.deepcopy(BUNDLE)
    changed["episodes"][0]["ranked_items"][0]["mean_log_probability"] += 0.01

    with pytest.raises(Failure, match="ranked_score_accounting"):
        verify(changed)


def test_real_trained_rpg_smoke_requires_every_resolution_row() -> None:
    changed = copy.deepcopy(BUNDLE)
    ranked = changed["episodes"][0]["ranked_items"][0]
    missing_id = ranked["resolved_normalized_item_ids"][0]
    changed["target_universe"]["rows"] = [
        row
        for row in changed["target_universe"]["rows"]
        if row["normalized_item_id"] != missing_id
    ]

    with pytest.raises(Failure, match="ranked_target_row_missing|ranked_resolution_row_missing"):
        verify(changed)
