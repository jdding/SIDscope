"""Delivery checks must execute an installed consumer path and real workloads."""
import json
import sys
from copy import deepcopy

import pytest

from sidinspector.runtime_demo import main as demo_main
from sidinspector.contracts import validate_source_identity
from tools.benchmark_sidscope_1_2_cli import ROOT
from tools.check_sidscope_current_performance import classify, delivery_gate
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
    current = deepcopy(baseline)
    current["environment"]["python"] = "3.12"
    assert classify(baseline, current)[0] == "environment_review_required"
    current = deepcopy(baseline)
    current["commands"] = {}
    assert classify(baseline, current)[0] == "workload_review_required"


def test_delivery_performance_policy_is_narrow_and_preserves_observation_status():
    baseline = {"environment": {"implementation": "CPython", "platform": "macOS-26.5.2-arm64-arm-64bit",
                                "processor": "arm", "python": "3.9.6"},
                "policy": {"review_threshold_percent": 20}, "commands": {"evaluate": {"median_ms": 10}}}
    current = deepcopy(baseline)
    gate = delivery_gate(baseline, current)
    assert gate["status"] == "pass"
    assert gate["observation_status"] == "pass"
    assert gate["disposition"] == "same_environment_within_threshold"
    current["environment"]["platform"] = "macOS-26.6.2-arm64-arm-64bit"
    gate = delivery_gate(baseline, current)
    assert gate["status"] == "pass"
    assert gate["observation_status"] == "environment_review_required"
    assert gate["disposition"] == "platform_version_variance_within_frozen_threshold"
    assert gate["comparison_code"] == "platform_version_only"
    current["commands"]["evaluate"]["median_ms"] = 12.1
    assert delivery_gate(baseline, current)["status"] == "blocked"
    current = deepcopy(baseline)
    current["environment"]["python"] = "3.12"
    gate = delivery_gate(baseline, current)
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_python_version_mismatch"


BASELINE_ENV = {"implementation": "CPython", "platform": "macOS-26.5.2-arm64-arm-64bit",
                "processor": "arm", "python": "3.9.6"}


def _gate_with_platform(platform):
    from tools.check_sidscope_current_performance import delivery_gate
    baseline = {"environment": dict(BASELINE_ENV), "policy": {"review_threshold_percent": 20},
                "commands": {"evaluate": {"median_ms": 10}}}
    current = deepcopy(baseline)
    current["environment"]["platform"] = platform
    return delivery_gate(baseline, current)


def test_cross_platform_or_architecture_drift_is_never_a_version_variance():
    gate = _gate_with_platform("Linux-26.6.2-arm64-arm-64bit")
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_os_family_mismatch"
    gate = _gate_with_platform("macOS-26.6.2-x86_64-arm-64bit")
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_machine_architecture_mismatch"
    gate = _gate_with_platform("macOS-26.6.2-arm64-arm-32bit")
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_bitness_mismatch"
    gate = _gate_with_platform("macOS-26.6.2-arm64-x86-64bit")
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_platform_processor_mismatch"
    baseline = {"environment": dict(BASELINE_ENV), "policy": {"review_threshold_percent": 20},
                "commands": {"evaluate": {"median_ms": 10}}}
    current = deepcopy(baseline)
    current["environment"]["implementation"] = "PyPy"
    assert delivery_gate(baseline, current)["comparison_code"] == "environment_implementation_mismatch"
    # Real Linux platform.platform() output is not the recorded legacy shape.
    gate = _gate_with_platform("Linux-6.5.0-x86_64-with-glibc2.35")
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_unparseable_platform"


def test_incomplete_or_unknown_environment_cannot_pass_as_version_change():
    baseline = {"environment": dict(BASELINE_ENV), "policy": {"review_threshold_percent": 20},
                "commands": {"evaluate": {"median_ms": 10}}}
    current = deepcopy(baseline)
    del current["environment"]["python"]
    gate = delivery_gate(baseline, current)
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_incomplete"
    current = deepcopy(baseline)
    current["environment"]["platform"] = "macOS-a"
    gate = delivery_gate(baseline, current)
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "environment_unparseable_platform"
    current = deepcopy(baseline)
    current["environment"]["cpu_identifier"] = "Apple M1"
    gate = delivery_gate(baseline, current)
    assert gate["status"] == "blocked"
    assert gate["comparison_code"] == "platform_version_only" or gate["comparison_code"] == "same_environment"
    assert gate["environment_comparison"]["current_only_fields"] == ["cpu_identifier"]


