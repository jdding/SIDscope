from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None

if TORCH_AVAILABLE:  # pragma: no branch - imports are exercised in full environments
    import pandas as pd

    from tools.run_v1_gate22_downstream_handoff import (
        build_stage_contract,
        build_validity_gate,
        rank_metrics,
        summarize_outcomes,
        write_d7_accounting,
    )


@unittest.skipUnless(TORCH_AVAILABLE, "G22 generator-handoff tests require optional PyTorch")
class Gate22DownstreamHandoffTest(unittest.TestCase):
    def test_unmapped_targets_are_forced_misses(self) -> None:
        frame = pd.DataFrame(
            {
                "state": ["stale"] * 3,
                "target_stratum": ["common", "new", "new"],
                "target_mapped": [True, False, False],
                "target_path_rank": [1, None, None],
                "target_unique_item_rank": [1, None, None],
                "history_missing_item_count": [0, 1, 2],
            }
        )
        metrics = rank_metrics(frame, "target_path_rank")
        self.assertAlmostEqual(metrics["Recall@20"], 1 / 3)
        summary = summarize_outcomes(frame)
        new_row = summary[summary["target_stratum"] == "new"].iloc[0]
        self.assertEqual(float(new_row["mapped_target_rate"]), 0.0)
        self.assertEqual(float(new_row["path_Recall@20"]), 0.0)

    def test_ambiguous_path_is_not_a_unique_item_hit(self) -> None:
        frame = pd.DataFrame(
            {
                "state": ["repaired", "repaired"],
                "target_stratum": ["common", "common"],
                "target_mapped": [True, True],
                "target_path_rank": [1, 2],
                "target_unique_item_rank": [None, 2],
                "history_missing_item_count": [0, 0],
            }
        )
        summary = summarize_outcomes(frame)
        overall = summary[summary["target_stratum"] == "overall"].iloc[0]
        self.assertEqual(float(overall["path_Recall@5"]), 1.0)
        self.assertEqual(float(overall["item_Recall@5"]), 0.5)

    def test_partial_common_recovery_remains_boundary_only(self) -> None:
        rows = []
        values = {
            "stale_old_model_old_mapping": {"overall": (0.45, 0.0), "common": (0.50, 0.0)},
            "mapping_only_old_model_new_mapping": {
                "overall": (0.10, 0.0),
                "common": (0.10, 0.0),
                "new": (0.0, 0.0),
            },
            "adapted_model_new_mapping_seed2025": {
                "overall": (0.20, 0.1),
                "common": (0.20, 0.0),
                "new": (0.10, 0.10),
            },
        }
        for state, strata in values.items():
            for stratum, (ndcg, recall) in strata.items():
                rows.append(
                    {
                        "state": state,
                        "target_stratum": stratum,
                        "path_NDCG@20": ndcg,
                        "item_Recall@20": recall,
                    }
                )
        gate = build_validity_gate(pd.DataFrame(rows))
        self.assertFalse(gate["adapted_all_seeds_meet_a_relative_common_recovery"])
        self.assertEqual(gate["claim_status"], "BOUNDARY_ONLY")

    def test_primary_contract_requires_exact_preregistered_seeds(self) -> None:
        common = dict(
            stage="primary",
            target_rows=5364,
            full_test_rows=5364,
            beam_width=20,
            max_train_rows=0,
            max_validation_rows=0,
            max_epochs=200,
            patience=15,
            reviewed_manifest_sha256="a" * 64,
        )
        self.assertTrue(build_stage_contract(seeds=[2025, 2026, 2027], **common)["primary"])
        self.assertFalse(build_stage_contract(seeds=[1, 2, 3], **common)["primary"])

    def test_normalized_d7_accounting_is_materialized(self) -> None:
        mapping = {1: (10, 20), 2: (10, 21)}
        outcomes = pd.DataFrame(
            [
                {
                    "trace_id": "t1",
                    "state": "s",
                    "user_id": "u1",
                    "target_item_id": 1,
                    "target_path_rank": 1,
                    "target_path_survived": True,
                    "target_uniquely_addressable": True,
                    "target_item_uniquely_hit": True,
                    "target_missed": False,
                    "target_ambiguous": False,
                    "decoding_mode": "constrained",
                }
            ]
        )
        beams = pd.DataFrame(
            [
                {
                    "trace_id": "t1",
                    "state": "s",
                    "user_id": "u1",
                    "target_item_id": 1,
                    "rank": 1,
                    "score": -0.1,
                    "sid_path": "10-20",
                    "resolved_item_ids_exporter": "1",
                    "beam_width": 2,
                    "decoding_mode": "constrained_beam",
                },
                {
                    "trace_id": "t1",
                    "state": "s",
                    "user_id": "u1",
                    "target_item_id": 1,
                    "rank": 2,
                    "score": -0.2,
                    "sid_path": "10-21",
                    "resolved_item_ids_exporter": "2",
                    "beam_width": 2,
                    "decoding_mode": "constrained_beam",
                },
            ]
        )
        with TemporaryDirectory() as directory:
            result = write_d7_accounting(
                state_name="s",
                item_to_code=mapping,
                outcomes=outcomes,
                beams=beams,
                output_dir=Path(directory),
                bootstrap_samples=20,
                seed=2025,
            )
            self.assertTrue(result["deterministic_label_check"])
            self.assertTrue(result["exporter_labeler_resolution_match"])
            self.assertTrue((Path(directory) / "s_d7_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
