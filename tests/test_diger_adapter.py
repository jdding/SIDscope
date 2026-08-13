import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from sidinspector.adapters.diger import (
    normalize_diger_codes,
    normalize_diger_interactions,
    normalize_diger_metadata,
    read_diger_emb_map,
)
from tools.run_v1_gate17_diger_intake import (
    DATASET_PROFILES,
    _resolve_item_count,
    parse_args,
)


class DIGERAdapterTest(unittest.TestCase):
    def _write_emb_map(self, root: Path) -> Path:
        path = root / "emb_map.json"
        path.write_text(json.dumps({"[PAD]": 0, "item_0": 1, "item_1": 2, "item_2": 3}), encoding="utf-8")
        return path

    def test_reads_emb_map_with_zero_based_item_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_emb_map(Path(tmp))
            out = read_diger_emb_map(path)

        self.assertEqual(list(out["item_id"]), [0, 1, 2])
        self.assertEqual(list(out["source_item_id"]), ["item_0", "item_1", "item_2"])
        self.assertEqual(list(out["diger_token_id"]), [1, 2, 3])

    def test_normalizes_codes_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emb_map = self._write_emb_map(root)
            codes = np.array([[1, 2, 3], [1, 2, 4], [5, 6, 7]], dtype=np.int64)
            sid_rows = normalize_diger_codes(codes, emb_map, method="diger_rqvae", dataset="Beauty")
            metadata = normalize_diger_metadata(emb_map, dataset="Beauty")

        self.assertEqual(list(sid_rows["sid"]), ["1-2-3", "1-2-4", "5-6-7"])
        self.assertEqual(list(sid_rows["sid_level_0"]), [1, 1, 5])
        self.assertEqual(list(metadata["category"]), ["unknown", "unknown", "unknown"])

    def test_reconstructs_longest_user_sequence_from_prefix_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emb_map = self._write_emb_map(root)
            train = root / "train.jsonl"
            test = root / "test.jsonl"
            train.write_text(
                "\n".join(
                    [
                        json.dumps({"user_id": "0", "target_id": "item_1", "inter_history": ["item_0"]}),
                        json.dumps({"user_id": "1", "target_id": "item_2", "inter_history": ["item_1"]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            test.write_text(
                json.dumps({"user_id": "0", "target_id": "item_2", "inter_history": ["item_0", "item_1"]}) + "\n",
                encoding="utf-8",
            )

            out = normalize_diger_interactions([train, test], emb_map, dataset="Beauty")

        user0 = out[out["user_id"] == 0].sort_values("position")
        self.assertEqual(list(user0["item_id"]), [0, 1, 2])
        self.assertEqual(len(out[out["user_id"] == 1]), 2)

    def test_rejects_interaction_items_missing_from_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emb_map = self._write_emb_map(root)
            train = root / "train.jsonl"
            train.write_text(
                json.dumps(
                    {
                        "user_id": "0",
                        "target_id": "item_1",
                        "inter_history": ["unknown_item", "item_0"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "absent from DIGER emb_map"):
                normalize_diger_interactions([train], emb_map, dataset="Yelp")

    def test_yelp_profile_uses_map_and_embedding_count_without_stats_file(self):
        profile = DATASET_PROFILES["yelp"]
        self.assertIsNone(profile["stats_file"])
        item_count, evidence = _resolve_item_count(
            item_map_rows=20_033,
            embedding_rows=20_033,
            stats_path=None,
        )
        self.assertEqual(item_count, 20_033)
        self.assertEqual(evidence["source"], "released_emb_map_and_embedding_shape")

    def test_item_count_rejects_map_embedding_mismatch(self):
        with self.assertRaisesRegex(ValueError, "map has 3 items"):
            _resolve_item_count(item_map_rows=3, embedding_rows=2, stats_path=None)

    def test_dataset_key_preserves_beauty_default_and_accepts_yelp(self):
        self.assertEqual(parse_args([]).dataset_key, "beauty")
        self.assertEqual(parse_args(["--dataset-key", "yelp"]).dataset_key, "yelp")


if __name__ == "__main__":
    unittest.main()
