import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_d3_catalog_dependence_primary_counts_and_direction() -> None:
    result = json.loads((ROOT / "docs/reproducibility/d3_catalog_dependence_summary.json").read_text())
    assert result["all_artifact_clusters"] == 12
    assert result["tokenizer_export_artifacts"] == 8
    assert result["catalog_clusters"] == 5
    assert result["tokenizer_export_exact"]["rho"] > 0.9
    assert result["tokenizer_export_exact"]["permutations"] == 40320
    assert result["catalog_collapsed_exact"]["rho"] > 0.7
    assert result["catalog_collapsed_exact"]["permutations"] == 120
