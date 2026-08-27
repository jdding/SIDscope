from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.rpg import (
    RPGContractError,
    build_catalog,
    canonical_unordered_token_set,
    model_vocabulary_tokens,
    normalize_rpg_interactions,
    normalize_rpg_metadata,
    normalize_rpg_sem_ids,
    read_rpg_item_mapping,
    read_rpg_sem_ids,
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

    def test_official_cache_shape_roundtrip_preserves_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            processed = Path(temporary)
            mapping = {
                "user2id": {"[PAD]": 0, "u1": 1, "u2": 2},
                "item2id": {"[PAD]": 0, "a": 1, "b": 2, "c": 3},
                "id2user": ["[PAD]", "u1", "u2"],
                "id2item": ["[PAD]", "a", "b", "c"],
            }
            sem_ids = {"a": [0, 1, 2], "b": [0, 1, 2], "c": [3, 2, 1]}
            sequences = {"u1": ["a", "b", "c"], "u2": ["c", "a", "b"]}
            mapping_path = processed / "id_mapping.json"
            sem_ids_path = processed / "cache.sem_ids"
            sequences_path = processed / "all_item_seqs.json"
            mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
            sem_ids_path.write_text(json.dumps(sem_ids), encoding="utf-8")
            sequences_path.write_text(json.dumps(sequences), encoding="utf-8")

            identities = read_rpg_item_mapping(mapping_path)
            self.assertEqual(
                [(row.source_item_id, row.normalized_item_id, row.rpg_item_node_id) for row in identities],
                [("a", 0, 1), ("b", 1, 2), ("c", 2, 3)],
            )
            cache = read_rpg_sem_ids(
                sem_ids_path,
                expected_source_items=(row.source_item_id for row in identities),
                n_codebooks=3,
                codebook_size=4,
            )
            self.assertEqual(cache["a"], cache["b"])

            sid = normalize_rpg_sem_ids(
                sem_ids_path,
                mapping_path,
                method="rpg_opq_official_code_derived",
                dataset="beauty",
                n_codebooks=3,
                codebook_size=4,
            )
            metadata = normalize_rpg_metadata(mapping_path, dataset="beauty", category="Beauty")
            interactions = normalize_rpg_interactions(
                sequences_path, mapping_path, dataset="beauty"
            )
            self.assertEqual(sid["item_id"].tolist(), [0, 1, 2])
            self.assertEqual(sid.iloc[0]["unordered_model_vocabulary_tokens"], [1, 6, 11])
            self.assertEqual(metadata["rpg_item_node_id"].tolist(), [1, 2, 3])
            self.assertEqual(interactions["split"].value_counts().to_dict(), {
                "train": 2,
                "validation_target": 2,
                "test_target": 2,
            })

    def test_official_cache_shape_rejects_catalog_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cache.sem_ids"
            path.write_text(json.dumps({"a": [0, 1], "extra": [1, 0]}), encoding="utf-8")
            with self.assertRaises(RPGContractError) as raised:
                read_rpg_sem_ids(
                    path,
                    expected_source_items=["a", "b"],
                    n_codebooks=2,
                    codebook_size=4,
                )
            self.assertEqual(raised.exception.label, "cache_catalog_mismatch")

    def test_official_cache_shape_rejects_fractional_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cache.sem_ids"
            path.write_text(json.dumps({"a": [0, 1.5]}), encoding="utf-8")
            with self.assertRaises(RPGContractError) as raised:
                read_rpg_sem_ids(
                    path,
                    expected_source_items=["a"],
                    n_codebooks=2,
                    codebook_size=4,
                )
            self.assertEqual(raised.exception.label, "semantic_code_not_integer")


if __name__ == "__main__":
    unittest.main()
