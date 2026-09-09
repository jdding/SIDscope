import json

import pytest

from tools.verify_sidscope_sid_refresh import main, verify


def _preflight(path, mapping):
    path.write_text(json.dumps({
        "dataset": "external/declaration",
        "catalog": [],
        "interactions": [],
        "splits": [],
        "targets": [],
        "mapping": [{"item_id": item, "sid": sid} for item, sid in mapping],
    }))


def test_real_shape_control_uses_route_specific_semantics_and_preserves_inputs(tmp_path):
    rpg, psid = tmp_path / "rpg.json", tmp_path / "psid.json"
    _preflight(rpg, [(1, [0, 0, 2]), (2, [0, 1, 2])])
    _preflight(psid, [(1, [0, 1]), (2, [0, 2])])
    before = rpg.read_bytes(), psid.read_bytes()
    result = verify(rpg, psid)
    assert result["status"] == "pass"
    assert result["routes"][0]["semantics"] == "parallel_positions"
    assert result["routes"][0]["structural_scopes"] == ["full_code"]
    assert result["routes"][1]["structural_scopes"] == ["prefix", "prefix", "full_code"]
    assert (rpg.read_bytes(), psid.read_bytes()) == before


def test_control_cli_never_overwrites_and_fails_closed(tmp_path, capsys):
    rpg, psid, output = tmp_path / "rpg.json", tmp_path / "psid.json", tmp_path / "result.json"
    _preflight(rpg, [(1, [0, 0])])
    _preflight(psid, [(1, [0])])
    argv = ["--rpg-preflight", str(rpg), "--psid-preflight", str(psid), "--output", str(output)]
    assert main(argv) == 0
    capsys.readouterr()
    assert main(argv) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "fail"
    bad = tmp_path / "bad.json"
    _preflight(bad, [(1, [0]), (1, [1])])
    with pytest.raises(ValueError):
        verify(bad, psid)
