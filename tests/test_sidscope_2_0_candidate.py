import json
import pytest

from tools.verify_sidscope_2_0_candidate import main, verify


def test_engineering_candidate_is_frozen_but_not_certified():
    result = verify()
    assert result["status"] == "pass"
    assert result["package_version"] == "1.7.0.dev0"
    assert result["adapter_sdk_version"] == "1.0.0"
    assert result["python_facade_symbol_count"] == 39
    assert result["engineering_ready"] is True
    assert result["certification_ready"] is False
    assert result["certification_blockers"] == ["F09"]
    assert result["excluded_candidates"] == ["N09", "N10"]
    assert result["release_authorized"] is False


def test_cli_blocks_certification_without_changing_acceptance(capsys):
    assert main(["--require-engineering-ready"]) == 0
    capsys.readouterr()
    assert main(["--require-certification-ready"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["pending_acceptance"] == ["independent_user_actual_use"]


@pytest.mark.parametrize("version", ["1.7.0.dev0", "2.0.0rc1", "2.0.0rc2"])
def test_recorded_actual_use_has_positive_certification_transition(monkeypatch, capsys, version):
    from tools import verify_sidscope_2_0_candidate as gate
    state = gate.verify_sdlc()
    state.update(blocking_requirements=[], pending_acceptance=[], certification_ready=True)
    monkeypatch.setattr(gate, "verify_sdlc", lambda:state)
    monkeypatch.setattr(gate, "verify_release_metadata", lambda:{"package_version":version})
    assert gate.main(["--require-certification-ready"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["certification_ready"] is True and result["release_authorized"] is False


@pytest.mark.parametrize("version,blockers,ready", [
    ("2.0.0rc1", ["F09"], False), ("1.7.0.dev0", ["F01"], False),
    ("1.7.0.dev0", ["F09"], True), ("1.8.0.dev0", [], True),
])
def test_candidate_transition_stays_fail_closed(monkeypatch, capsys, version, blockers, ready):
    from tools import verify_sidscope_2_0_candidate as gate
    state = gate.verify_sdlc()
    state.update(blocking_requirements=blockers, certification_ready=ready)
    monkeypatch.setattr(gate, "verify_sdlc", lambda:state)
    monkeypatch.setattr(gate, "verify_release_metadata", lambda:{"package_version":version})
    assert gate.main(["--require-certification-ready"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "fail"
