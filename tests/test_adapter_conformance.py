import json
import hashlib
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.conformance import run_conformance


class AdapterConformanceTest(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _fixture(self, root: Path, *, broken_sid: bool = False) -> Path:
        data = root / "data"
        data.mkdir()
        sid = pd.DataFrame(
            {
                "item_id": [1, 2, 3],
                "sid": ["0-0", "broken" if broken_sid else "0-1", "1-0"],
                "method": ["fixture"] * 3,
                "dataset": ["toy"] * 3,
                "sid_level_0": [0, 0, 1],
                "sid_level_1": [0, 1, 0],
            }
        )
        metadata = pd.DataFrame({"item_id": [1, 2, 3], "category": ["a", "a", "b"]})
        interactions = pd.DataFrame({"user_id": [1, 1, 2, 2], "item_id": [1, 2, 1, 3]})
        sid.to_csv(data / "sid.csv", index=False)
        metadata.to_csv(data / "metadata.csv", index=False)
        interactions.to_csv(data / "interactions.csv", index=False)
        (root / "evidence.md").write_text("fixture\n", encoding="utf-8")

        manifest = {
            "schema_version": "sidscope.adapter_manifest.v1",
            "artifact_id": "toy_fixture",
            "paper_label": "Toy fixture",
            "method_family": "fixture",
            "configuration": "three-row unit-test fixture",
            "source": {
                "url": "https://example.org/toy",
                "revision": "fixture-v1",
                "license_status": "licensed",
                "license_identifier": "MIT",
                "derivation": "control",
                "artifact_name": "data/sid.csv",
                "redistribution_policy": "summary_and_derived_tables",
            },
            "dataset": {"name": "toy", "expected_items": 3, "sid_depth": 2},
            "inputs": {
                "sid_assignments": "data/sid.csv",
                "item_metadata": "data/metadata.csv",
                "interactions": "data/interactions.csv",
            },
            "input_sha256": {
                "sid_assignments": self._sha256(data / "sid.csv"),
                "item_metadata": self._sha256(data / "metadata.csv"),
                "interactions": self._sha256(data / "interactions.csv"),
            },
            "metric_smoke": {"max_metric_items": 10, "top_k": 1, "max_pair_events": 100},
            "reproduction": {
                "command": ["python3", "fixture.py"],
                "runtime_class": "cpu_seconds",
                "source_evidence": ["evidence.md"],
            },
            "promotion": {
                "route_id": "toy_fixture",
                "evidence_role": "control",
                "paper_counted": False,
                "conformance_status": "fixture",
                "conformance_evidence": "evidence.md",
            },
        }
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_complete_control_fixture_passes_all_levels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            report = run_conformance(manifest, root=root)

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual([check["level"] for check in report["checks"]], ["C0", "C1", "C2", "C3", "C4", "C5"])
        c3 = next(check for check in report["checks"] if check["level"] == "C3")
        self.assertEqual(c3["details"]["metric_smoke_summary"][0]["d1_level_count"], 2)

    def test_sid_level_mismatch_fails_c1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root, broken_sid=True)
            report = run_conformance(manifest, root=root)

        self.assertEqual(report["status"], "fail")
        self.assertIn("C1", report["failed_levels"])

    def test_paper_counted_control_fails_c5(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["promotion"]["paper_counted"] = True
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C5", report["failed_levels"])

    def test_missing_input_hash_fails_c4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            del value["input_sha256"]["interactions"]
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C4", report["failed_levels"])

    def test_source_evidence_cannot_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["reproduction"]["source_evidence"] = ["../outside.md"]
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C4", report["failed_levels"])

    def test_input_path_aliases_do_not_count_as_distinct_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["inputs"]["item_metadata"] = "data/./sid.csv"
            value["input_sha256"]["item_metadata"] = value["input_sha256"]["sid_assignments"]
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C1", report["failed_levels"])

    def test_partial_coverage_must_be_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["allow_partial_coverage"] = "false"
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C0", report["failed_levels"])

    def test_wrong_dataset_interactions_do_not_pass_join_or_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            interactions_path = root / "data/interactions.csv"
            interactions = pd.read_csv(interactions_path)
            interactions["dataset"] = "other"
            interactions.to_csv(interactions_path, index=False)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["input_sha256"]["interactions"] = self._sha256(interactions_path)
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C2", report["failed_levels"])
        self.assertIn("C3", report["failed_levels"])

    def test_paper_dataset_label_may_differ_from_normalized_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["dataset"]["name"] = "Toy Dataset"
            value["dataset"]["normalized_name"] = "toy"
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertEqual(report["status"], "pass", report)

    def test_resot_inventory_configuration_mismatch_fails_c5(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_manifest = root / "docs/reproducibility/conformance/resot_instruments_manifest.json"
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            value = json.loads(source_manifest.read_text(encoding="utf-8"))
            value["configuration"] = "different tokenizer configuration"
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C5", report["failed_levels"])

    def test_resot_inventory_evidence_role_mismatch_fails_c5(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_manifest = root / "docs/reproducibility/conformance/resot_instruments_manifest.json"
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            value = json.loads(source_manifest.read_text(encoding="utf-8"))
            value["promotion"]["evidence_role"] = "source_traced_named_route"
            manifest.write_text(json.dumps(value), encoding="utf-8")
            report = run_conformance(manifest, root=root)

        self.assertIn("C5", report["failed_levels"])

    def test_released_resot_route_passes_and_public_fixture_fails_only_c1(self) -> None:
        root = Path(__file__).resolve().parents[1]
        resot_manifest = root / "docs/reproducibility/conformance/resot_instruments_manifest.json"
        resot_manifest_value = json.loads(resot_manifest.read_text(encoding="utf-8"))
        resot_inputs = [root / path for path in resot_manifest_value["inputs"].values()]
        if not all(path.exists() for path in resot_inputs):
            self.skipTest("local normalized ReSOT inputs are not shipped in the public package")
        resot = run_conformance(
            resot_manifest,
            root=root,
        )
        broken = run_conformance(
            root / "examples/conformance_failure_fixture/manifest.json",
            root=root,
        )

        self.assertEqual(resot["status"], "pass", resot)
        self.assertEqual(resot["failed_levels"], [])
        self.assertEqual(broken["status"], "fail", broken)
        self.assertEqual(broken["failed_levels"], ["C1"])


if __name__ == "__main__":
    unittest.main()
