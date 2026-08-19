import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_g22_paired_bootstrap_preserves_case_and_gate() -> None:
    result = json.loads((ROOT / "docs/reproducibility/g22_handoff_uncertainty.json").read_text())
    assert result["paired_users"] == 5364
    assert result["common_users"] == 4780
    assert result["new_item_users"] == 584
    assert result["bootstrap"]["samples"] == 4999
    assert 0.4 < result["mapping_only_vs_stale"]["probability_mapping_below_stale"] < 0.7
    assert result["probability_all_adapted_seeds_pass"] == 1.0
