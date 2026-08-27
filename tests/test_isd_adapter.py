from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.isd import (
    ISDContractError,
    build_catalog,
    reciprocal_rank_fusion,
    run_deterministic_overlay_fixture,
    support_maps,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/isd_decoder_overlay_fixture/manifest.json"


class ISDAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_support_map_uses_best_ranked_shortlist_item(self) -> None:
        catalog = build_catalog(self.manifest["catalog"])
        supports = support_maps(["3", "1", "2"], catalog)
        self.assertEqual(supports[1], {(2,): 1, (1,): 2})
        self.assertEqual(supports[2][(1, 5)], 2)
        self.assertNotIn((2, 8), supports[2])

    def test_equal_weight_rrf(self) -> None:
        self.assertAlmostEqual(
            reciprocal_rank_fusion(1, 2, rrf_constant=60),
            1.0 / 61.0 + 1.0 / 62.0,
        )
        self.assertAlmostEqual(
            reciprocal_rank_fusion(3, None, rrf_constant=60), 1.0 / 63.0
        )

    def test_fixture_preserves_base_candidates_and_overlay_survival(self) -> None:
        trace = run_deterministic_overlay_fixture(self.manifest)
        self.assertEqual(
            trace["decode_state_kind"],
            "autoregressive_base_beam_with_item_support_overlay",
        )
        self.assertEqual(
            [step["survivor_ids"] for step in trace["base_decoder_steps"]],
            [["a1", "b1"], ["a2", "c2"], ["a3", "c3"]],
        )
        depth_two = trace["base_decoder_steps"][1]["base_candidates"]
        pruned = next(row for row in depth_two if row["candidate_id"] == "b2")
        self.assertFalse(pruned["survived"])
        self.assertEqual(pruned["failure_label"], "pruned_by_overlay")
        target = next(row for row in depth_two if row["candidate_id"] == "c2")
        self.assertEqual(target["best_supporting_item_rank"], 1)
        self.assertTrue(target["survived"])

    def test_final_rerank_preserves_collisions_without_inserting_items(self) -> None:
        trace = run_deterministic_overlay_fixture(self.manifest)
        self.assertEqual(
            [row["normalized_item_id"] for row in trace["ranked_items"]],
            ["1", "3", "5"],
        )
        self.assertNotIn("2", [row["normalized_item_id"] for row in trace["ranked_items"]])
        self.assertEqual(trace["ambiguity"]["catalog_collision_count"], 1)
        self.assertEqual(trace["ambiguity"]["ambiguous_generated_candidate_count"], 1)
        self.assertFalse(trace["invariants"]["provider_only_items_inserted"])

    def test_expected_provider_only_insertion_failure_is_typed(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        expected = invalid["expected_failure"]
        invalid["declared_final_item_ids"].append(expected["provider_only_item_id"])
        with self.assertRaises(ISDContractError) as raised:
            run_deterministic_overlay_fixture(invalid)
        self.assertEqual(raised.exception.label, expected["failure_label"])

    def test_unknown_parent_candidate_is_typed(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["base_decoder_steps"][1]["base_candidates"][0][
            "parent_candidate_id"
        ] = "pruned-parent"
        with self.assertRaises(ISDContractError) as raised:
            run_deterministic_overlay_fixture(invalid)
        self.assertEqual(raised.exception.label, "unknown_parent_candidate")


if __name__ == "__main__":
    unittest.main()
