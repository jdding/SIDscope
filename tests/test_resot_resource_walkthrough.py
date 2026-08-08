import json
import tempfile
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from tools.build_resot_resource_walkthrough import build_walkthrough


class ReSOTResourceWalkthroughTest(unittest.TestCase):
    def test_walkthrough_closes_intake_to_promotion_and_rejection(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = build_walkthrough(root)

        self.assertEqual(payload["status"], "pass")
        self.assertTrue(payload["decision"]["paper_counted"])
        self.assertEqual(
            [stage["stage"] for stage in payload["stages"]],
            ["discover", "normalize", "inspect", "promote", "reject-invalid"],
        )
        self.assertEqual(payload["diagnostic_snapshot"]["items"], 6250)

    def test_walkthrough_rejects_cross_route_stage_substitution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_path = root / "docs/reproducibility/resot_walkthrough_sources.json"
        value = json.loads(source_path.read_text(encoding="utf-8"))
        value["promotion"]["route_id"] = "different_route"
        with tempfile.TemporaryDirectory() as tmp:
            substituted = Path(tmp) / "sources.json"
            substituted.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "promotion stage"):
                build_walkthrough(root, substituted)

    def test_walkthrough_rejects_diagnostic_substitution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_path = root / "docs/reproducibility/resot_walkthrough_sources.json"
        value = json.loads(source_path.read_text(encoding="utf-8"))
        value["intake"]["d3_depth1_weighted_collab_recall"] = 0.999
        with tempfile.TemporaryDirectory() as tmp:
            substituted = Path(tmp) / "sources.json"
            substituted.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "d3_depth1_weighted_collab_recall"):
                build_walkthrough(root, substituted)

    def test_walkthrough_rejects_metadata_count_substitution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_path = root / "docs/reproducibility/resot_walkthrough_sources.json"
        value = json.loads(source_path.read_text(encoding="utf-8"))
        value["intake"]["metadata_rows"] = 999
        with tempfile.TemporaryDirectory() as tmp:
            substituted = Path(tmp) / "sources.json"
            substituted.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "metadata_rows"):
                build_walkthrough(root, substituted)

    def test_walkthrough_rejects_sid_count_substitution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_path = root / "docs/reproducibility/resot_walkthrough_sources.json"
        value = json.loads(source_path.read_text(encoding="utf-8"))
        value["intake"]["sid_rows"] = 999
        with tempfile.TemporaryDirectory() as tmp:
            substituted = Path(tmp) / "sources.json"
            substituted.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "intake item count"):
                build_walkthrough(root, substituted)

    def test_walkthrough_rejects_interaction_count_substitution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_path = root / "docs/reproducibility/resot_walkthrough_sources.json"
        value = json.loads(source_path.read_text(encoding="utf-8"))
        value["intake"]["interaction_rows"] = 999
        with tempfile.TemporaryDirectory() as tmp:
            substituted = Path(tmp) / "sources.json"
            substituted.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "interaction_rows"):
                build_walkthrough(root, substituted)

    def test_walkthrough_requires_packaged_public_evidence(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_path = root / "docs/reproducibility/resot_walkthrough_sources.json"
        value = json.loads(source_path.read_text(encoding="utf-8"))
        value["archive"]["public_record"] = "docs/reproducibility/missing_public_record.json"
        with tempfile.TemporaryDirectory() as tmp:
            substituted = Path(tmp) / "sources.json"
            substituted.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(FileNotFoundError, "public walkthrough evidence"):
                build_walkthrough(root, substituted)


if __name__ == "__main__":
    unittest.main()
