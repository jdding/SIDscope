from __future__ import annotations

import copy
import json
from argparse import Namespace
import tempfile
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
from tools.run_llada_rec_resumable_tokenizer import bindings, validate_state
from tools.run_llada_rec_resumable_training import (
    load_semantic_ids,
    validate_resume_payload,
)
from tools.finalize_llada_rec_prepared_contract import (
    canonical_hash as prepared_hash,
    finalize as finalize_prepared,
    sha256_file as prepared_file_hash,
)
from tools.export_llada_rec_trained_trace import validate_inputs as validate_trained_inputs
from tools.verify_llada_rec_trained_trace_bundle import (
    VerificationFailure,
    verify as verify_trained_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/llada_rec_diffusion_fixture/manifest.json"
TRAINED_FIXTURE = ROOT / "examples/llada_rec_trained_trace_fixture"


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

    def test_tokenizer_resume_is_bound_and_contiguous(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.json"
            embeddings = root / "embeddings.bin"
            source = root / "source.json"
            runtime.write_text("runtime", encoding="utf-8")
            embeddings.write_bytes(b"embeddings")
            source.write_text("source", encoding="utf-8")
            expected = bindings(Namespace(
                runtime_manifest=runtime,
                sentence_embeddings=embeddings,
                source_manifest=source,
                domain="amazon_vg",
                seed=2024,
                expected_catalog_rows=3,
                learning_rate=0.001,
                weight_decay=1e-4,
                batch_size=2,
                target_epochs=2,
            ))
            state = {
                "schema": "sidscope.llada_rec_tokenizer_state.v1",
                "bindings": expected,
                "completed_epochs": 2,
                "epoch_records": [{"epoch": 1}, {"epoch": 2}],
                "model": {}, "optimizer": {}, "rng_state": {},
            }
            validate_state(state, expected)
            state["epoch_records"][1]["epoch"] = 3
            with self.assertRaisesRegex(ValueError, "not contiguous"):
                validate_state(state, expected)

    def test_formal_semantic_ids_require_exact_catalog_and_4x256_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.json"
            semantic = root / "semantic.json"
            runtime.write_text(json.dumps({
                "schema": "genrec_dormant.diffgrm_private_runtime.v1",
                "catalog": [
                    {"normalized_item_id": "n1", "runtime_item_key": "p1"},
                    {"normalized_item_id": "n2", "runtime_item_key": "p2"},
                ],
            }), encoding="utf-8")
            semantic.write_text(json.dumps({
                "n1": [0, 1, 2, 3],
                "n2": [0, 1, 2, 3],
            }), encoding="utf-8")
            mapped, summary = load_semantic_ids(
                runtime, semantic, expected_catalog_rows=2
            )
            self.assertEqual(mapped["p1"], [0, 1, 2, 3])
            self.assertEqual(summary["unique_semantic_ids"], 1)
            self.assertEqual(summary["collision_excess"], 1)
            invalid = json.loads(semantic.read_text(encoding="utf-8"))
            invalid["n2"] = [0, 1, 2, 256]
            semantic.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "4x256"):
                load_semantic_ids(runtime, semantic, expected_catalog_rows=2)

    def test_generator_resume_requires_contiguous_step_ledger(self) -> None:
        bindings_value = {"target_steps": 10}
        state = {
            "schema": "sidscope.llada_rec_generator_state.v1",
            "bindings": bindings_value,
            "completed_steps": 4,
            "completed_epochs": 2,
            "epoch_records": [
                {"epoch": 1, "completed_steps": 2},
                {"epoch": 2, "completed_steps": 4},
            ],
            "model": {},
            "optimizer": {},
            "scheduler": {},
            "rng_state": {},
        }
        validate_resume_payload(state, bindings_value, verify_model_hash=False)
        state["epoch_records"][1]["completed_steps"] = 2
        with self.assertRaisesRegex(ValueError, "not increasing"):
            validate_resume_payload(state, bindings_value, verify_model_hash=False)

    def test_formal_prepared_contract_uses_official_position_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_path = root / "prepared.json"
            selection_path = root / "episode_selection_1pb.json"
            semantic_path = root / "semantic.json"
            tokenizer_path = root / "tokenizer.json"
            output = root / "output"
            base = {
                "schema": "sidscope.diffgrm_prepared_dataset.v1",
                "dataset": "fixture",
                "category": "vg",
                "profile": "frozen",
                "split_sha256": {"train": "a", "validation": "b", "test": "c"},
                "episode_index": [{
                    "episode_id": "e1",
                    "split": "test",
                    "target_normalized_item_id": "n1",
                    "catalog_reachable": True,
                }],
                "catalog": [
                    {"normalized_item_id": "n1"},
                    {"normalized_item_id": "n2"},
                ],
            }
            base_path.write_text(json.dumps(base), encoding="utf-8")
            semantic_path.write_text(json.dumps({
                "n1": [0, 1, 2, 3], "n2": [4, 5, 6, 7]
            }), encoding="utf-8")
            tokenizer_path.write_text(json.dumps({
                "schema": "sidscope.llada_rec_tokenizer_training.v1",
                "status": "pass",
                "semantic_ids_sha256": prepared_file_hash(semantic_path),
            }), encoding="utf-8")
            selection_path.write_text(json.dumps({
                "schema": "sidscope.diffgrm_episode_selection.v1",
                "prepared_dataset_contract_sha256": prepared_hash(base),
                "selection_policy": "explicit",
                "episodes": [{
                    "selection_ordinal": 1,
                    "episode_id": "e1",
                    "split": "test",
                    "target_normalized_item_id": "n1",
                    "gap_bucket": "short",
                    "generator_input_contains_bucket_or_label": False,
                }],
            }), encoding="utf-8")
            result = finalize_prepared(Namespace(
                base_prepared=base_path,
                base_selection=[selection_path],
                tokenizer_training_manifest=tokenizer_path,
                semantic_ids=semantic_path,
                output_dir=output,
            ))
            self.assertEqual(result["status"], "pass")
            prepared = json.loads((output / "prepared_dataset.json").read_text())
            self.assertEqual(
                prepared["catalog"][0]["model_vocabulary_tokens"],
                [1, 258, 515, 772],
            )
            self.assertEqual(prepared["sid_contract"]["mask_token"], 1026)

    def test_trained_selection_binding_fails_closed(self) -> None:
        prepared = {
            "schema": "sidscope.llada_rec_prepared_dataset.v1",
            "source_revision": "83dbcd6061da9266adcd8f68b16d1de7cc2612f3",
            "catalog": [{"normalized_item_id": "n1"}],
            "episode_index": [{
                "episode_id": "e1",
                "target_normalized_item_id": "n1",
            }],
        }
        runtime = {
            "schema": "genrec_dormant.diffgrm_private_runtime.v1",
            "splits": {"test": [{"episode_id": "e1", "item_seq": ["p0", "p1"]}]},
        }
        selection = {
            "schema": "sidscope.llada_rec_episode_selection.v1",
            "prepared_dataset_contract_sha256": "0" * 64,
            "first_n_fallback_allowed": False,
            "episodes": [],
        }
        with self.assertRaisesRegex(ValueError, "prepared binding mismatch"):
            validate_trained_inputs(prepared, selection, runtime, {"n1": [0, 1, 2, 3]})

    def test_trained_trace_fixture_and_typed_failures(self) -> None:
        arguments = {
            "prepared_path": TRAINED_FIXTURE / "prepared_dataset.json",
            "selection_path": TRAINED_FIXTURE / "episode_selection.json",
            "bundle_path": TRAINED_FIXTURE / "trained_trace.json",
            "training_manifest_path": TRAINED_FIXTURE / "training_manifest.json",
        }
        result = verify_trained_bundle(**arguments)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["episode_count"], 1)
        for label in ("unknown_parent_beam", "prepared_binding_mismatch"):
            with self.assertRaises(VerificationFailure) as raised:
                verify_trained_bundle(
                    **arguments,
                    expected_failure_mutation=label,
                )
            self.assertEqual(raised.exception.label, label)


if __name__ == "__main__":
    unittest.main()
