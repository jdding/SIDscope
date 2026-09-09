from copy import deepcopy
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
