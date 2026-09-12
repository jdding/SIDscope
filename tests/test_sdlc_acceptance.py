from copy import deepcopy
import hashlib
import pytest
from tools import verify_sidscope_sdlc_acceptance as gate


def test_requirement_paths_dependencies_and_generated_status():
    result = gate.verify()
    assert result["requirement_count"] == 24
    assert result["generated_documents"] == 7
    assert result["release_authorized"] is False
    assert result["user_acceptance"] == "pending_actual_use"
    assert result["unclosed_requirements"] == ["F09"]


def test_canonical_technical_acceptance_does_not_invent_user_adoption():
    records = {row["id"]: row for row in gate.rows()}
    for name in ("F09", "N03"):
        assert "producer" in records[name]["acceptance"]
        assert "bundle" in records[name]["acceptance"]
        assert records[name]["implemented"] == "yes"
        assert "tools/build_sidscope_native_submission.py" in records[name]["implementation"]
    assert records["N03"]["state"] == "verified"
    assert records["N03"]["verified"] == "yes"
    assert records["F09"]["state"] == "partial"
    assert records["F09"]["verified"] == "no"
    assert records["F09"]["user_accepted"] == "pending_actual_use"


def test_ledger_change_without_document_update_fails(monkeypatch):
    records = deepcopy(gate.rows())
    records[0]["state"] = "open"
    monkeypatch.setattr(gate, "rows", lambda: records)
    with pytest.raises(AssertionError, match="current status drift"):
        gate.verify()


@pytest.mark.parametrize("column,value", [("tests", "tests/nonexistent.py"), ("depends_on", "F01"), ("release_authorized", "yes"), ("accountable", "invented_reviewer")])
def test_incomplete_or_invented_traceability_fails(monkeypatch, column, value):
    records = deepcopy(gate.rows())
    records[0][column] = value
    monkeypatch.setattr(gate, "rows", lambda: records)
    with pytest.raises(AssertionError):
        gate.verify()


def test_actual_use_transition_requires_consistent_traceable_record(tmp_path, monkeypatch):
    records = deepcopy(gate.rows())
    for row in records:
        if row["id"] in {"F09", "N01"}:
            row.update(state="verified", implemented="yes", verified="yes", user_accepted="yes")
    with pytest.raises(AssertionError,match="actual-use evidence required"):
        gate.user_acceptance_status(records)
    (tmp_path / "actual-use.md").write_text("Synthetic state-machine fixture only; not actual user acceptance.")
    monkeypatch.setattr(gate,"ROOT",tmp_path)
    for row in records:
        if row["id"] in {"F09", "N01"}:
            row["user_acceptance_evidence"] = "actual-use.md"
            row["user_acceptance_sha256"] = hashlib.sha256((tmp_path/"actual-use.md").read_bytes()).hexdigest()
    assert gate.user_acceptance_status(records) == "accepted"
    next(row for row in records if row["id"] == "F09")["user_acceptance_sha256"] = "0"*64
    with pytest.raises(AssertionError,match="actual-use evidence hash mismatch"):
        gate.user_acceptance_status(records)
    next(row for row in records if row["id"] == "F09")["user_acceptance_sha256"] = next(row for row in records if row["id"] == "N01")["user_acceptance_sha256"]
    next(row for row in records if row["id"] == "N01")["user_accepted"] = "pending_actual_use"
    with pytest.raises(AssertionError,match="actual-use state mismatch"):
        gate.user_acceptance_status(records)


def test_pending_human_use_cannot_be_promoted_by_verified_flag():
    records = deepcopy(gate.rows())
    next(row for row in records if row["id"] == "F09")["state"] = "verified"
    with pytest.raises(AssertionError,match="pending actual use"):
        gate.user_acceptance_status(records)


def test_n08_evidence_command_uses_the_real_parser_flag(monkeypatch, capsys):
    import sys
    from tools import benchmark_sidscope_observed_review as benchmark
    row = next(row for row in gate.rows() if row["id"] == "N08")
    assert row["evidence_command"].endswith("--repeats 3")
    captured = {}
    def fake(source, metadata, output, **kwargs):
        captured.update(kwargs)
        return {"status":"fail","summary":{}}
    monkeypatch.setattr(benchmark,"benchmark",fake)
    monkeypatch.setattr(sys,"argv",["benchmark","--input","INPUT","--metadata","META","--output","OUT","--repeats","3"])
    assert benchmark.main() == 2
    capsys.readouterr()
    assert captured["repeats"] == 3


def test_public_onboarding_distinguishes_current_paths_from_historical_rejection():
    readme = (gate.ROOT / "README.md").read_text()
    workflows = (gate.ROOT / "docs/SIDSCOPE_USER_WORKFLOWS.md").read_text()
    assert "historical structure-only fixture is an expected rejection" in readme
    assert "code=independent_gate_verification_required" in readme
    assert "N03's technical bridge is verified" in workflows
    assert "F09/N01 remain pending" in workflows
