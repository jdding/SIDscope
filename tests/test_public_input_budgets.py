import contextlib
import io
import json
from pathlib import Path
import pytest
import sidscope
from sidinspector.cli import main
from sidinspector.contracts import JSONInputError, load_json


@pytest.mark.parametrize("payload,code", [(b"[" * 100 + b"0" + b"]" * 100, "json_depth_exceeded"), (b"\xff", "invalid_json_input"), (b'{"x":', "invalid_json_input"), (b'{"x":1,"x":2}', "duplicate_json_key"), (b'{"x":NaN}', "nonfinite_json_number"), (b" " * (8*1024*1024+1), "json_size_exceeded")])
def test_all_curated_file_loaders_reject_bounded_bad_json(tmp_path, payload, code):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    names = [name for name in sidscope.__all__ if name.startswith("load_") and name not in {"load_public_schema_catalog"}]
    for name in names:
        with pytest.raises((ValueError, JSONInputError)):
            getattr(sidscope, name)(path)
    with pytest.raises(JSONInputError) as caught:
        load_json(path)
    assert caught.value.code == code


@pytest.mark.parametrize("arguments", [["schema", "validate", "--input"], ["adapter", "preflight", "--descriptor"], ["trace", "validate", "--input"], ["evidence", "bundle", "verify", "--input"], ["contract", "validate", "--type", "source-identity", "--input"]])
def test_public_cli_never_crashes_on_deep_json(tmp_path, arguments):
    path = tmp_path / "deep.json"
    path.write_bytes(b"[" * 100 + b"0" + b"]" * 100)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main([*arguments, str(path)]) == 2
    result = json.loads(output.getvalue())
    assert result["status"] == "fail"
    assert result["failure"]["code"] == "json_depth_exceeded"


def test_exponent_overflow_is_not_a_finite_json_number(tmp_path):
    path = tmp_path / "overflow.json"
    path.write_text('{"x":1e9999}')
    with pytest.raises(JSONInputError) as caught:
        load_json(path)
    assert caught.value.code == "nonfinite_json_number"
