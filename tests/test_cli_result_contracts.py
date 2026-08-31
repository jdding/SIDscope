from __future__ import annotations

import json
import unittest
from pathlib import Path

from sidinspector.schemas.result_contracts import (
    CLI_RESULT_SCHEMA_IDS,
    CLIResultValidationError,
    validate_cli_result,
)


ROOT = Path(__file__).resolve().parents[1]


class CLIResultContractsTest(unittest.TestCase):
    def test_python_and_json_schema_authorities_cover_same_ids(self) -> None:
        resource = json.loads(
            (ROOT / "src/sidinspector/schemas/cli_result.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        schema_ids = resource["properties"]["schema"]["enum"]
        self.assertEqual(schema_ids, list(CLI_RESULT_SCHEMA_IDS))
        self.assertEqual(schema_ids, sorted(set(schema_ids)))

    def test_pass_and_fail_envelopes_are_accepted(self) -> None:
        for schema_id in CLI_RESULT_SCHEMA_IDS:
            self.assertEqual(
                validate_cli_result(
                    {"schema": schema_id, "status": "pass", "failure": None}
                )["status"],
                "pass",
            )
        self.assertEqual(
            validate_cli_result(
                {
                    "schema": "sidscope.contract_validation.v1",
                    "status": "fail",
                    "failure": {"code": "fixture_failure", "detail": "expected"},
                }
            )["status"],
            "fail",
        )

    def test_invalid_envelopes_fail_closed_with_typed_codes(self) -> None:
        cases = (
            ({"schema": "unknown", "status": "pass", "failure": None}, "unknown_cli_result_schema"),
            ({"schema": CLI_RESULT_SCHEMA_IDS[0], "status": "unknown", "failure": None}, "invalid_status"),
            ({"schema": CLI_RESULT_SCHEMA_IDS[0], "status": "pass"}, "missing_failure_field"),
            (
                {
                    "schema": CLI_RESULT_SCHEMA_IDS[0],
                    "status": "pass",
                    "failure": {"code": "x", "detail": "y"},
                },
                "pass_with_failure",
            ),
            (
                {"schema": CLI_RESULT_SCHEMA_IDS[0], "status": "fail", "failure": None},
                "invalid_failure",
            ),
        )
        for value, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(CLIResultValidationError) as caught:
                    validate_cli_result(value)
                self.assertEqual(caught.exception.code, expected)


if __name__ == "__main__":
    unittest.main()
