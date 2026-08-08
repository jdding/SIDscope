from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd
import torch

from sidinspector.d7_trace import label_traces
from tools.run_v1_gate12b_sequence_generator_anchor import SequenceSIDGenerator, build_sid_encoding
from tools.run_v1_gate20_d7_trained_beam import build_trie_index, trie_constrained_beam_decode
from tools.run_v1_gate20_d7_trained_beam import (
    bootstrap_user_rate,
    analyze_traces,
    determine_gate_status,
    effective_seed,
    evaluate_replicated_promotion,
    split_g20_events,
)


class Gate20TrainedBeamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sid = pd.DataFrame(
            {
                "item_id": [1, 2, 3, 4, 5],
                "sid_level_0": [0, 0, 0, 1, 1],
                "sid_level_1": [0, 1, 1, 0, 1],
                "sid_level_2": [0, 0, 0, 0, 0],
            }
        )
        self.encoding = build_sid_encoding(self.sid)
        self.trie = build_trie_index(self.encoding)
        self.model = SequenceSIDGenerator(
            num_items=5,
            level_vocab_sizes=self.encoding.level_vocab_sizes,
            embedding_dim=8,
            hidden_dim=12,
            decoder_dim=12,
            dropout=0.0,
        )
        for parameter in self.model.parameters():
            torch.nn.init.constant_(parameter, 0.0)

    def test_trie_contains_only_catalog_paths_and_preserves_aliases(self) -> None:
        self.assertEqual(len(self.trie.code_to_items), 4)
        aliased = [items for items in self.trie.code_to_items.values() if len(items) > 1]
        self.assertEqual(aliased, [(2, 3)])

    def test_constrained_beam_is_valid_unique_and_deterministic(self) -> None:
        history = torch.as_tensor([[1, 2]], dtype=torch.long)
        first = trie_constrained_beam_decode(
            model=self.model,
            history=history,
            trie=self.trie,
            depth=3,
            beam_width=4,
        )
        second = trie_constrained_beam_decode(
            model=self.model,
            history=history,
            trie=self.trie,
            depth=3,
            beam_width=4,
        )
        self.assertEqual([beam.path for beam in first], [beam.path for beam in second])
        self.assertEqual(len(first), 4)
        self.assertEqual(len({beam.path for beam in first}), 4)
        self.assertTrue(all(beam.path in self.trie.code_to_items for beam in first))
        self.assertTrue(all(len(beam.step_logprobs) == 3 for beam in first))
        self.assertTrue(all(len(beam.prefix_entropies) == 3 for beam in first))
        self.assertTrue(all(abs(beam.score - sum(beam.step_logprobs)) < 1e-8 for beam in first))

    def test_beam_rows_expose_real_ambiguous_paths_without_invalid_paths(self) -> None:
        history = torch.as_tensor([[1, 2]], dtype=torch.long)
        beams = trie_constrained_beam_decode(
            model=self.model,
            history=history,
            trie=self.trie,
            depth=3,
            beam_width=4,
        )
        traces = pd.DataFrame(
            [
                {
                    "trace_id": "trace",
                    "user_id": "user",
                    "rank": rank,
                    "sid_path": "-".join(self.trie.code_to_sid_path[beam.path]),
                }
                for rank, beam in enumerate(beams, 1)
            ]
        )
        labels = label_traces(self.sid, traces)
        self.assertEqual(int((labels["primary_failure"] == "invalid_path").sum()), 0)
        self.assertEqual(int((labels["primary_failure"] == "ambiguous_path").sum()), 1)

    def test_explicit_split_uses_test_targets_and_train_plus_validation_history(self) -> None:
        interactions = pd.DataFrame(
            {
                "user_id": [1, 1, 1, 2, 2, 2],
                "item_id": [1, 2, 3, 2, 4, 5],
                "timestamp": [1, 2, 3, 1, 2, 3],
                "split": ["train", "validation", "test"] * 2,
            }
        )
        train, history, targets, protocol = split_g20_events(interactions)
        self.assertEqual(set(train["split"]), {"train"})
        self.assertEqual(set(history["split"]), {"train", "validation"})
        self.assertEqual(set(targets["split"]), {"test"})
        self.assertEqual(protocol, "test_targets_train_plus_validation_history")
        self.assertTrue(history["timestamp"].max() < targets["timestamp"].min())

    def test_effective_seed_is_the_recorded_training_seed(self) -> None:
        self.assertEqual(effective_seed(20260808, 9, 1), 20261718)

    def test_primary_requires_both_500_targets_and_10000_rows(self) -> None:
        status, promotion = determine_gate_status(
            stage="primary",
            accounting_pass=True,
            target_traces=499,
            trace_rows=24950,
            beam_width=50,
            structural_nonzero=True,
            outcome_variation=True,
        )
        self.assertEqual(status, "FAIL_G20_PRIMARY_INCOMPLETE")
        self.assertEqual(promotion, "BOUNDARY_G20_NOT_FAILURE_RICH")
        status, promotion = determine_gate_status(
            stage="primary",
            accounting_pass=True,
            target_traces=500,
            trace_rows=25000,
            beam_width=50,
            structural_nonzero=False,
            outcome_variation=False,
        )
        self.assertEqual(status, "PASS_G20_PRIMARY_RUN_COMPLETE")
        self.assertEqual(promotion, "BOUNDARY_G20_NOT_FAILURE_RICH")

    def test_paper_promotion_requires_two_folds_with_a_common_structural_family(self) -> None:
        def result(fold: int, seed: int, family: str) -> dict:
            return {
                "status": "PASS_G20_PRIMARY_RUN_COMPLETE",
                "configuration": {"fold": fold, "effective_seed": seed},
                "analysis": {"failure_flag_target_counts": {family: 4}},
                "target_outcome_variation": True,
            }

        one = evaluate_replicated_promotion([result(0, 10, "ambiguous_path")])
        self.assertEqual(one["status"], "BOUNDARY_G20_NOT_REPRODUCIBLE")
        passed = evaluate_replicated_promotion(
            [result(0, 10, "ambiguous_path"), result(1, 11, "ambiguous_path")]
        )
        self.assertEqual(passed["status"], "PASS_G20_FAILURE_RICH_PAPER_PROMOTION")
        mismatched = evaluate_replicated_promotion(
            [result(0, 10, "ambiguous_path"), result(1, 11, "prefix_loop")]
        )
        self.assertEqual(mismatched["status"], "BOUNDARY_G20_NOT_REPRODUCIBLE")

    def test_bootstrap_reports_user_cluster_and_target_counts(self) -> None:
        frame = pd.DataFrame({"user_id": ["a", "a", "b"], "hit": [1, 0, 1]})
        result = bootstrap_user_rate(frame, value_col="hit", samples=50, seed=7)
        self.assertEqual(result["users"], 2)
        self.assertEqual(result["targets"], 3)
        self.assertAlmostEqual(result["rate"], 2 / 3)

    def test_analysis_preserves_overlapping_flags_and_outcome_strata(self) -> None:
        traces = pd.DataFrame(
            [
                {
                    "trace_id": "t1",
                    "user_id": "u1",
                    "rank": rank,
                    "sid_path": "0-1-0",
                    "resolved_item_ids_exporter": "2;3",
                    "beam_width": 2,
                    "decoding_mode": "trie_constrained_beam",
                }
                for rank in (1, 2)
            ]
        )
        outcomes = pd.DataFrame(
            [
                {
                    "trace_id": "t1",
                    "user_id": "u1",
                    "target_missed": True,
                    "target_ambiguous": False,
                    "target_path_survived": False,
                    "target_item_uniquely_hit": False,
                }
            ]
        )
        _, target_analysis, overlap, strata, analysis = analyze_traces(
            sid=self.sid,
            traces=traces,
            outcomes=outcomes,
            bootstrap_samples=20,
            seed=3,
        )
        self.assertEqual(int(target_analysis.loc[0, "ambiguous_path"]), 1)
        self.assertEqual(int(target_analysis.loc[0, "duplicate_path"]), 1)
        pair = overlap[
            (overlap["failure_left"] == "ambiguous_path")
            & (overlap["failure_right"] == "duplicate_path")
        ]
        self.assertEqual(int(pair.iloc[0]["target_count"]), 1)
        self.assertFalse(strata.empty)
        self.assertEqual(analysis["bootstrap_unit"], "user_cluster")

    def test_remote_runner_contract_is_fail_closed_and_replicated(self) -> None:
        runner = Path(
            "experiments/v1_evidence_chain/autodl/run_remote_gate20_d7_trained_beam_batch.sh"
        )
        if not runner.exists():
            self.skipTest("AutoDL orchestration is intentionally outside the reviewer package")
        runner = runner.read_text(encoding="utf-8")
        self.assertNotIn("if ! archive_outputs", runner)
        self.assertIn('if [[ -e "${BATCH_ROOT}" || -e "${ARCHIVE_DIR}" ]]', runner)
        self.assertIn("GRID_FOLD1_ROOT", runner)
        self.assertIn("evaluate_grid_promotion", runner)
        self.assertIn('tar -czf "${ARCHIVE_DIR}/g20_outputs.tgz"', runner)
        self.assertIn("|| return 1", runner)


if __name__ == "__main__":
    unittest.main()
