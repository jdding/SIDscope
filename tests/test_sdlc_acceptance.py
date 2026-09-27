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
    assert result["pending_acceptance"] == []
    assert result["excluded_acceptance"] == ["independent_user_actual_use"]
    assert result["scope_unresolved_requirements"] == []
    assert result["acceptance_scope"]["policy_revision"] == 2


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
    current_scope = gate.acceptance_scope()
    records[0]["state"] = "open"
    monkeypatch.setattr(gate, "rows", lambda: records)
    # Pin the real scope resolution so the drift check itself is exercised;
    # an unmapped regressed row otherwise fails closed earlier by design.
    monkeypatch.setattr(gate, "acceptance_scope", lambda: current_scope)
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
    assert "adoption is excluded from current gates (ADR-0025) and remains not verified" in workflows


def _scope_policy():
    import json
    from tools import sidscope_acceptance_scope as scope_mod
    return json.loads((gate.ROOT / scope_mod.SCOPE_RELATIVE_PATH).read_text()), scope_mod


def _write_scope(tmp_path, policy):
    import json
    from tools import sidscope_acceptance_scope as scope_mod
    path = tmp_path / scope_mod.SCOPE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy))
    adr = tmp_path / policy["decision"]["adr"]
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text("# stub decision record\n")
    return tmp_path


def test_scope_policy_records_owner_decision_without_fabricating_adoption():
    policy, scope_mod = _scope_policy()
    records = gate.rows()
    loaded = scope_mod.load_acceptance_scope(gate.ROOT, records)
    assert loaded == policy
    assert policy["policy_revision"] == 2
    assert policy["decision"]["decided_by"] == "project_owner"
    assert policy["decision"]["date"] == "2026-09-27"
    excluded = [c for c in policy["conditions"] if c["scope"] == "excluded"]
    assert [c["condition_id"] for c in excluded] == ["independent_user_actual_use"]
    assert excluded[0]["condition_type"] == "independent_user_adoption"
    assert excluded[0]["fact_status"] == "not_verified"
    for row in records:
        if row["id"] in {"F09", "N01"}:
            assert row["user_accepted"] == "pending_actual_use"
            assert row["state"] != "verified"
    resolution = scope_mod.resolve_requirement_scope(records, loaded)
    assert resolution["excluded_acceptance"] == ["independent_user_actual_use"]
    assert resolution["unresolved_requirements"] == []


def test_producer_technical_chains_stay_required_and_gate_on_regression():
    policy, scope_mod = _scope_policy()
    records = gate.rows()
    technical = {c["condition_id"]: c for c in policy["conditions"] if c["condition_type"] == "technical_chain"}
    assert set(technical) == {"distinct_family_producer_technical_chains", "minimum_observed_review_workflow"}
    assert all(c["scope"] == "required" for c in technical.values())
    assert set(technical["distinct_family_producer_technical_chains"]["covered_by_requirements"]) == {"N03"}
    from copy import deepcopy
    regressed = deepcopy(records)
    next(row for row in regressed if row["id"] == "N03")["state"] = "partial"
    # A regressed coverage requirement becomes a gating row the policy does not
    # model, so resolution refuses instead of silently scoping F09 out.
    with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
        scope_mod.resolve_requirement_scope(regressed, policy)
    assert caught.value.code == "scope_requirement_unmapped"
    assert "N03" in caught.value.detail


def test_missing_scope_policy_fails_closed(tmp_path):
    policy, scope_mod = _scope_policy()
    with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
        scope_mod.load_acceptance_scope(tmp_path, gate.rows())
    assert caught.value.code == "scope_policy_missing"


def test_scope_policy_mutations_fail_closed(tmp_path):
    import json
    policy, scope_mod = _scope_policy()
    deep = json.loads(json.dumps(policy))
    deep["schema"] = scope_mod.SCHEMA.replace("v1", "v0")
    with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
        scope_mod.load_acceptance_scope(_write_scope(tmp_path, deep), gate.rows())
    assert caught.value.code == "scope_policy_invalid"
    deep = json.loads(json.dumps(policy))
    deep["policy_revision"] = 1
    with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
        scope_mod.load_acceptance_scope(_write_scope(tmp_path, deep), gate.rows())
    assert caught.value.code == "scope_policy_invalid"
    deep = json.loads(json.dumps(policy))
    deep["conditions"][0]["requirement_ids"] = ["F09", "F99"]
    with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
        scope_mod.load_acceptance_scope(_write_scope(tmp_path, deep), gate.rows())
    assert caught.value.code == "scope_policy_unknown_requirement"
    for requirement_id in ("F01", "F02", "F11"):
        deep = json.loads(json.dumps(policy))
        deep["conditions"].append({
            "condition_id": f"excluded_{requirement_id.lower()}_chain",
            "requirement_ids": [requirement_id],
            "condition_type": "technical_chain",
            "scope": "excluded",
            "fact_status": "tampered",
        })
        with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
            scope_mod.load_acceptance_scope(_write_scope(tmp_path, deep), gate.rows())
        assert caught.value.code == "scope_policy_forbidden_exclusion"
    deep = json.loads(json.dumps(policy))
    deep["conditions"][0]["requirement_ids"] = ["F02"]
    with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
        scope_mod.load_acceptance_scope(_write_scope(tmp_path, deep), gate.rows())
    assert caught.value.code == "scope_policy_forbidden_exclusion"


def test_unmapped_gating_requirement_fails_closed():
    import json
    policy, scope_mod = _scope_policy()
    deep = json.loads(json.dumps(policy))
    deep["conditions"] = [c for c in deep["conditions"] if c["condition_id"] != "distinct_family_producer_technical_chains"]
    deep["conditions"][0]["requirement_ids"] = ["N01"]
    with pytest.raises(scope_mod.AcceptanceScopeError) as caught:
        scope_mod.resolve_requirement_scope(gate.rows(), deep)
    assert caught.value.code == "scope_requirement_unmapped"


def test_current_scope_sentence_is_consistent_across_plan_rc_and_freeze_documents():
    for name in gate.SCOPE_SENTINEL_DOCUMENTS:
        assert gate.SCOPE_SENTINEL in (gate.ROOT / name).read_text(), name
