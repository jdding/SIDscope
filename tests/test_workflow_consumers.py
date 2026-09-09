"""External-style consumers import only the documented public workflow module."""
import json
import inspect
import pytest
from sidscope.workflows import audit, evaluate, compare, WorkflowError, main
from sidscope import with_content_sha256


def inputs():
    return [{"episode_id": "a", "ranked_items": [None, 2]}, {"episode_id": "b", "ranked_items": [1, 3]}], [{"episode_id": "a", "target_item_id": 2, "slice": "cold"}, {"episode_id": "b", "target_item_id": 3, "slice": "warm"}]


def test_mapping_and_checkpoint_journey(tmp_path, capsys):
    mapping = [{"item_id": 1, "sid": [0, 1]}, {"item_id": 2, "sid": [0, 1]}, {"item_id": 3, "sid": [1, 0]}]
    report = audit(mapping)
    assert report["metrics"]["D2_aliasing"][0]["full_collision_rate"] == 2 / 3
    assert report["findings"][0]["normalized_items"] == [1, 2]
    path, output = tmp_path / "mapping.json", tmp_path / "report.json"
    path.write_text(json.dumps(mapping))
    assert main(["audit", "--input", str(path), "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == report
    assert main(["audit", "--input", str(path), "--output", str(output)]) == 2
    predictions, targets = inputs()
    left = evaluate(predictions, targets, dataset="toy", cutoff=2)
    assert left["records"][0]["rank"] == 2  # invalid slot must not be backfilled
    assert left["metrics"]["overall"]["success"] == 2
    predictions[0]["ranked_items"] = [None, 1]
    right = evaluate(predictions, targets, dataset="toy", cutoff=2)
    diff = compare(left, right)
    assert diff["status"] == "qualified"
    assert "matched experimental controls" in diff["unavailable"]
    assert diff["overall_delta"]["hit_at_cutoff"] == -0.5
    assert diff["regressed_episodes"] == ["a"]
    assert diff["slice_deltas"]["cold"]["hit_at_cutoff"] == -1


def test_comparison_rejects_forged_report_and_other_cohort():
    predictions, targets = inputs()
    left = evaluate(predictions, targets, dataset="toy", cutoff=2)
    right = json.loads(json.dumps(left))
    right["metrics"]["overall"]["hit_at_cutoff"] = 0.3
    with pytest.raises(WorkflowError) as caught:
        compare(left, with_content_sha256(right))
    assert caught.value.code == "workflow_report_recomputation_mismatch"
    targets[0]["slice"] = "different"
    with pytest.raises(WorkflowError) as caught:
        compare(left, evaluate(predictions, targets, dataset="toy", cutoff=2))
    assert caught.value.code == "evaluation_protocol_mismatch"


@pytest.mark.parametrize("change,code", [("short", "insufficient_publication_depth"), ("duplicate", "duplicate_ranked_item"), ("missing", "evaluation_population_mismatch")])
def test_checkpoint_input_failures(change, code):
    predictions, targets = inputs()
    if change == "short":
        predictions[0]["ranked_items"] = [2]
    elif change == "duplicate":
        predictions[0]["ranked_items"] = [2, 2]
    else:
        predictions.pop()
    with pytest.raises(WorkflowError) as caught:
        evaluate(predictions, targets, dataset="toy", cutoff=2)
    assert caught.value.code == code


def test_supported_workflow_signature_defaults_and_purity():
    assert list(inspect.signature(audit).parameters) == ["mapping", "budget"]
    assert inspect.signature(audit).parameters["budget"].default is None
    signature = inspect.signature(evaluate)
    assert signature.parameters["cutoff"].default == 10
    assert signature.parameters["dataset"].kind == inspect.Parameter.KEYWORD_ONLY
    predictions, targets = inputs()
    before = json.dumps([predictions, targets])
    assert evaluate(predictions, targets, dataset="toy", cutoff=2) == evaluate(predictions, targets, dataset="toy", cutoff=2)
    assert json.dumps([predictions, targets]) == before
    with pytest.raises(WorkflowError) as caught:
        audit([{"item_id": 1, "sid": [0]}, {"item_id": 1, "sid": [1]}])
    assert caught.value.code == "duplicate_mapping_item"


@pytest.mark.parametrize("extension", ["csv", "parquet"])
def test_own_mapping_file_without_internal_json(tmp_path, extension):
    import pandas as pd
    frame = pd.DataFrame({"item_id": [1, 2], "sid_level_0": [0, 0], "sid_level_1": [1, 1]})
    path, output = tmp_path / ("mapping."+extension), tmp_path / "audit.json"
    if extension == "csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_parquet(path, index=False)
    assert main(["audit", "--input", str(path), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["findings"][0]["normalized_items"] == [1, 2]


def test_all_public_cli_and_python_reports_are_identical(tmp_path):
    predictions, targets = inputs()
    arguments = {"predictions": predictions, "targets": targets, "dataset": "toy", "cutoff": 2}
    source, output = tmp_path / "inputs.json", tmp_path / "evaluation.json"
    source.write_text(json.dumps(arguments))
    assert main(["evaluate", "--input", str(source), "--output", str(output)]) == 0
    report = evaluate(**arguments)
    assert json.loads(output.read_text()) == report
    source.write_text(json.dumps({"left": report, "right": report}))
    compared = tmp_path / "compared.json"
    assert main(["compare", "--input", str(source), "--output", str(compared)]) == 0
    assert json.loads(compared.read_text()) == compare(report, report)