def test_measurement_validity_rejects_illegal_numbers_and_workloads():
    from tools.sidscope_performance_policy import PerformancePolicyError, measurement_validity
    baseline = {"evaluate": {"median_ms": 10}}
    def current_with(value):
        return {"evaluate": {"median_ms": value}}
    for value, code in [(float("nan"), "measurement_nonfinite_median"),
                        (float("inf"), "measurement_nonfinite_median"),
                        (True, "measurement_boolean_median"),
                        (0, "measurement_nonpositive_median"),
                        (-1.0, "measurement_nonpositive_median"),
                        ("fast", "measurement_nonnumeric_median")]:
        with pytest.raises(PerformancePolicyError) as caught:
            measurement_validity(baseline, current_with(value))
        assert caught.value.code == code
    with pytest.raises(PerformancePolicyError) as caught:
        measurement_validity(baseline, {"evaluate": {}})
    assert caught.value.code == "measurement_missing_median"
    with pytest.raises(PerformancePolicyError) as caught:
        measurement_validity(baseline, {"evaluate": {"median_ms": 10}, "verify": {"median_ms": 2}})
    assert caught.value.code == "workload_command_set_mismatch"
    with pytest.raises(PerformancePolicyError) as caught:
        measurement_validity(baseline, {})
    assert caught.value.code == "workload_command_set_mismatch"
    payload_baseline = {"commands": baseline, "policy": {"review_threshold_percent": 20},
                        "environment": dict(BASELINE_ENV)}
    payload_current = {"commands": current_with(12.0), "environment": dict(BASELINE_ENV)}
    observation, ratios = classify(payload_baseline, payload_current)
    assert observation == "pass" and ratios == {"evaluate": 1.2}


def test_threshold_boundary_uses_unrounded_ratio():
    baseline = {"environment": dict(BASELINE_ENV), "policy": {"review_threshold_percent": 20},
                "commands": {"evaluate": {"median_ms": 10}}}
    current = deepcopy(baseline)
    current["commands"]["evaluate"]["median_ms"] = 12.0
    assert classify(baseline, current)[0] == "pass"
    current["commands"]["evaluate"]["median_ms"] = 12.0001
    assert classify(baseline, current)[0] == "performance_review_required"
    current["commands"]["evaluate"]["median_ms"] = 12.000001
    gate = delivery_gate(baseline, current)
    assert gate["status"] == "blocked"
    assert gate["observation_status"] == "performance_review_required"


def test_frozen_baseline_file_is_never_rewritten():
    import hashlib
    path = ROOT / "docs/reproducibility/sidscope_1_2_cli_cpu_baseline.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == \
        "62430232b6c78107773835a60aa3db8512f5cb2e5d46b4c7915d13be7d9b6d10"


def test_expected_digest_rejects_before_archive_execution(tmp_path):
    path = tmp_path / "untrusted.zip"
    path.write_bytes(b"not even a zip")
    with pytest.raises(ReleaseProfileError) as caught:
        smoke_archive(path, expected_sha256="0" * 64)
    assert caught.value.code == "archive_digest_mismatch"
    with pytest.raises(ReleaseProfileError) as caught:
        verify_archive_digest(path, "not-a-digest")
    assert caught.value.code == "invalid_expected_archive_digest"


def test_readiness_stays_blocked_without_delivery_evidence(monkeypatch, capsys):
    from tools.verify_sidscope_sdlc_hardening import main
    monkeypatch.setattr(sys, "argv", ["verify", "--require-ready"])
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["certification_ready"] is False
    assert "F01" not in result["blocking_requirements"]
    assert "F07" not in result["blocking_requirements"]
    assert "F09" in result["blocking_requirements"]
    assert result["unresolved_certification_blockers"] == []
    assert result["pending_acceptance"] == []
    assert result["excluded_acceptance"] == ["independent_user_actual_use"]
    assert not any(item.startswith("N") for item in result["blocking_requirements"])
    assert result["engineering_ready"] is True
    assert result["implementation_ready"] is True
    assert result["delivery_ready"] is False
    assert result["engineering_blocking_requirements"] == []
    assert result["approved_local_workflow_pending"] == ["N01"]
    assert result["approved_local_workflow_ready"] is False
    assert result["candidate_requirements"] == ["N09", "N10"]
