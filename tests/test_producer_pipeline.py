"""Synthetic orchestration acceptance, explicitly NOT real producer acceptance."""
import json
from pathlib import Path
import pytest

from sidinspector.contracts import with_content_sha256
from sidinspector.submission.checker import validate_submission_package
from sidscope.pipeline import run, main
from sidscope.workflows import WorkflowError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/conformance_ecosystem_fixture/submission/positive"
FIXTURE = ROOT / "examples/canonical_pipeline_fixture"
SELECTION = FIXTURE / "episode_selection.json"


class SyntheticProducer:
    def __init__(self, mutation=None):
        self.calls = 0
        self.mutation = mutation

    def get_capabilities(self):
        caps = json.loads((FIXTURE / "adapter_capabilities.json").read_text())
        caps["adapter_id"] = "external-parallel"
        return with_content_sha256(caps)

    def produce(self, kind, output):
        assert kind == "trace-envelope"
        self.calls += 1
        trace = json.loads((FIXTURE / "trace_envelope.json").read_text())
        bundle = validate_submission_package(SOURCE).evidence_bundle
        for binding, role in (("run_binding", "run"), ("checkpoint_binding", "checkpoint")):
            trace[binding]["content_sha256"] = next(r["content_sha256"] for r in bundle.artifacts if r["role"] == role)
        if self.mutation:
            self.mutation(trace)
        output.write_text(json.dumps(with_content_sha256(trace)))
        return output


def test_producer_called_bundle_recomputed_and_baseline_compared(tmp_path):
    producer = SyntheticProducer()
    left = run(producer, source=SOURCE, selection=SELECTION, output=tmp_path / "left")
    right = run(producer, source=SOURCE, selection=SELECTION, baseline=tmp_path / "left/submission", output=tmp_path / "right")
    assert producer.calls == 2
    assert left["comparison_kind"] == "self_recomputation"
    assert right["comparison_kind"] == "baseline"
    assert left["bundle_sha256"] == right["bundle_sha256"]
    assert right["comparison"]["method_difference"]["verification_level"] == "recomputed_diagnostics"
    assert "independent_user_adoption" in right["unverified_claims"]
    assert json.loads((tmp_path / "right/complete.json").read_text()) == right
    with pytest.raises(FileExistsError):
        run(producer, source=SOURCE, selection=SELECTION, output=tmp_path / "right")
    assert producer.calls == 2


@pytest.mark.parametrize("mutation,code", [
    (lambda t: t["run_binding"].update(content_sha256="a" * 64), "producer_provenance_mismatch"),
    (lambda t: t["checkpoint_binding"].update(content_sha256="a" * 64), "producer_provenance_mismatch"),
    (lambda t: t["episode_selection_binding"].update(content_sha256="a" * 64), "diagnostic_selection_binding_mismatch"),
    (lambda t: t["observations"][0]["target"].update(exact_rank=0), "invalid_count"),
])
def test_bad_export_never_publishes_output(tmp_path, mutation, code):
    with pytest.raises(ValueError) as caught:
        run(SyntheticProducer(mutation), source=SOURCE, selection=SELECTION, output=tmp_path / "failed")
    assert getattr(caught.value, "code", "") == code
    assert not (tmp_path / "failed").exists()


def test_unverified_baseline_is_not_compared(tmp_path):
    with pytest.raises(WorkflowError, match="producer_comparison_incompatible"):
        run(SyntheticProducer(), source=SOURCE, selection=SELECTION, baseline=SOURCE, output=tmp_path / "failed")
    assert not (tmp_path / "failed").exists()


def test_output_cannot_write_into_existing_source_evidence():
    producer = SyntheticProducer()
    with pytest.raises(WorkflowError, match="producer_output_inside_input"):
        run(producer, source=SOURCE, selection=SELECTION, output=SOURCE / "new-output")
    assert producer.calls == 0


def test_input_spec_cannot_select_executable_code(tmp_path, monkeypatch):
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps({"source": "x", "selection": "y", "output": "z", "producer": "bad:code"}))
    def forbidden(*args):
        raise AssertionError("untrusted input selected code")
    monkeypatch.setattr("sidscope.pipeline._load_producer", forbidden)
    assert main(["--spec", str(spec), "--producer", "chosen:factory"]) == 2


def test_cli_uses_explicit_factory_and_relative_spec_paths(tmp_path, monkeypatch):
    producer = SyntheticProducer()
    monkeypatch.setattr("sidscope.pipeline._load_producer", lambda selector: producer)
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps({"source": str(SOURCE), "selection": str(SELECTION), "output": "output"}))
    assert main(["--spec", str(spec), "--producer", "chosen:make"]) == 0
    assert producer.calls == 1
    assert (tmp_path / "output/complete.json").exists()
