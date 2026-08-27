from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.llada_rec import (
    LLaDARecContractError,
    build_catalog,
    mask_token_id,
    model_vocabulary_tokens,
    resolve_model_tokens,
    run_deterministic_diffusion_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/llada_rec_diffusion_fixture/manifest.json"


class LLaDARecAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_position_disjoint_vocabulary_and_mask_token(self) -> None:
        sizes = [4, 4, 4, 4]
        self.assertEqual(model_vocabulary_tokens([0, 1, 0, 2], sizes), (1, 6, 9, 15))
        self.assertEqual(mask_token_id(sizes), 18)

    def test_catalog_resolution_preserves_ambiguity(self) -> None:
        catalog = build_catalog(self.manifest["catalog"], codebook_sizes=[4, 4, 4, 4])
        resolution = resolve_model_tokens([4, 8, 12, 16], catalog)
        self.assertEqual(resolution["resolution_status"], "ambiguous_semantic_id")
        self.assertEqual(resolution["resolved_item_ids"], ["3", "4"])

    def test_fixture_preserves_masked_parallel_state(self) -> None:
        trace = run_deterministic_diffusion_fixture(self.manifest)
        self.assertEqual(trace["decode_state_kind"], "masked_parallel_adaptive_unmasking")
        self.assertEqual(trace["initial_mask_state"], [18, 18, 18, 18])
        self.assertEqual(
            [row["normalized_item_id"] for row in trace["ranked_items"]], ["1", "2"]
        )
        self.assertEqual(trace["ranked_items"][0]["generation_order"], [2, 0, 3, 1])
        self.assertEqual(trace["ranked_items"][1]["generation_order"], [2, 3, 0, 1])
        self.assertEqual(trace["ambiguity"]["catalog_collision_count"], 1)
        self.assertEqual(trace["remasking"]["observed_transition_count"], 0)
        self.assertNotIn("prefix_depth", json.dumps(trace, sort_keys=True))

    def test_expected_remasking_failure_is_typed(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        expected = invalid["expected_failure"]
        transition = invalid["steps"][expected["refinement_step"] - 1]["transitions"][
            expected["transition_index"]
        ]
        transition["remasked_positions"] = expected["remasked_positions"]
        with self.assertRaises(LLaDARecContractError) as raised:
            run_deterministic_diffusion_fixture(invalid)
        self.assertEqual(raised.exception.label, "unsupported_remasking_transition")

    def test_position_vocabulary_violation_is_typed(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["steps"][0]["transitions"][0]["predicted_tokens"] = [1]
        invalid["steps"][0]["transitions"][0]["post_tokens"] = [18, 18, 1, 18]
        with self.assertRaises(LLaDARecContractError) as raised:
            run_deterministic_diffusion_fixture(invalid)
        self.assertEqual(raised.exception.label, "token_outside_position_vocabulary")

    def test_reselecting_filled_position_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["steps"][-1]["transitions"][0]["selected_positions"] = [0]
        invalid["steps"][-1]["transitions"][0]["predicted_tokens"] = [1]
        invalid["steps"][-1]["transitions"][0]["post_tokens"] = [1, 18, 9, 15]
        with self.assertRaises(LLaDARecContractError) as raised:
            run_deterministic_diffusion_fixture(invalid)
        self.assertEqual(raised.exception.label, "selected_position_not_masked")


if __name__ == "__main__":
    unittest.main()
