"""Executable positive admission and adversarial protocol-bound comparisons."""
import json
from pathlib import Path

import pytest

from sidinspector.contracts import with_content_sha256
from sidinspector.contracts.evaluation_protocol import validate_evaluation_protocol, EvaluationProtocolError
from sidinspector.evidence.comparison import compare_evidence_bundles
from sidinspector.evidence.recomputation import recompute_bundle
from sidinspector.evidence.bundle import EvidenceBundleValidationError
from sidinspector.submission.checker import check_submission, validate_submission_package
from sidinspector.submission.recomputed import build_recomputed_submission
from sidinspector.submission.indexes import generate_status_index, generate_result_index

ROOT = Path(__file__).resolve().parents[1]


def build(tmp_path, name="new", selection=None):
    fixture = ROOT / "examples/canonical_pipeline_fixture"
    trace = json.loads((fixture / "trace_envelope.json").read_text())
    selection = selection or json.loads((fixture / "episode_selection.json").read_text())
    trace["episode_selection_binding"]["content_sha256"] = selection["content_sha256"]
    trace = with_content_sha256(trace)
    output = tmp_path / name
    result = build_recomputed_submission(ROOT / "examples/conformance_ecosystem_fixture/submission/positive", output, trace=trace, selection=selection)
    assert result["status"] == "accepted", result
    assert result["bindings"]["status_label"] == "diagnostics_verified"
    return validate_submission_package(output)


def test_positive_admission_and_comparison(tmp_path):
    package = build(tmp_path)
    assert check_submission(tmp_path / "new").status == "accepted"
    assert generate_status_index([package])["entries"][0]["status_label"] == "diagnostics_verified"
    assert generate_result_index([package])["entries"][0]["result_card"] == package.evidence_bundle.result_card
    evidence = recompute_bundle(package.evidence_bundle, package.objects)
    assert evidence["unverified_claims"] == ["native_trace_authenticity", "training_reproducibility", "named_adapter"]
    result = compare_evidence_bundles(package.evidence_bundle, package.evidence_bundle, left_objects=package.objects, right_objects=package.objects)
    assert result["status"] == "compatible"
    assert result["method_difference"]["compute"]["delta"] is None
    assert result["method_difference"]["verification_level"] == "recomputed_diagnostics"


def test_self_hashed_metric_tampering_rejected(tmp_path):
    package = build(tmp_path)
    bundle = package.evidence_bundle.to_dict()
    key = next(iter(bundle["result_card"]["overall_metrics"]))
    bundle["result_card"]["overall_metrics"][key] = 0.123
    with pytest.raises(EvidenceBundleValidationError, match="result_card") as error:
        recompute_bundle(with_content_sha256(bundle), package.objects)
    assert error.value.code == "recomputed_result_card_mismatch"


def test_absent_and_tampered_objects_fail_closed(tmp_path):
    package = build(tmp_path)
    assert compare_evidence_bundles(package.evidence_bundle, package.evidence_bundle)["status"] == "incompatible"
    objects = dict(package.objects)
    row = next(row for row in package.evidence_bundle.artifacts if row["role"] == "trace")
    objects[row["object_sha256"]] += b" "
    with pytest.raises(EvidenceBundleValidationError) as error:
        recompute_bundle(package.evidence_bundle, objects)
    assert error.value.code == "verification_object_hash_mismatch"


def test_same_dataset_different_population_rejected(tmp_path):
    left = build(tmp_path, "left")
    selection = json.loads((ROOT / "examples/canonical_pipeline_fixture/episode_selection.json").read_text())
    selection["selection_id"] += ":other"
    right = build(tmp_path, "right", with_content_sha256(selection))
    result = compare_evidence_bundles(left.evidence_bundle, right.evidence_bundle, left_objects=left.objects, right_objects=right.objects)
    assert result["status"] == "incompatible"
    assert result["contract_compatibility"]["reasons"][0]["code"] == "evaluation_protocol_mismatch"
    assert result["method_difference"] is None


def test_unknown_metric_definition_rejected(tmp_path):
    package = build(tmp_path)
    protocol = recompute_bundle(package.evidence_bundle, package.objects)["evaluation_protocol"]
    protocol["aggregation"] = "micro_over_unselected_items"
    with pytest.raises(EvaluationProtocolError):
        validate_evaluation_protocol(with_content_sha256(protocol))


def test_submission_builder_does_not_overwrite(tmp_path):
    build(tmp_path)
    with pytest.raises(FileExistsError):
        build(tmp_path)


