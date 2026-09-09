from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
PROFILE_FIXTURE = ROOT / "examples" / "conformance_ecosystem_fixture" / "profile"
SUBMISSION_FIXTURE = (
    ROOT / "examples" / "conformance_ecosystem_fixture" / "submission" / "positive"
)


def invoke(argv: list[str]) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = cli_main(argv)
    return code, json.loads(output.getvalue())


class ConformanceSubmissionCLITest(unittest.TestCase):
    def test_profile_catalog_and_bound_report_validation(self) -> None:
        code, catalog = invoke(["profile", "catalog"])
        self.assertEqual(code, 0)
        self.assertEqual(catalog["status"], "pass")
        self.assertEqual(
            [row["profile_id"] for row in catalog["profiles"]],
            ["generator_g0_g5", "overlay_g0_g5", "release_local", "static_mapping_c0_c5"],
        )

        code, report = invoke(
            [
                "profile",
                "verify",
                "--descriptor",
                str(PROFILE_FIXTURE / "dataset_profile_descriptor.json"),
                "--report",
                str(PROFILE_FIXTURE / "generator_report.json"),
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["profile_id"], "generator_g0_g5")
        self.assertEqual(report["status_label"], "unverified")
        self.assertEqual(report["declared_status_label"], "named_adapter")
        self.assertEqual(report["verification_level"], "structure_only")

    def test_submission_check_and_deterministic_index_export(self) -> None:
        code, report = invoke(
            ["submission", "check", "--root", str(SUBMISSION_FIXTURE)]
        )
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["failures"][0]["code"], "independent_gate_verification_required")

        with tempfile.TemporaryDirectory() as tmp:
            first_status = Path(tmp) / "first-status.json"
            first_result = Path(tmp) / "first-result.json"
            second_status = Path(tmp) / "second-status.json"
            second_result = Path(tmp) / "second-result.json"
            for status_path, result_path in (
                (first_status, first_result),
                (second_status, second_result),
            ):
                code, exported = invoke(
                    [
                        "submission",
                        "indexes",
                        "--root",
                        str(SUBMISSION_FIXTURE),
                        "--status-output",
                        str(status_path),
                        "--result-output",
                        str(result_path),
                    ]
                )
                self.assertEqual(code, 2)
                self.assertEqual(exported["failure"]["code"], "independent_gate_verification_required")
                self.assertFalse(status_path.exists())
                self.assertFalse(result_path.exists())

    def test_missing_submission_root_is_typed_rejection(self) -> None:
        code, report = invoke(
            ["submission", "check", "--root", "/tmp/sidscope-missing-submission-root"]
        )
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["failures"][0]["code"], "submission_root_missing")


if __name__ == "__main__":
    unittest.main()
