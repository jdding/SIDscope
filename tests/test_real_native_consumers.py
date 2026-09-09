import json
from pathlib import Path

import pytest

from tools.inspect_sidscope_native_export import NativeInspectionError, inspect_export

ROOT = Path(__file__).resolve().parents[1]
RPG = ROOT / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"
PSID = ROOT / "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json"


def test_two_real_native_semantics_deterministic():
    rpg, psid = inspect_export(RPG), inspect_export(PSID)
    assert rpg == inspect_export(RPG)
    assert psid == inspect_export(PSID)
    assert rpg["native_semantics"] != psid["native_semantics"]
    assert rpg["metrics"]["population_size"] == 5
    assert rpg["metrics"]["hit_at_cutoff"] == 0.2
    assert len(psid["records"]) == 5
    assert psid["metrics"]["hit_at_cutoff"] is None
    assert psid["metrics"]["reason"] == "target_labels_not_exported"
    assert not rpg["retraining_performed"] and not psid["retraining_performed"]


@pytest.mark.parametrize("source", [RPG, PSID])
def test_native_tamper_fails(tmp_path, source):
    doc = json.loads(source.read_text())
    if source == RPG:
        doc["episodes"][0]["target_rank"] = 999
    else:
        doc["decode_state_kind"] = "unordered_token_set_graph_propagation"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(NativeInspectionError):
        inspect_export(path)


def test_native_depth_and_size_bounded(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"[" * 100 + b"0" + b"]" * 100)
    with pytest.raises(NativeInspectionError, match="depth"):
        inspect_export(path)
    path.write_bytes(b" " * (8 * 1024 * 1024 + 1))
    with pytest.raises(NativeInspectionError, match="budget"):
        inspect_export(path, max_input_bytes=8 * 1024 * 1024)


@pytest.mark.parametrize("payload", [b'\xff', b'{"x":', b'{"x":1,"x":2}', b'{"x":1e9999}'])
def test_native_invalid_json_never_reaches_historical_verifier(tmp_path, payload):
    path = tmp_path / "invalid.json"
    path.write_bytes(payload)
    with pytest.raises(NativeInspectionError):
        inspect_export(path)
