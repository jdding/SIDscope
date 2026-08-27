from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.rpg import (
    RPGContractError,
    build_catalog,
    canonical_unordered_token_set,
    model_vocabulary_tokens,
    run_deterministic_graph_fixture,
    token_set_resolution,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/rpg_generator_fixture/manifest.json"


class RPGAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_vocabulary_tokens_preserve_disjoint_codebook_identity(self) -> None:
        self.assertEqual(model_vocabulary_tokens([0, 1, 0], 4), (1, 6, 9))
        self.assertEqual(
            canonical_unordered_token_set([9, 1, 6], n_codebooks=3, codebook_size=4),
            (1, 6, 9),
        )

    def test_invalid_set_reports_duplicate_codebook_partition(self) -> None:
        with self.assertRaises(RPGContractError) as raised:
            canonical_unordered_token_set([1, 2, 9], n_codebooks=3, codebook_size=4)
        self.assertEqual(raised.exception.label, "duplicate_codebook_partition")

    def test_duplicate_token_set_keeps_ambiguous_item_nodes(self) -> None:
        config = self.manifest["configuration"]
        catalog = build_catalog(
            self.manifest["catalog"],
            n_codebooks=config["n_codebooks"],
            codebook_size=config["codebook_size"],
        )
        result = token_set_resolution(
            [9, 5, 1],
            catalog,
            n_codebooks=config["n_codebooks"],
            codebook_size=config["codebook_size"],
        )
        self.assertEqual(result["resolution_status"], "ambiguous_item_nodes")
        self.assertEqual(result["resolved_item_ids"], ["1", "4"])

    def test_cpu_fixture_preserves_parallel_graph_state_and_ranked_items(self) -> None:
        result = run_deterministic_graph_fixture(self.manifest)
        self.assertEqual(result["decode_state_kind"], "unordered_token_set_graph_propagation")
        self.assertEqual([row["normalized_item_id"] for row in result["ranked_items"]], ["2", "1"])
        self.assertEqual(result["ranked_items"][0]["rank"], 1)
        self.assertTrue(result["validity"]["all_ranked_items_graph_valid"])
        self.assertEqual(result["ambiguity"]["token_set_collision_count"], 1)
        self.assertNotIn("prefix_depth", json.dumps(result))

    def test_graph_requires_self_edges_for_monotone_frontier(self) -> None:
        self.manifest["graph"]["1"] = [2, 4]
        with self.assertRaises(RPGContractError) as raised:
            run_deterministic_graph_fixture(self.manifest)
        self.assertEqual(raised.exception.label, "missing_self_edge")


if __name__ == "__main__":
    unittest.main()
