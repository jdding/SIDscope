import json
import tempfile
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.resot import (
    normalize_resot_index,
    normalize_resot_interactions,
    normalize_resot_metadata,
    read_resot_item2id,
)


class ReSOTAdapterTest(unittest.TestCase):
    def test_reads_item2id_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "item2id"
            path.write_text("ASIN0\t0\nASIN1\t1\n", encoding="utf-8")
            out = read_resot_item2id(path)

        self.assertEqual(list(out["source_item_id"]), ["ASIN0", "ASIN1"])
        self.assertEqual(list(out["internal_item_id"]), [0, 1])

    def test_normalizes_index_with_stable_item_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index_path = root / "index.json"
            item2id_path = root / "item2id"
            index_path.write_text(
                json.dumps({"0": ["<a_1>", "<b_2>"], "1": ["<a_1>", "<b_3>"]}),
                encoding="utf-8",
            )
            item2id_path.write_text("ASIN0\t0\nASIN1\t1\n", encoding="utf-8")
            out = normalize_resot_index(index_path, item2id_path, method="resot_text", dataset="toy")

        self.assertEqual(list(out["item_id"]), [0, 1])
        self.assertEqual(list(out["source_item_id"]), ["ASIN0", "ASIN1"])
        self.assertEqual(list(out["internal_item_id"]), [0, 1])
        self.assertEqual(list(out["sid_level_0"]), [1, 1])
        self.assertEqual(list(out["sid_level_1"]), [2, 3])
        self.assertEqual(list(out["sid"]), ["1-2", "1-3"])

    def test_normalizes_metadata_and_interactions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item2id_path = root / "item2id"
            item_path = root / "item.json"
            inter_path = root / "inter.json"
            item2id_path.write_text("ASIN0\t0\nASIN1\t1\n", encoding="utf-8")
            item_path.write_text(
                json.dumps({"0": {"title": "T0", "brand": "B", "categories": ["x", "y"], "description": ["d0"]}}),
                encoding="utf-8",
            )
            inter_path.write_text(json.dumps({"2": [0, 1]}), encoding="utf-8")
            metadata = normalize_resot_metadata(item_path, item2id_path, dataset="toy")
            interactions = normalize_resot_interactions(inter_path, item2id_path, dataset="toy")

        self.assertEqual(metadata.loc[0, "item_id"], 0)
        self.assertEqual(metadata.loc[0, "source_item_id"], "ASIN0")
        self.assertEqual(metadata.loc[0, "category"], "x > y")
        self.assertEqual(metadata.loc[0, "text"], "d0")
        self.assertEqual(list(interactions["item_id"]), [0, 1])
        self.assertEqual(list(interactions["source_item_id"]), ["ASIN0", "ASIN1"])
        self.assertEqual(list(interactions["position"]), [0, 1])
        self.assertNotIn("split", interactions.columns)


if __name__ == "__main__":
    unittest.main()
