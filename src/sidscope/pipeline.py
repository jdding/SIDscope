"""Local producer -> validated trace -> diagnostics -> EvidenceBundle -> compare.

The caller explicitly selects executable producer code. A run-spec or submission
cannot select code. Existing provenance is required, never borrowed from fixtures.
"""
from __future__ import annotations
import argparse
import importlib
import json
import shutil
import tempfile
from pathlib import Path

from sidinspector.contracts import load_json, canonical_json_bytes, load_episode_selection
from sidinspector.sdk import AdapterHarness, validate_adapter_capabilities
from sidinspector.submission.checker import validate_submission_package
from sidinspector.submission.recomputed import build_recomputed_submission
from sidinspector.evidence.comparison import compare_evidence_bundles
from sidscope.workflows import WorkflowError


def _load_producer(selector):
    """Load caller-selected trusted code without exposing import machinery to specs."""
    module, factory = selector.split(":", 1)
    return getattr(importlib.import_module(module), factory)()


def run(producer, *, source, selection, output, baseline=None):
    """Execute an explicitly supplied AdapterHarness producer.

    Producer owns native generation and trace-envelope export; SIDScope does not
    supply target labels to it. This orchestrator does not certify native execution.
    source is an existing provenance submission, NOT a template/default fixture.
    Missing canonical producer exports remain an integration task, not a replay PASS.
    """
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    for root in (source, baseline):
        if root is not None and Path(root).resolve() in output.resolve().parents:
            raise WorkflowError("producer_output_inside_input", "output must not modify source or baseline evidence")
    original = validate_submission_package(Path(source))
    selected = load_episode_selection(Path(selection))
    baseline_package = validate_submission_package(Path(baseline)) if baseline else None
    caps = validate_adapter_capabilities(producer.get_capabilities())
    subject = original.evidence_bundle.subject
    if caps.adapter_id != subject["adapter_id"] or caps.method_family != subject["method_family"]:
        raise WorkflowError("producer_subject_mismatch", "producer and provenance subject differ")
    with tempfile.TemporaryDirectory(prefix="sidscope-producer-run-") as temporary:
        stage = Path(temporary)
        trace = AdapterHarness(caps, producer).produce("trace-envelope", stage / "trace.json")
        doc = trace.to_dict()
        if doc["method_family"] != caps.method_family:
            raise WorkflowError("producer_family_mismatch", "export changed declared native family")
        # Trace dependencies must agree with preserved provenance, not merely
        # be individually valid hash strings. Selection is checked by evaluation.
        for binding, role in (("run_binding", "run"), ("checkpoint_binding", "checkpoint")):
            hashes = {row["content_sha256"] for row in original.evidence_bundle.artifacts if row["role"] == role}
            if doc[binding]["content_sha256"] not in hashes:
                raise WorkflowError("producer_provenance_mismatch", role)
        result = build_recomputed_submission(Path(source), stage / "submission", trace=doc, selection=selected.to_dict())
        if result["status"] != "accepted":
            raise WorkflowError("producer_diagnostic_admission_failed", json.dumps(result, sort_keys=True))
        current = validate_submission_package(stage / "submission")
        other = baseline_package or current
        comparison = compare_evidence_bundles(other.evidence_bundle, current.evidence_bundle,
            left_objects=other.objects, right_objects=current.objects)
        if comparison["status"] != "compatible":
            raise WorkflowError("producer_comparison_incompatible", json.dumps(comparison, sort_keys=True))
        receipt = {"status": "pass", "verification_scope": "diagnostics_from_supplied_trace",
            "adapter_id": caps.adapter_id, "method_family": caps.method_family,
            "producer_called": True, "bundle_sha256": current.evidence_bundle.content_sha256,
            "comparison_kind": "baseline" if baseline else "self_recomputation",
            "comparison": comparison, "unverified_claims": ["native_execution_authenticity", "training_reproducibility", "independent_user_adoption"]}
        # Validate everything before publishing. Completion marker is written last;
        # interrupted I/O must never be interpreted as a completed run.
        output.mkdir(parents=True, exist_ok=False)
        shutil.copytree(stage / "submission", output / "submission")
        with (output / "complete.json").open("xb") as handle:
            handle.write(canonical_json_bytes(receipt)+b"\n")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer", required=True, help="Trusted installed module:zero_argument_factory; executes caller-selected code")
    parser.add_argument("--spec", required=True, type=Path, help="source/selection/output and optional baseline paths; no code fields")
    args = parser.parse_args(argv)
    try:
        spec = load_json(args.spec)
        if not isinstance(spec, dict) or set(spec) not in ({"source", "selection", "output"}, {"source", "selection", "output", "baseline"}):
            raise WorkflowError("invalid_run_spec", "source/selection/output and optional baseline required")
        if any(not isinstance(value, str) or not value for value in spec.values()):
            raise WorkflowError("invalid_run_spec", "paths must be nonempty strings")
        paths = {key: args.spec.parent / value for key, value in spec.items()}
        producer = _load_producer(args.producer)
        result = run(producer, **paths)
    except (ValueError, OSError, TypeError, AttributeError, ImportError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
