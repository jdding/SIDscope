"""Delivery checks must execute an installed consumer path and real workloads."""
import json
import sys
from copy import deepcopy

import pytest

from sidinspector.runtime_demo import main as demo_main
from sidinspector.contracts import validate_source_identity
from tools.check_sidscope_current_performance import classify
from tools.smoke_sidscope_release_candidate_archive import smoke_archive, verify_archive_digest
from tools.sidscope_release_profiles import ReleaseProfileError


def test_runtime_demo_is_self_contained_and_never_overwrites(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["runtime_demo", "--output-dir", str(tmp_path)])
    demo_main()
    assert json.loads(capsys.readouterr().out)["synthetic"] is True
    path = tmp_path / "source_identity.json"
    validate_source_identity(json.loads(path.read_text()))
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        demo_main()
    assert path.read_bytes() == original


def test_selected_parser_preserves_each_command_contract():
    import argparse
    from sidinspector.cli import build_parser
    def tree(parser):
        result = []
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                result.append((action.dest, {name: tree(child) for name, child in action.choices.items()}))
            else:
                result.append((action.dest, action.option_strings, action.required, action.default, action.nargs, action.choices))
        return result
    full = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    for name, child in full.choices.items():
        selected = next(a for a in build_parser(name)._actions if isinstance(a, argparse._SubParsersAction))
        assert list(selected.choices) == [name]
        assert tree(selected.choices[name]) == tree(child)
        assert selected.choices[name].format_help() == child.format_help()


def test_performance_threshold_and_environment_do_not_silently_pass():
    baseline = {"environment": {"python": "3.9"}, "policy": {"review_threshold_percent": 20},
                "commands": {"evaluate": {"median_ms": 10}}}
    current = deepcopy(baseline)
    assert classify(baseline, current)[0] == "pass"
    current["commands"]["evaluate"]["median_ms"] = 12.1
    assert classify(baseline, current)[0] == "performance_review_required"
    current["environment"]["python"] = "3.12"
    assert classify(baseline, current)[0] == "environment_review_required"
    current = deepcopy(baseline)
    current["commands"] = {}
    assert classify(baseline, current)[0] == "workload_review_required"


def test_expected_digest_rejects_before_archive_execution(tmp_path):
    path = tmp_path / "untrusted.zip"
    path.write_bytes(b"not even a zip")
    with pytest.raises(ReleaseProfileError) as caught:
        smoke_archive(path, expected_sha256="0" * 64)
    assert caught.value.code == "archive_digest_mismatch"
    with pytest.raises(ReleaseProfileError) as caught:
        verify_archive_digest(path, "not-a-digest")
    assert caught.value.code == "invalid_expected_archive_digest"


def test_readiness_stays_blocked_with_open_requirements(monkeypatch, capsys):
    from tools.verify_sidscope_sdlc_hardening import main
    monkeypatch.setattr(sys, "argv", ["verify", "--require-ready"])
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["certification_ready"] is False
    assert "F01" not in result["blocking_requirements"]
    assert "F07" not in result["blocking_requirements"]
    assert "F09" in result["blocking_requirements"]
    assert result["pending_acceptance"] == ["independent_user_actual_use"]
    assert not any(item.startswith("N") for item in result["blocking_requirements"])
    assert result["engineering_ready"] is True
    assert result["engineering_blocking_requirements"] == []
    assert result["approved_local_workflow_pending"] == ["N01"]
    assert result["approved_local_workflow_ready"] is False
    assert result["candidate_requirements"] == ["N09", "N10"]
