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
    ADAPTER_SDK_VERSION,
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
    def test_verify_recomputes_only_when_all_inputs_are_available(self) -> None:
        def invoke(arguments):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = cli_main(arguments)
            return code, json.loads(output.getvalue())

        command = ["verify", "--report", str(FIXTURE / "conformance_report.json")]
        code, result = invoke(command)
        self.assertEqual(code, 0)
        self.assertFalse(result["verification_performed"])
        self.assertEqual(result["verification_scope"], "structure_only")
        code, result = invoke(command + ["--trace", str(FIXTURE / "trace_envelope.json")])
        self.assertEqual(code, 2)
        self.assertEqual(result["failure"]["code"], "incomplete_recomputation_inputs")
        complete = ["--trace", str(FIXTURE / "trace_envelope.json"), "--selection", str(FIXTURE / "episode_selection.json")]
        code, result = invoke(command + complete + ["--diagnostic", str(FIXTURE / "diagnostic_report.json")])
        self.assertEqual(code, 0)
        self.assertTrue(result["verification_performed"])
        self.assertEqual(result["verification_scope"], "diagnostics_from_supplied_trace")
        self.assertIn("training_reproducibility", result["unverified_claims"])

        with tempfile.TemporaryDirectory() as tmp:
            document = json.loads((FIXTURE / "diagnostic_report.json").read_text())
            document["evaluation"]["hit_at_cutoff"] = 0.0
            document["slices"][0]["hit_at_cutoff"] = 0.0
            document["failure_decomposition"]["success"] = 0
            document["failure_decomposition"]["generation_search_miss"] = 1
            path = Path(tmp) / "rehashed.json"
            path.write_text(json.dumps(with_content_sha256(document)))
            code, result = invoke(command + complete + ["--diagnostic", str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(result["failure"]["code"], "metric_mismatch")

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
        with self.assertRaises(ReportContractValidationError) as captured:
            validate_diagnostic_report(with_content_sha256(document))
        self.assertEqual(captured.exception.code, "success_hit_mismatch")
        # A self-consistent falsification still needs the independent replay.
        document["evaluation"]["hit_at_cutoff"] = 0.0
        document["slices"][0]["hit_at_cutoff"] = 0.0
        document["failure_decomposition"]["success"] = 0
        document["failure_decomposition"]["generation_search_miss"] = 1
        tampered = validate_diagnostic_report(with_content_sha256(document))
        with self.assertRaises(ReportContractValidationError) as captured:
            validate_report_bindings(tampered, conformance, trace, selection)
        self.assertEqual(captured.exception.code, "metric_mismatch")

    def test_sdk_capability_and_producer_harness(self) -> None:
        self.assertEqual(ADAPTER_SDK_VERSION, "1.0.0")
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

        stable = json.loads(
            (ROOT / "examples/native_trace_payload_fixtures/adapter_capabilities.v1.json").read_text()
        )
        self.assertEqual(validate_adapter_capabilities(stable).schema, "sidscope.adapter_capabilities.v1")
        replay = dict(stable)
        replay["sdk_compatibility"] = {"minimum": "0.2.0", "maximum_exclusive": "0.3.0"}
        replay = with_content_sha256(replay)
        self.assertEqual(validate_adapter_capabilities(replay).schema, "sidscope.adapter_capabilities.v1")
        unsupported = dict(stable)
        unsupported["sdk_compatibility"] = {"minimum": "0.1.0", "maximum_exclusive": "0.2.0"}
        unsupported = with_content_sha256(unsupported)
        with self.assertRaises(AdapterSDKError) as captured:
            validate_adapter_capabilities(unsupported)
        self.assertEqual(captured.exception.code, "sdk_version_incompatible")

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
