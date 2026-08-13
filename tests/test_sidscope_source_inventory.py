import csv
import json
import tempfile
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from tools.verify_sidscope_source_inventory import (
    DEFAULT_COVERAGE,
    DEFAULT_INVENTORY,
    _verify_c0_c5_report,
    verify_inventory,
)


class SIDScopeSourceInventoryTest(unittest.TestCase):
    def test_repository_inventory_matches_paper_coverage(self) -> None:
        result = verify_inventory(DEFAULT_INVENTORY, DEFAULT_COVERAGE)
        self.assertEqual(result["status"], "pass", result["failures"])
        self.assertEqual(result["route_count"], 9)

    def test_no_license_route_cannot_claim_raw_redistribution(self) -> None:
        with DEFAULT_INVENTORY.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0])
        card = next(row for row in rows if row["route_id"] == "card_p5_beauty")
        card["redistribution_policy"] = "redistribute_raw_upstream_artifact"

        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "inventory.csv"
            with inventory.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            result = verify_inventory(inventory, DEFAULT_COVERAGE)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("redistribution_policy" in item for item in result["failures"]))

    def test_restricted_source_route_cannot_claim_raw_redistribution(self) -> None:
        with DEFAULT_INVENTORY.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0])
        grid = next(row for row in rows if row["route_id"] == "grid_p5_beauty")
        grid["redistribution_policy"] = "summary_and_derived_tables"

        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "inventory.csv"
            with inventory.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            result = verify_inventory(inventory, DEFAULT_COVERAGE)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("restricted_source_license" in item for item in result["failures"]))

    def test_substituted_pass_report_is_rejected(self) -> None:
        with DEFAULT_INVENTORY.open(newline="", encoding="utf-8") as handle:
            row = next(row for row in csv.DictReader(handle) if row["route_id"] == "resot_instruments")
        report = json.loads((Path(__file__).resolve().parents[1] / row["conformance_evidence"]).read_text())
        report["artifact_id"] = "substituted_artifact"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            failure = _verify_c0_c5_report(row, path, DEFAULT_INVENTORY)

        self.assertIsNotNone(failure)
        self.assertIn("artifact ID", failure)


if __name__ == "__main__":
    unittest.main()
