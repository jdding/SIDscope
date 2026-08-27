from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.dact import (
    DACTContractError,
    build_catalog,
    model_vocabulary_tokens,
    resolve_model_tokens,
    run_deterministic_autoregressive_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/dact_tiger_autoregressive_fixture/manifest.json"


class DACTAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_released_position_disjoint_vocabulary(self) -> None:
        self.assertEqual(model_vocabulary_tokens([20, 6, 39, 0]), (21, 263, 552, 769))
        with self.assertRaises(DACTContractError) as raised:
            model_vocabulary_tokens([256, 0, 0, 0])
        self.assertEqual(raised.exception.label, "code_out_of_range")

    def test_resolution_preserves_full_sid_collision(self) -> None:
        catalog = build_catalog(self.manifest["catalog"])
        resolution = resolve_model_tokens([3, 260, 517, 774], catalog)
        self.assertEqual(resolution["resolution_status"], "ambiguous_semantic_id")
        self.assertEqual(resolution["resolved_item_ids"], ["3", "4"])

    def test_fixture_preserves_ordered_prefixes_and_beam_parents(self) -> None:
        trace = run_deterministic_autoregressive_fixture(self.manifest)
        self.assertEqual(trace["decode_state_kind"], "ordered_autoregressive_prefix_beam")
        self.assertEqual([step["prefix_depth"] for step in trace["steps"]], [1, 2, 3, 4])
        self.assertEqual(
            trace["steps"][-1]["transitions"][0]["parent_beam_id"], "b1-3"
        )
        self.assertEqual(
            trace["steps"][-1]["transitions"][0]["prefix_tokens"],
            [1, 258, 515, 772],
        )
        self.assertEqual(
            [row["normalized_item_id"] for row in trace["ranked_items"]],
            ["1", "2", "3", "4"],
        )
        self.assertEqual(trace["ambiguity"]["catalog_collision_count"], 1)
        self.assertTrue(trace["target_outcome"]["target_item_uniquely_hit"])

    def test_expected_position_vocabulary_failure_is_typed(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        expected = invalid["expected_failure"]
        transition = invalid["steps"][int(expected["prefix_depth"]) - 1]["transitions"][
            int(expected["transition_index"])
        ]
        transition["appended_token"] = int(expected["invalid_appended_token"])
        with self.assertRaises(DACTContractError) as raised:
            run_deterministic_autoregressive_fixture(invalid)
        self.assertEqual(raised.exception.label, expected["failure_label"])

    def test_prefix_parent_mismatch_is_typed(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["steps"][1]["transitions"][0]["prefix_tokens"] = [1, 259]
        with self.assertRaises(DACTContractError) as raised:
            run_deterministic_autoregressive_fixture(invalid)
        self.assertEqual(raised.exception.label, "prefix_parent_mismatch")


if __name__ == "__main__":
    unittest.main()
