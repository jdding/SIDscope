from __future__ import annotations

import argparse
import importlib.util
import sys
import unittest
from unittest import mock
import tempfile
from pathlib import Path

TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None

if TORCH_AVAILABLE:  # pragma: no branch - imports are exercised in full environments
    import pandas as pd
    from pandas.testing import assert_frame_equal

    from sidinspector.d7_trace import label_traces
    from tools.run_v1_gate21_tiger_d7_trace import (
        DEFAULT_DACT_ROOT,
        assert_official_preprocessing_parity,
        build_trie,
        decode_mode,
        load_mapping,
        load_model,
        load_official_module,
        offset_code,
        prepare_examples,
        ranking_metrics,
        sid_frame,
        stage_contract_pass,
        validate_mode_accounting,
        source_revision,
    )
    from sidinspector.trace_analysis import analyze_traces as lightweight_analyze_traces
    from tools.run_v1_gate20_d7_trained_beam import analyze_traces as legacy_analyze_traces


@unittest.skipUnless(TORCH_AVAILABLE, "G21 released-checkpoint tests require optional PyTorch")
class Gate21TigerD7TraceTest(unittest.TestCase):
    @staticmethod
    def _stage_args(**overrides: object) -> argparse.Namespace:
        values = {
            "stage": "preflight",
            "reviewed_manifest_sha256": "",
            "device": "cpu",
            "max_targets": 4,
            "beam_width": 3,
            "batch_size": 2,
            "modes": ["constrained", "unconstrained"],
            "bootstrap_samples": 20,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_stage_contracts_are_exact_and_manifest_bound(self) -> None:
        self.assertTrue(stage_contract_pass(self._stage_args(), 4))
        self.assertFalse(stage_contract_pass(self._stage_args(), 3))

        canary = self._stage_args(
            stage="canary",
            reviewed_manifest_sha256="a" * 64,
            device="cuda",
            max_targets=100,
            beam_width=20,
            batch_size=16,
            modes=["constrained"],
        )
        self.assertTrue(stage_contract_pass(canary, 100))
        self.assertFalse(stage_contract_pass(canary, 99))
        canary.reviewed_manifest_sha256 = ""
        self.assertFalse(stage_contract_pass(canary, 100))
        canary.reviewed_manifest_sha256 = "a" * 64
        canary.device = "cpu"
        self.assertFalse(stage_contract_pass(canary, 100))
        canary.device = "cuda"
        canary.batch_size = 8
        self.assertFalse(stage_contract_pass(canary, 100))

        primary = self._stage_args(
            stage="primary",
            reviewed_manifest_sha256="b" * 64,
            device="cuda",
            max_targets=500,
            beam_width=50,
            batch_size=16,
            modes=["constrained", "unconstrained"],
            bootstrap_samples=2000,
        )
        self.assertTrue(stage_contract_pass(primary, 500))
        primary.modes = ["unconstrained", "constrained"]
        self.assertFalse(stage_contract_pass(primary, 500))
        primary.modes = ["constrained", "unconstrained"]
        primary.device = "cpu"
        self.assertFalse(stage_contract_pass(primary, 500))

    def test_official_loader_fail_closed_stub_covers_unused_openpyxl_import(self) -> None:
        if not (DEFAULT_DACT_ROOT / "TIGER-backbone" / "main_trie.py").is_file():
            self.skipTest("released package does not redistribute the DACT source checkout")

        real_find_spec = importlib.util.find_spec
        existing = sys.modules.pop("openpyxl", None)

        def without_openpyxl(name: str, *args: object, **kwargs: object) -> object:
            return None if name == "openpyxl" else real_find_spec(name, *args, **kwargs)

        try:
            with mock.patch(
                "tools.run_v1_gate21_tiger_d7_trace.importlib.util.find_spec",
                side_effect=without_openpyxl,
            ):
                module = load_official_module(DEFAULT_DACT_ROOT)
            self.assertTrue(bool(module._sidscope_openpyxl_stubbed))
            with self.assertRaises(RuntimeError):
                module.Workbook()
        finally:
            if existing is not None:
                sys.modules["openpyxl"] = existing

    def test_hash_bound_source_revision_marker_precedes_container_git_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SIDSCOPE_PINNED_REVISION.txt").write_text("abc123\n", encoding="utf-8")
            self.assertEqual(source_revision(root), "abc123")

    def test_offset_code_matches_released_tiger_contract(self) -> None:
        self.assertEqual(offset_code([20, 6, 39, 0]), (21, 263, 552, 769))
        with self.assertRaises(ValueError):
            offset_code([256, 0, 0, 0])

    def test_sid_frame_uses_generated_token_space(self) -> None:
        frame = sid_frame({1: (21, 263, 552, 769), 2: (22, 264, 553, 770)})
        self.assertEqual(list(frame.columns), ["item_id", "sid_level_0", "sid_level_1", "sid_level_2", "sid_level_3"])
        traces = pd.DataFrame(
            [{"trace_id": "t", "user_id": "u", "rank": 1, "sid_path": "21-263-552-769", "target_item_id": 1}]
        )
        labels = label_traces(frame, traces)
        self.assertEqual(labels.loc[0, "primary_failure"], "valid_hit")
        self.assertTrue(bool(labels.loc[0, "target_hit"]))

    def test_immediate_eos_is_labeled_invalid_path(self) -> None:
        frame = sid_frame({1: (21, 263, 552, 769)})
        traces = pd.DataFrame(
            [{"trace_id": "t", "user_id": "u", "rank": 1, "sid_path": "", "target_item_id": 1}]
        )
        labels = label_traces(frame, traces)
        self.assertEqual(labels.loc[0, "primary_failure"], "invalid_path")
        self.assertEqual(int(labels.loc[0, "path_prefix_len"]), 0)

    def test_ranking_metrics_use_target_path_rank(self) -> None:
        outcomes = pd.DataFrame({"target_path_rank": [1, 6, None]})
        metrics = ranking_metrics(outcomes)
        self.assertAlmostEqual(metrics["Recall@5"], 1 / 3)
        self.assertAlmostEqual(metrics["Recall@10"], 2 / 3)
        self.assertGreater(metrics["NDCG@10"], metrics["NDCG@5"])

    def test_lightweight_trace_analysis_matches_g20_contract(self) -> None:
        sid = sid_frame({1: (21, 263, 552, 769), 2: (22, 264, 553, 770)})
        traces = pd.DataFrame(
            [
                {
                    "trace_id": trace_id,
                    "user_id": user,
                    "rank": rank,
                    "sid_path": path,
                    "target_item_id": target,
                    "resolved_item_ids_exporter": resolved,
                    "beam_width": 2,
                    "decoding_mode": "fixture",
                }
                for trace_id, user, target in (("t1", "u1", 1), ("t2", "u2", 2))
                for rank, path, resolved in (
                    (1, "21-263-552-769", "1"),
                    (2, "99-399-699-999", ""),
                )
            ]
        )
        outcomes = pd.DataFrame(
            [
                {
                    "trace_id": trace_id,
                    "user_id": user,
                    "target_missed": False,
                    "target_ambiguous": False,
                    "target_path_survived": True,
                    "target_item_uniquely_hit": True,
                }
                for trace_id, user in (("t1", "u1"), ("t2", "u2"))
            ]
        )
        legacy = legacy_analyze_traces(
            sid=sid, traces=traces, outcomes=outcomes, bootstrap_samples=20, seed=7
        )
        lightweight = lightweight_analyze_traces(
            sid=sid, traces=traces, outcomes=outcomes, bootstrap_samples=20, seed=7
        )
        for old_frame, new_frame in zip(legacy[:4], lightweight[:4]):
            assert_frame_equal(old_frame, new_frame)
        self.assertEqual(legacy[4], lightweight[4])

    def test_released_preprocessing_has_golden_parity(self) -> None:
        code_path = DEFAULT_DACT_ROOT / "data/Tools/Tools_0.6_cf.npy"
        test_path = DEFAULT_DACT_ROOT / "data/Tools/test_0.6.parquet"
        if not code_path.exists() or not test_path.exists():
            self.skipTest("released DACT assets are not present")
        item_to_code, _ = load_mapping(code_path)
        examples = prepare_examples(test_path, item_to_code, max_targets=2, max_history_items=20)
        result = assert_official_preprocessing_parity(
            dact_root=DEFAULT_DACT_ROOT,
            test_path=test_path,
            code_path=code_path,
            examples=examples,
            item_to_code=item_to_code,
            max_history_items=20,
            checks=2,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checked_rows"], 2)

    def test_released_checkpoint_generation_closes_both_mode_contracts(self) -> None:
        checkpoint = DEFAULT_DACT_ROOT / "TIGER-backbone/ckpt/tiger_Tools_0.6_cf.pth"
        code_path = DEFAULT_DACT_ROOT / "data/Tools/Tools_0.6_cf.npy"
        test_path = DEFAULT_DACT_ROOT / "data/Tools/test_0.6.parquet"
        if not checkpoint.exists() or not code_path.exists() or not test_path.exists():
            self.skipTest("released DACT assets are not present")
        item_to_code, reverse = load_mapping(code_path)
        examples = prepare_examples(test_path, item_to_code, max_targets=2, max_history_items=20)
        model = load_model(DEFAULT_DACT_ROOT, checkpoint, "cpu")
        _, constraint = build_trie(DEFAULT_DACT_ROOT, item_to_code)
        provenance = {
            "mapping_sha256": "fixture",
            "checkpoint_sha256": "fixture",
            "configuration_sha256": "fixture",
        }
        for mode in ("constrained", "unconstrained"):
            traces, outcomes = decode_mode(
                model=model,
                examples=examples,
                item_to_code=item_to_code,
                reverse=reverse,
                constraint_fn=constraint,
                mode=mode,
                beam_width=3,
                batch_size=2,
                max_history_items=20,
                device="cpu",
                provenance=provenance,
            )
            result = validate_mode_accounting(
                traces=traces,
                outcomes=outcomes,
                examples=examples,
                beam_width=3,
                mode=mode,
                depth=4,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["trace_rows"], 6)


if __name__ == "__main__":
    unittest.main()
