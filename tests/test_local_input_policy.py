import json
from pathlib import Path
import pytest
from sidscope.workflows import audit, evaluate, compare, main, LocalInputBudget, WorkflowError
from sidinspector.contracts.json_io import load_json, JSONInputError, MAX_JSON_BYTES
from tools.inspect_sidscope_native_export import inspect_export, NativeInspectionError


def mapping(n=10001):
    return [{"item_id": i, "sid": [i, 0]} for i in range(n)]


@pytest.mark.parametrize("extension", ["json", "csv", "parquet"])
def test_local_inputs_cross_old_row_limit_and_preserve_api_cli_parity(tmp_path, extension):
    rows = mapping()
    path, output = tmp_path / ("mapping."+extension), tmp_path / "report.json"
    if extension == "json":
        path.write_text(json.dumps(rows))
    else:
        import pandas as pd
        frame = pd.DataFrame({"item_id": range(len(rows)), "sid_level_0": range(len(rows)), "sid_level_1": 0})
        if extension == "csv":
            frame.to_csv(path, index=False)
        else:
            frame.to_parquet(path, index=False)
    expected = audit(rows)
    assert audit(path) == expected
    assert main(["audit", "--input", str(path), "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == expected
    with pytest.raises(WorkflowError, match="workflow_row_budget"):
        audit(path, budget=LocalInputBudget(max_rows=10000))
    assert audit(path, budget=LocalInputBudget(max_rows=10001)) == expected


def test_large_local_json_does_not_disable_untrusted_default(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_bytes(b" " * MAX_JSON_BYTES + json.dumps(mapping(2)).encode())
    assert audit(path) == audit(mapping(2))
    with pytest.raises(JSONInputError, match="json_size_exceeded"):
        load_json(path)
    with pytest.raises(JSONInputError, match="json_size_exceeded"):
        audit(path, budget=LocalInputBudget(max_input_bytes=MAX_JSON_BYTES))
    assert audit(path, budget=LocalInputBudget(max_input_bytes=path.stat().st_size)) == audit(mapping(2))


def test_large_local_evaluation_and_comparison_roundtrip(tmp_path):
    predictions = [{"episode_id": str(i), "ranked_items": [None, 2]} for i in range(10001)]
    targets = [{"episode_id": str(i), "target_item_id": 2, "slice": str(i)} for i in range(10001)]
    arguments = dict(predictions=predictions, targets=targets, dataset="scale", cutoff=2)
    report = evaluate(**arguments)
    assert len(report["metrics"]["slices"]) == 10001
    path, output = tmp_path / "inputs.json", tmp_path / "evaluated.json"
    path.write_bytes(b" " * MAX_JSON_BYTES + json.dumps(arguments).encode())
    assert main(["evaluate", "--input", str(path), "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == report
    path.write_bytes(b" " * MAX_JSON_BYTES + json.dumps({"left": report, "right": report}).encode())
    output = tmp_path / "compared.json"
    assert main(["compare", "--input", str(path), "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == compare(report, report)
    with pytest.raises(WorkflowError, match="workflow_row_budget"):
        compare(report, report, budget=LocalInputBudget(max_rows=10000))
    output = tmp_path / "must-not-exist.json"
    assert main(["compare", "--input", str(path), "--output", str(output), "--max-input-bytes", "100"]) == 2
    assert not output.exists()


@pytest.mark.parametrize("bad", [0, -1, True, "100"])
def test_bad_budget_is_rejected(bad):
    with pytest.raises(WorkflowError, match="invalid_workflow_budget"):
        LocalInputBudget(max_rows=bad)


@pytest.mark.parametrize("payload,code", [(b'['*65+b'0'+b']'*65, "json_depth_exceeded"), (b'{"x":1,"x":2}', "duplicate_json_key"), (b'{"x":NaN}', "nonfinite_json_number"), (b'\xff', "invalid_json_input")])
def test_uncapped_local_read_keeps_structural_protections(tmp_path, payload, code):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    with pytest.raises(JSONInputError, match=code):
        audit(path)


def test_local_native_export_crosses_old_byte_limit_without_mutating_history(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"
    path = tmp_path / "large-native.json"
    path.write_bytes(b" " * MAX_JSON_BYTES + source.read_bytes())
    assert inspect_export(path)["metrics"] == inspect_export(source)["metrics"]
    with pytest.raises(NativeInspectionError, match="native_input_budget_exceeded"):
        inspect_export(path, max_input_bytes=MAX_JSON_BYTES)


def test_parquet_expansion_budget_is_explicit_and_optional(tmp_path):
    import pandas as pd
    path = tmp_path / "mapping.parquet"
    pd.DataFrame({"item_id": [1, 2], "sid_level_0": [1, 2]}).to_parquet(path)
    assert audit(path)
    with pytest.raises(WorkflowError, match="workflow_parquet_budget"):
        audit(path, budget=LocalInputBudget(max_parquet_bytes=1))


def test_no_hidden_cutoff_width_caps_and_invalid_inputs_still_fail():
    assert audit([{"item_id": 1, "sid": [0]*257}])
    result = evaluate([{"episode_id": "x", "ranked_items": list(range(10001))}], [{"episode_id": "x", "target_item_id": 10000, "slice": "all"}], dataset="scale", cutoff=10001)
    assert result["records"][0]["rank"] == 10001
    with pytest.raises(WorkflowError, match="duplicate_mapping_item"):
        audit(mapping() + [mapping(1)[0]])
