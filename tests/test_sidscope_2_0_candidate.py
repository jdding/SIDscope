import json
import pytest

from tools.verify_sidscope_2_0_candidate import main, verify


def test_engineering_candidate_is_policy_scoped_and_not_delivery_ready():
    result = verify()
    assert result["status"] == "pass"
    assert result["package_version"] == "1.7.0.dev0"
    assert result["adapter_sdk_version"] == "1.0.0"
    assert result["python_facade_symbol_count"] == 39
    assert result["engineering_ready"] is True
    assert result["implementation_ready"] is True
    assert result["delivery_ready"] is False
    assert result["certification_ready"] is False
    assert result["certification_blockers"] == []
    assert result["ledger_unclosed_requirements"] == ["F09"]
    assert result["pending_acceptance"] == []
    assert result["excluded_acceptance"] == ["independent_user_actual_use"]
    assert result["acceptance_scope"]["policy_revision"] == 2
    assert result["excluded_candidates"] == ["N09", "N10"]
    assert result["release_authorized"] is False


def test_cli_blocks_certification_without_delivery_evidence(capsys):
    assert main(["--require-engineering-ready"]) == 0
    capsys.readouterr()
    assert main(["--require-certification-ready"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["pending_acceptance"] == []
    assert result["excluded_acceptance"] == ["independent_user_actual_use"]
    assert result["delivery_ready"] is False


def test_full_delivery_evidence_unlocks_the_certification_transition(monkeypatch, capsys):
    from tools import verify_sidscope_2_0_candidate as gate
    state = gate.verify_sdlc()
    state.update(unresolved_certification_blockers=[], pending_acceptance=[],
                 implementation_ready=True, delivery_ready=True, certification_ready=True)
    monkeypatch.setattr(gate, "verify_sdlc", lambda: state)
    monkeypatch.setattr(gate, "verify_release_metadata", lambda: {"package_version": "1.7.0.dev0"})
    assert gate.main(["--require-certification-ready"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["certification_ready"] is True and result["release_authorized"] is False


@pytest.mark.parametrize("version", ["1.7.0.dev0", "2.0.0rc1", "2.0.0rc2"])
def test_recorded_actual_use_transition_path_stays_executable(monkeypatch, capsys, version):
    from tools import verify_sidscope_2_0_candidate as gate
    state = gate.verify_sdlc()
    state.update(unresolved_certification_blockers=[], pending_acceptance=[],
                 implementation_ready=True, delivery_ready=True, certification_ready=True)
    monkeypatch.setattr(gate, "verify_sdlc", lambda: state)
    monkeypatch.setattr(gate, "verify_release_metadata", lambda: {"package_version": version})
    assert gate.main(["--require-certification-ready"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["certification_ready"] is True and result["release_authorized"] is False


@pytest.mark.parametrize("version,unresolved,delivery_ready", [
    ("2.0.0rc1", [], False),
    ("2.0.0rc1", ["F09"], True),
    ("1.7.0.dev0", ["F01"], True),
    ("1.8.0.dev0", [], True),
])
def test_candidate_transition_stays_fail_closed(monkeypatch, capsys, version, unresolved, delivery_ready):
    from tools import verify_sidscope_2_0_candidate as gate
    state = gate.verify_sdlc()
    certification_ready = delivery_ready and not unresolved
    state.update(unresolved_certification_blockers=unresolved, delivery_ready=delivery_ready,
                 implementation_ready=True, certification_ready=certification_ready)
    monkeypatch.setattr(gate, "verify_sdlc", lambda: state)
    monkeypatch.setattr(gate, "verify_release_metadata", lambda: {"package_version": version})
    assert gate.main(["--require-certification-ready"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] in {"blocked", "fail"}


def test_inconsistent_certification_state_fails_closed(monkeypatch, capsys):
    from tools import verify_sidscope_2_0_candidate as gate
    state = gate.verify_sdlc()
    state.update(unresolved_certification_blockers=[], pending_acceptance=[],
                 implementation_ready=True, delivery_ready=False, certification_ready=True)
    monkeypatch.setattr(gate, "verify_sdlc", lambda: state)
    monkeypatch.setattr(gate, "verify_release_metadata", lambda: {"package_version": "1.7.0.dev0"})
    assert gate.main(["--require-certification-ready"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "fail"


def test_unexpected_scope_exclusion_fails_closed(monkeypatch, capsys):
    from tools import verify_sidscope_2_0_candidate as gate
    state = gate.verify_sdlc()
    state.update(excluded_acceptance=["independent_user_actual_use", "recomputed_admission_chain"])
    monkeypatch.setattr(gate, "verify_sdlc", lambda: state)
    monkeypatch.setattr(gate, "verify_release_metadata", lambda: {"package_version": "1.7.0.dev0"})
    assert gate.main([]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "fail"
