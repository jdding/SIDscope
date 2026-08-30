from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main
from sidinspector.contracts import (
    ReportContractValidationError,
    load_conformance_report,
    load_diagnostic_report,
    load_episode_selection,
    load_trace_envelope,
    validate_conformance_report,
    validate_diagnostic_report,
    validate_report_bindings,
    with_content_sha256,
)
from sidinspector.sdk import (
    AdapterHarness,
    AdapterSDKError,
    load_adapter_capabilities,
    validate_adapter_capabilities,
)
from tools.verify_sidscope_1_2_closure import verify_closure


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/canonical_pipeline_fixture"


class FixtureProducer:
    def produce(self, contract_type: str, output_path: Path) -> Path:
        source = FIXTURE / f"{contract_type.replace('-', '_')}.json"
        output_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return output_path


class ReportSDKCLITest(unittest.TestCase):
    def test_reports_and_cross_metrics_pass(self) -> None:
        diagnostic = load_diagnostic_report(FIXTURE / "diagnostic_report.json")
        conformance = load_conformance_report(FIXTURE / "conformance_report.json")
        trace = load_trace_envelope(FIXTURE / "trace_envelope.json")
        selection = load_episode_selection(FIXTURE / "episode_selection.json")

        validate_report_bindings(diagnostic, conformance, trace, selection)
        self.assertEqual(diagnostic.to_dict()["evaluation"]["hit_at_cutoff"], 1.0)
        self.assertEqual(conformance.to_dict()["decision"]["status"], "fixture_pass")

    def test_report_negatives_and_recomputed_metric_tamper_fail(self) -> None:
        cases = (
            (
                "expected_failure_metric_mismatch.json",
                "metric_out_of_range",
                load_diagnostic_report,
            ),
            (
                "expected_failure_gate_order.json",
                "noncanonical_gate_order",
                load_conformance_report,
            ),
        )
        for name, expected, loader in cases:
            with self.subTest(name=name), self.assertRaises(
                ReportContractValidationError
            ) as captured:
                loader(FIXTURE / name)
            self.assertEqual(captured.exception.code, expected)

        diagnostic = load_diagnostic_report(FIXTURE / "diagnostic_report.json")
        conformance = load_conformance_report(FIXTURE / "conformance_report.json")
        trace = load_trace_envelope(FIXTURE / "trace_envelope.json")
        selection = load_episode_selection(FIXTURE / "episode_selection.json")
        document = diagnostic.to_dict()
        document["evaluation"]["hit_at_cutoff"] = 0.5
        document["slices"][0]["hit_at_cutoff"] = 0.5
        tampered = validate_diagnostic_report(with_content_sha256(document))
        with self.assertRaises(ReportContractValidationError) as captured:
            validate_report_bindings(tampered, conformance, trace, selection)
        self.assertEqual(captured.exception.code, "metric_mismatch")

    def test_sdk_capability_and_producer_harness(self) -> None:
        capabilities = load_adapter_capabilities(FIXTURE / "adapter_capabilities.json")
        with self.assertRaises(AdapterSDKError) as captured:
            load_adapter_capabilities(FIXTURE / "expected_failure_telemetry_overlap.json")
        self.assertEqual(captured.exception.code, "telemetry_overlap")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "trace.json"
            artifact = AdapterHarness(capabilities, FixtureProducer()).produce(
                "trace-envelope", output
            )
        self.assertEqual(artifact.artifact_id, "rpg:fixture-trace-envelope")

        with self.assertRaises(AdapterSDKError) as captured:
            validate_adapter_capabilities([])  # type: ignore[arg-type]
        self.assertEqual(captured.exception.code, "invalid_type")

    def test_report_decision_and_overall_slice_are_derived(self) -> None:
        conformance = load_conformance_report(FIXTURE / "conformance_report.json")
        document = conformance.to_dict()
        document["decision"]["status"] = "fail"
        with self.assertRaises(ReportContractValidationError) as captured:
            validate_conformance_report(with_content_sha256(document))
        self.assertEqual(captured.exception.code, "decision_gate_mismatch")

        diagnostic = load_diagnostic_report(FIXTURE / "diagnostic_report.json")
        document = diagnostic.to_dict()
        document["slices"][0]["episode_count"] = 2
        with self.assertRaises(ReportContractValidationError) as captured:
            validate_diagnostic_report(with_content_sha256(document))
        self.assertEqual(captured.exception.code, "overall_slice_mismatch")

        document = diagnostic.to_dict()
        document["slices"][1]["hit_at_cutoff"] = 1.1
        with self.assertRaises(ReportContractValidationError) as captured:
            validate_diagnostic_report(with_content_sha256(document))
        self.assertEqual(captured.exception.code, "metric_out_of_range")

    def test_cli_end_to_end_and_missing_dependency_failure(self) -> None:
        result = verify_closure()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["contract_count"], 11)

        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "evidence", "package",
                        "--artifact", str(FIXTURE / "conformance_report.json"),
                        "--index-id", "incomplete",
                        "--output", str(Path(tmp) / "index.json"),
                    ]
                )
        self.assertEqual(exit_code, 2)
        self.assertEqual(
            json.loads(stdout.getvalue())["failure"]["code"],
            "missing_evidence_dependency",
        )


if __name__ == "__main__":
    unittest.main()
