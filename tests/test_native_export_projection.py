"""Native file regressions; synthetic PSID labels are NOT real user acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from tools.project_sidscope_native_export import project_export, compare_exports, main

ROOT = Path(__file__).resolve().parents[1]
RPG = ROOT / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"
PSID = ROOT / "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json"


def synthetic_labels():
    native = json.loads(PSID.read_text())
    return {"format": "sidscope.native_selection.v1", "native_sha256": hashlib.sha256(PSID.read_bytes()).hexdigest(),
        "checkpoint_sha256": native["evidence"]["checkpoint_sha256"],
        "split_id": native["evidence"]["split_id"],
        "target_universe_sha256": native["target_universe"]["sha256"],
        # Deliberately synthetic first-slot targets for a known-answer test.
        "rows": [{"episode_id": ep["trace_id"], "target_normalized_item_id": ep["evaluation_slots"][0]["normalized_item_id"],
            "slice": ep["gap_bucket"], "cluster_id": "synthetic-cluster-" + str(i)} for i, ep in enumerate(native["episodes"])]}


def test_real_rpg_projection_and_honest_replay():
    result = project_export(RPG)
    assert result == project_export(RPG)
    assert result["metrics"]["overall"]["hit_at_cutoff"] == .2
    assert result["catalog_scope"] == "bounded_resolution_subset"
    assert result["native_semantics"] == "unordered_token_set_graph_propagation"
    assert "per_episode_compute" in result["unverified"]
    comparison = compare_exports(RPG, RPG)
    assert comparison["comparison_kind"] == "same_export_recomputation"
    assert comparison["overall_delta"] == {"hit_at_cutoff": 0., "ndcg_at_cutoff": 0.}


def test_psid_no_labels_no_fake_metrics_or_comparison():
    result = project_export(PSID)
    assert result["metrics"] is None
    assert result["status"] == "target_labels_unavailable"
    assert all(row["rank_state"] == "unavailable" for row in result["records"])
    native = json.loads(PSID.read_text())
    for projected, ep in zip(result["records"], native["episodes"]):
        assert projected["ranked_items"] == [r["normalized_item_id"] if r["valid"] else None for r in ep["evaluation_slots"]]
    with pytest.raises(ValueError, match="native_target_labels_required"):
        compare_exports(PSID, PSID)


def test_synthetic_identity_bound_labels_and_cli(tmp_path):
    label = tmp_path / "synthetic.json"
    label.write_text(json.dumps(synthetic_labels()))
    result = project_export(PSID, selection=label)
    assert result["metrics"]["overall"]["hit_at_cutoff"] == 1
    assert "label_source_authenticity" in result["unverified"]
    assert main([str(PSID), "--selection", str(label), "--output", str(tmp_path / "out.json")]) == 0
    assert json.loads((tmp_path / "out.json").read_text()) == result
    assert main([str(PSID), "--output", str(tmp_path / "out.json")]) == 2
    before = result["protocol"]
    doc = synthetic_labels()
    doc["rows"].reverse()
    label.write_text(json.dumps(doc))
    assert project_export(PSID, selection=label)["protocol"] == before


@pytest.mark.parametrize("field", ["native_sha256", "checkpoint_sha256", "target_universe_sha256", "split_id"])
def test_binding_tamper(tmp_path, field):
    doc = synthetic_labels()
    doc[field] = "bad"
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="native_selection_binding_mismatch"):
        project_export(PSID, selection=path)


@pytest.mark.parametrize("mutation,code", [
    (lambda d: d["rows"].pop(), "native_selection_population_mismatch"),
    (lambda d: d["rows"].__setitem__(1, copy.deepcopy(d["rows"][0])), "duplicate_native_selection_episode"),
    (lambda d: d["rows"][0].update(target_normalized_item_id=True), "invalid_native_target"),
    (lambda d: d["rows"][0].update(target_normalized_item_id=99999999), "native_target_outside_catalog"),
    (lambda d: d["rows"][0].update(slice="wrong"), "native_slice_mismatch"),
    (lambda d: d["rows"][0].update(cluster_id=0), "invalid_cluster_id"),
])
def test_typed_selection_negatives(tmp_path, mutation, code):
    doc = synthetic_labels()
    mutation(doc)
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match=code):
        project_export(PSID, selection=path)


def test_changed_cluster_population_not_comparable(tmp_path):
    doc = synthetic_labels()
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(doc))
    doc["rows"][0]["cluster_id"] = "different-pairing-unit"
    b.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="native_protocol_mismatch"):
        compare_exports(PSID, PSID, left_selection=a, right_selection=b)


def test_native_rehashed_bad_rank_still_fails(tmp_path):
    doc = json.loads(RPG.read_text())
    doc["episodes"][0]["target_rank"] = 1000
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="native_verification_failed"):
        project_export(path)


def test_packaged_check_needs_no_pytest_runtime():
    assert main(["--check-fixtures"]) == 0
    assert main(["--check-fixtures", str(RPG)]) == 2
    assert main([]) == 2
