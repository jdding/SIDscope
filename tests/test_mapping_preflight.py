from copy import deepcopy
import json
from pathlib import Path
import pytest
from sidscope.mapping_check import preflight, main
from sidscope.workflows import WorkflowError, audit


def inputs():
    return dict(dataset="test", mapping=[{"item_id": i, "sid": [i // 2, i % 2]} for i in range(4)],
        catalog=[{"item_id": i, "category": "a" if i < 2 else "b"} for i in range(4)],
        splits=[{"episode_id": "e", "split": "test", "target_item_id": 3, "history_item_ids": [0, 1]}],
        targets=[{"episode_id": "e", "split": "test", "target_item_id": 3, "sid": [1, 1]}],
        interactions=[{"normalized_user_id": 0, "item_id": i, "split": "train"} for i in [0, 1, 1, 2]])


def test_complete_preflight_cli_api_and_determinism(tmp_path):
    spec = inputs()
    before = deepcopy(spec)
    report = preflight(**spec)
    assert spec == before
    assert len(report["checks"]) == 5
    assert set(report["metrics"]) == {"D1_utilization", "D2_aliasing", "D3_alignment", "D4_popularity", "D5_structure"}
    assert report["metrics"]["D1_utilization"] == audit(spec["mapping"])["metrics"]["D1_utilization"]
    source, output = tmp_path / "spec.json", tmp_path / "result.json"
    source.write_text(json.dumps(spec))
    assert main(["--input", str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == report
    for key in ("mapping", "catalog", "splits", "targets", "interactions"):
        spec[key].reverse()
    assert preflight(**spec) == report
    assert main(["--input", str(source), "--output", str(output)]) == 2


@pytest.mark.parametrize("mutation,code", [
    (lambda x: x["catalog"].append(x["catalog"][0]), "duplicate_catalog_item"),
    (lambda x: x["catalog"].pop(), "catalog_mapping_mismatch"),
    (lambda x: x["mapping"].pop(), "catalog_mapping_mismatch"),
    (lambda x: x["splits"].append(x["splits"][0]), "duplicate_split_episode"),
    (lambda x: x["splits"][0]["history_item_ids"].append(99), "item_without_mapping"),
    (lambda x: x["targets"][0].update(episode_id="absent"), "target_episode_out_of_split"),
    (lambda x: x["targets"][0].update(split="valid"), "target_split_mismatch"),
    (lambda x: x["targets"][0].update(target_item_id=2, sid=[1, 0]), "target_item_mismatch"),
    (lambda x: x["targets"][0].update(sid=[0, 0]), "target_sid_mismatch"),
    (lambda x: x["targets"][0].update(sid=[True, 1]), "target_sid_mismatch"),
    (lambda x: x["targets"].append(x["targets"][0]), "duplicate_target_episode"),
    (lambda x: x["interactions"][0].update(item_id=99), "item_without_mapping"),
    (lambda x: x["interactions"][0].update(split="trian"), "invalid_split"),
])
def test_typed_join_negatives_publish_nothing(tmp_path, mutation, code):
    spec = inputs()
    mutation(spec)
    with pytest.raises(WorkflowError, match=code):
        preflight(**spec)
    source, output = tmp_path / "bad.json", tmp_path / "absent.json"
    source.write_text(json.dumps(spec))
    assert main(["--input", str(source), "--output", str(output)]) == 2
    assert not output.exists()


def test_heldout_never_falls_back_to_training():
    spec = inputs()
    expected = preflight(**spec)["metrics"]
    spec["interactions"] += [{"normalized_user_id": 99, "item_id": 3, "split": "test"}] * 100
    assert preflight(**spec)["metrics"] == expected
    for row in spec["interactions"]:
        row["split"] = "test"
    report = preflight(**spec)
    assert "D4_popularity" not in report["metrics"]
    assert all(row["mean_collab_prefix_recall"] is None for row in report["metrics"]["D3_alignment"])
    assert any("no explicit training" in reason for reason in report["unavailable"])


def test_omitted_inputs_are_not_invented():
    report = preflight(inputs()["mapping"], dataset="test")
    assert report["checks"] == {}
    assert "D3_alignment" not in report["metrics"]
    assert "D4_popularity" not in report["metrics"]
    assert any("catalog not supplied" in s for s in report["unavailable"])


def test_real_bounded_rpg_mapping_is_not_a_full_catalog():
    root = Path(__file__).resolve().parents[1]
    native = json.loads((root / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json").read_text())
    mapping = [{"item_id": r["normalized_item_id"], "sid": r["semantic_codes"]} for r in native["target_universe"]["rows"]]
    report = preflight(mapping, dataset="RPG-Beauty-public-bounded")
    assert report["metrics"]["D1_utilization"][0]["items"] == 43
    assert len(mapping) < native["target_universe"]["row_count"]
    assert "catalog_mapping" not in report["checks"]
    # This real bounded export omits target/history mappings. Never fill them in
    # to make a full-dataset preflight appear successful.
    ep = next(ep for ep in native["episodes"] if ep["target_normalized_item_id"] not in {r["item_id"] for r in mapping})
    with pytest.raises(WorkflowError, match="item_without_mapping"):
        preflight(mapping, dataset="RPG-Beauty-public-bounded", splits=[{
            "episode_id": ep["trace_id"], "split": "test",
            "target_item_id": ep["target_normalized_item_id"],
            "history_item_ids": ep["context_normalized_item_ids"]}])


def test_local_caller_budget_and_invalid_cli_policy(tmp_path):
    from sidscope.workflows import LocalInputBudget
    spec = inputs()
    with pytest.raises(WorkflowError, match="workflow_row_budget"):
        preflight(**spec, budget=LocalInputBudget(max_rows=3))
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    assert main(["--input", str(path), "--output", str(tmp_path / "absent"), "--max-input-bytes", "10"]) == 2
    assert not (tmp_path / "absent").exists()