def test_registry_cli_positive_object_roundtrip(tmp_path):
    import contextlib
    import io
    from sidinspector.cli import main
    package = build(tmp_path)
    root, store = tmp_path / "new", tmp_path / "store"
    arguments = ["registry", "add", "--store", str(store), "--bundle", str(root / "evidence_bundle.json")]
    for row in package.submission.artifacts:
        if row["sha256"] in package.objects:
            arguments.extend(["--artifact", f"{row['sha256']}={root / row['path']}"])
    with contextlib.redirect_stdout(io.StringIO()):
        assert main(arguments) == 0
    captured = io.StringIO()
    digest = package.evidence_bundle.content_sha256
    with contextlib.redirect_stdout(captured):
        assert main(["registry", "compare", "--store", str(store), "--left", digest, "--right", digest]) == 0
    result = json.loads(captured.getvalue())
    assert result["status"] == "compatible", result
    assert result["method_difference"]["verification_level"] == "recomputed_diagnostics"


def test_builder_cli_accepts_pretty_json_inputs(tmp_path, monkeypatch, capsys):
    from sidinspector.submission.recomputed import main
    fixture = ROOT / "examples/canonical_pipeline_fixture"
    monkeypatch.setattr("sys.argv", ["recomputed",
        "--source", str(ROOT / "examples/conformance_ecosystem_fixture/submission/positive"),
        "--trace", str(fixture / "trace_envelope.json"),
        "--selection", str(fixture / "episode_selection.json"),
        "--output", str(tmp_path / "new")])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["bindings"]["status_label"] == "diagnostics_verified"


def _registry_fixture(tmp_path):
    from sidinspector.evidence import ObjectStore, EvidenceRegistry
    package = build(tmp_path)
    store = ObjectStore(tmp_path / "store")
    store.admit_bundle(package.evidence_bundle, {
        row["object_sha256"]: package.objects[row["object_sha256"]]
        for row in package.evidence_bundle.artifacts if row["availability"] == "embedded_public"
    })
    registry = EvidenceRegistry(store.root / "registry.sqlite3")
    registry.add(package.evidence_bundle)
    return store, registry, package.evidence_bundle.content_sha256


@pytest.mark.parametrize("operand", ["left", "right"])
@pytest.mark.parametrize("state", ["quarantined", "cas_only", "index_only", "missing", "tampered"])
def test_registry_compare_requires_active_authoritative_both_operands(tmp_path, capsys, operand, state):
    from sidinspector.cli import main
    from sidinspector.contracts import canonical_json_bytes
    store, registry, suspect = _registry_fixture(tmp_path)
    # A different hash with the same recomputed diagnostics is a valid baseline.
    doc = registry.show(suspect)
    doc["bundle_id"] += ":baseline"
    doc = with_content_sha256(doc)
    store.admit_bundle(doc)
    registry.add(doc)
    if state in {"quarantined", "cas_only"}:
        store.quarantine_bundle(suspect)
    if state in {"quarantined", "index_only"}:
        registry.quarantine(suspect, reason="suspect")
    if state == "missing":
        store.bundle_path(suspect).unlink()
    if state == "tampered":
        store.bundle_path(suspect).write_bytes(canonical_json_bytes(doc))
    pair = {"left": doc["content_sha256"], "right": doc["content_sha256"]}
    pair[operand] = suspect
    assert main(["registry", "compare", "--store", str(store.root), "--left", pair["left"], "--right", pair["right"]]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["failure"]["code"] in {"bundle_quarantined", "bundle_not_found", "bundle_path_hash_mismatch"}
    assert "method_difference" not in result


def test_registry_invalid_quarantine_is_noop_and_index_failure_is_recoverable(tmp_path, capsys, monkeypatch):
    import sqlite3
    from sidinspector.cli import main
    store, registry, digest = _registry_fixture(tmp_path)
    def bytes_snapshot():
        return {str(p.relative_to(store.root)): p.read_bytes() for p in store.root.rglob("*") if p.is_file()}
    before = bytes_snapshot()
    args = ["registry", "quarantine", "--store", str(store.root), "--sha256", digest, "--reason"]
    assert main(args + [" "]) == 2
    assert json.loads(capsys.readouterr().out)["failure"]["code"] == "invalid_quarantine_reason"
    assert bytes_snapshot() == before
    def fail_index(*args, **kwargs):
        raise sqlite3.OperationalError("simulated index failure")
    with monkeypatch.context() as scoped:
        scoped.setattr(type(registry), "quarantine", fail_index)
        assert main(args + ["suspect"]) == 2
    assert json.loads(capsys.readouterr().out)["failure"]["code"] == "quarantine_index_update_failed"
    assert store.quarantine_path(digest).is_file() and not store.bundle_path(digest).exists()
    assert main(["registry", "compare", "--store", str(store.root), "--left", digest, "--right", digest]) == 2
    assert json.loads(capsys.readouterr().out)["failure"]["code"] == "bundle_quarantined"
    assert main(["registry", "rebuild", "--store", str(store.root)]) == 0
    capsys.readouterr()
    assert registry.list_bundles()[0]["status"] == "quarantined"
    assert registry.show(digest)["content_sha256"] == digest
