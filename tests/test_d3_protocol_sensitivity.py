import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_d3_protocol_sensitivity_covers_declared_grid() -> None:
    result = json.loads((ROOT / "docs/reproducibility/d3_protocol_sensitivity.json").read_text())
    assert result["routes"] == 8
    assert len(result["configurations"]) == 9
    assert result["primary"] == {"top_k": 5, "max_user_items": 50, "max_pair_events": 10000}
    assert result["minimum_rank_spearman_vs_primary"] >= 0.8
