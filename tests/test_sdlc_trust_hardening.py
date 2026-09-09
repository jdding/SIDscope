"""Adversarial regressions from the pre-2.0 SDLC review, not new evidence."""
import json
import itertools
from pathlib import Path

import pytest

from sidinspector.contracts import (
    RuntimeContractValidationError, validate_trace_envelope, with_content_sha256,
)
from sidinspector.submission import (
    SubmissionValidationError, check_submission, validate_submission_package,
    generate_submission_indexes,
)
from sidinspector.evidence import (
    EvidenceBundleValidationError, validate_evidence_bundle, compare_evidence_bundles,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "examples/conformance_ecosystem_fixture/submission/positive"


def bundle_document():
    return json.loads((PACKAGE / "evidence/bundle.json").read_text())


@pytest.mark.parametrize("flag", ["catalog_reachable", "generated", "resolved"])
def test_exact_target_requires_reachable_generated_resolved(flag):
    trace = json.loads((ROOT / "examples/canonical_pipeline_fixture/trace_envelope.json").read_text())
    trace["observations"][0]["target"][flag] = False
    with pytest.raises(RuntimeContractValidationError) as caught:
        validate_trace_envelope(with_content_sha256(trace))
    assert caught.value.code in {"exact_rank_without_resolution", "inconsistent_target_state"}


def test_deep_submission_json_returns_typed_rejection(tmp_path):
    (tmp_path / "submission.json").write_text("[" * 1500 + "0" + "]" * 1500)
    report = check_submission(tmp_path)
    assert report.status == "rejected"
    assert report.failures[0]["code"] == "submission_json_depth_exceeded"


def test_submission_size_budget_precedes_read_and_parse(tmp_path, monkeypatch):
    import sidinspector.submission.checker as checker
    monkeypatch.setattr(checker, "MAX_ARTIFACT_BYTES", 128, raising=False)
    (tmp_path / "submission.json").write_text(" " * 129)
    report = check_submission(tmp_path)
    assert report.status == "rejected"
    assert report.failures[0]["code"] == "submission_artifact_too_large"


@pytest.mark.parametrize("value", [-0.1, 1.01, 42])
@pytest.mark.parametrize("metric", ["hit_at_10", "recall_at_20", "ndcg_at_10"])
def test_rehashed_out_of_range_metrics_fail(value, metric):
    bundle = bundle_document()
    bundle["result_card"]["overall_metrics"][metric] = value
    bundle = with_content_sha256(bundle)
    with pytest.raises(EvidenceBundleValidationError) as caught:
        validate_evidence_bundle(bundle)
    assert caught.value.code == "standard_metric_out_of_range"
    assert compare_evidence_bundles(bundle_document(), bundle)["status"] == "rejected"


def test_hash_only_comparison_never_claims_recomputed_metrics():
    from sidinspector.evidence.comparison import compare_legacy_evidence_bundles
    left = bundle_document()
    right = bundle_document()
    right["result_card"]["overall_metrics"]["hit_at_10"] = 0.9
    left["result_card"]["overall_metrics"]["custom_score"] = 1
    right["result_card"]["overall_metrics"]["custom_score"] = 2
    assert compare_evidence_bundles(with_content_sha256(left), with_content_sha256(right))["status"] == "incompatible"
    result = compare_legacy_evidence_bundles(with_content_sha256(left), with_content_sha256(right))
    assert result["method_difference"]["verification_level"] == "declared_metrics_not_recomputed"
    assert result["method_difference"]["overall_metrics"]["custom_score"]["delta"] is None


def test_caller_gate_declarations_cannot_admit_or_publish():
    report = check_submission(PACKAGE)
    assert report.status == "rejected"
    assert report.failures[0]["code"] == "independent_gate_verification_required"
    with pytest.raises(SubmissionValidationError) as caught:
        generate_submission_indexes([validate_submission_package(PACKAGE)])
    assert caught.value.code == "independent_gate_verification_required"


def test_artifact_count_and_total_budgets(tmp_path, monkeypatch):
    import sidinspector.submission.checker as checker
    monkeypatch.setattr(checker, "MAX_SUBMISSION_ARTIFACTS", 2)
    assert check_submission(PACKAGE).failures[0]["code"] == "submission_artifact_count_exceeded"
    monkeypatch.setattr(checker, "MAX_SUBMISSION_ARTIFACTS", 256)
    monkeypatch.setattr(checker, "MAX_SUBMISSION_BYTES", (PACKAGE / "submission.json").stat().st_size + 10)
    assert check_submission(PACKAGE).failures[0]["code"] == "submission_total_too_large"


@pytest.mark.parametrize("payload", [b'{', b'\xff', b'{"x":NaN}', b'{"x":"\\ud800"}'])
def test_malformed_json_is_typed(tmp_path, payload):
    (tmp_path / "submission.json").write_bytes(payload)
    report = check_submission(tmp_path)
    assert report.status == "rejected"
    assert report.failures[0]["code"] == "invalid_json_artifact"


def test_brackets_inside_strings_do_not_exhaust_depth_budget():
    from sidinspector.submission.checker import _read_json_bytes
    from sidinspector.contracts import canonical_json_bytes
    value = {"note": '[{\\"' * 2000}
    assert _read_json_bytes(canonical_json_bytes(value) + b"\n", "quoted") == value


def test_resolved_state_truth_table():
    source = json.loads((ROOT / "examples/canonical_pipeline_fixture/trace_envelope.json").read_text())
    for reachable, generated in itertools.product([False, True], repeat=2):
        target = source["observations"][0]["target"]
        target.update(catalog_reachable=reachable, generated=generated)
        if reachable and generated:
            validate_trace_envelope(with_content_sha256(source))
        else:
            with pytest.raises(RuntimeContractValidationError) as caught:
                validate_trace_envelope(with_content_sha256(source))
            assert caught.value.code == "inconsistent_target_state"
