from __future__ import annotations

import json
from pathlib import Path

import pytest

from sidinspector.adapters.latte import (
    LatteCacheContractError,
    export_latte_trace,
    latte_vocabulary_tokens,
    normalize_latte_interactions,
    normalize_latte_metadata,
    normalize_latte_sem_ids,
    psid_vocabulary_tokens,
    read_latte_item_mapping,
    read_sem_ids_cache,
)
from sidinspector.preflight import build_metric_smoke_summary


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "examples" / "latte_psid_cache_fixture"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


def _fixture_paths() -> dict[str, Path]:
    return {key: FIXTURE_DIR / value for key, value in MANIFEST["inputs"].items()}


def test_latte_psid_fixture_normalizes_and_runs_metrics() -> None:
    config = MANIFEST["configuration"]
    paths = _fixture_paths()
    sid = normalize_latte_sem_ids(
        paths["sem_ids"],
        paths["item_mapping"],
        method="latte_psid_rqkmeans_fixture",
        dataset=config["dataset"],
        vq_method=config["vq_method"],
        n_codebooks=config["vq_n_codebooks"],
        codebook_size=config["vq_codebook_size"],
    )
    metadata = normalize_latte_metadata(
        paths["item_mapping"],
        dataset=config["dataset"],
        category=config["category"],
        metadata_path=paths["metadata"],
    )
    interactions = normalize_latte_interactions(
        paths["all_item_seqs"], paths["item_mapping"], dataset=config["dataset"]
    )
    assert sid["source_item_id"].tolist() == [
        "fixture-asin-a",
        "fixture-asin-b",
        "fixture-asin-c",
        "fixture-asin-d",
    ]
    assert sid["latte_item_token_id"].tolist() == [1, 2, 3, 4]
    assert sid["item_id"].tolist() == [0, 1, 2, 3]
    assert sid["sid"].tolist() == ["0-1-2", "1-1-2", "2-0-3", "3-2-0"]
    summary = build_metric_smoke_summary(
        sid, metadata, interactions, top_k=2, max_pair_events=100, max_user_items=10
    )
    assert summary[0]["d1_level_count"] == 3
    assert summary[0]["unique_sid"] == 4


def test_model_vocabulary_offsets_match_official_layout() -> None:
    assert psid_vocabulary_tokens((0, 1, 2), 4) == (1, 6, 11)
    assert latte_vocabulary_tokens((0, 1, 2), 4, 3) == (4, 9, 14)


def test_latte_trace_preserves_latent_paths_and_aggregation() -> None:
    config = MANIFEST["configuration"]
    paths = _fixture_paths()
    identities = read_latte_item_mapping(paths["item_mapping"])
    cache = read_sem_ids_cache(
        paths["sem_ids"],
        expected_source_items=(item.source_item_id for item in identities),
        n_codebooks=config["vq_n_codebooks"],
        codebook_size=config["vq_codebook_size"],
    )
    trace = export_latte_trace(
        route_id=MANIFEST["route_id"],
        trace_id="latte-fixture-001",
        split_id=config["split_id"],
        cache=cache,
        normalized_item_ids={item.source_item_id: item.normalized_item_id for item in identities},
        beams=MANIFEST["beams"],
        codebook_size=config["vq_codebook_size"],
        n_latent_tokens=config["n_latent_tokens"],
        aggregation_method=config["aggregation_method"],
    )
    assert trace["decode_state_kind"] == "latent_token_then_ordered_sid_prefix"
    assert [row["source_item_id"] for row in trace["ranked_items"]] == [
        "fixture-asin-a",
        "fixture-asin-b",
    ]
    assert trace["ranked_items"][0]["supporting_beam_count"] == 2
    assert [state["prefix_depth"] for state in trace["beams"][0]["prefix_states"]] == [0, 1, 2, 3]
    assert trace["beams"][0]["prefix_states"][0]["ordered_semantic_prefix"] == []
    assert trace["beams"][0]["prefix_states"][3]["ordered_semantic_prefix"] == [0, 1, 2]
    assert trace["beams"][3]["failure_labels"] == ["invalid_latent_token"]
    assert trace["beams"][4]["failure_labels"] == ["unresolved_semantic_id"]


def test_expected_collision_fixture_fails_with_typed_label(tmp_path: Path) -> None:
    config = MANIFEST["configuration"]
    path = tmp_path / "collision.sem_ids"
    path.write_text(json.dumps(MANIFEST["expected_failure"]["cache"]), encoding="utf-8")
    with pytest.raises(LatteCacheContractError) as raised:
        read_sem_ids_cache(
            path,
            expected_source_items=MANIFEST["expected_failure"]["cache"],
            n_codebooks=config["vq_n_codebooks"],
            codebook_size=config["vq_codebook_size"],
        )
    assert raised.value.label == MANIFEST["expected_failure"]["failure_label"]


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.sem_ids"
    path.write_text('{"fixture-asin-a":[0,1,2],"fixture-asin-a":[1,2,3]}', encoding="utf-8")
    with pytest.raises(LatteCacheContractError) as raised:
        read_sem_ids_cache(
            path,
            expected_source_items=["fixture-asin-a"],
            n_codebooks=3,
            codebook_size=4,
        )
    assert raised.value.label == "duplicate_json_key"


def test_incomplete_cache_cannot_be_admitted(tmp_path: Path) -> None:
    paths = _fixture_paths()
    path = tmp_path / "partial.sem_ids"
    path.write_text('{"fixture-asin-a":[0,1,2]}', encoding="utf-8")
    identities = read_latte_item_mapping(paths["item_mapping"])
    with pytest.raises(LatteCacheContractError) as raised:
        read_sem_ids_cache(
            path,
            expected_source_items=(item.source_item_id for item in identities),
            n_codebooks=3,
            codebook_size=4,
        )
    assert raised.value.label == "cache_catalog_mismatch"
