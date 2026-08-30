from __future__ import annotations

import json
import unittest
from pathlib import Path

from sidinspector.contracts import (
    RuntimeContractValidationError,
    load_checkpoint_binding,
    load_episode_selection,
    load_prepared_dataset,
    load_run_identity,
    load_source_identity,
    load_trace_envelope,
    validate_runtime_bindings,
    validate_trace_envelope,
    with_content_sha256,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/canonical_pipeline_fixture"


class RuntimeContractsTest(unittest.TestCase):
    def load_runtime(self):
        return (
            load_episode_selection(FIXTURE / "episode_selection.json"),
            load_run_identity(FIXTURE / "run_identity.json"),
            load_checkpoint_binding(FIXTURE / "checkpoint_binding.json"),
            load_trace_envelope(FIXTURE / "trace_envelope.json"),
        )

    def test_complete_runtime_pipeline_bindings_pass(self) -> None:
        selection, run, checkpoint, trace = self.load_runtime()
        source = load_source_identity(FIXTURE / "source_identity.json")
        prepared = load_prepared_dataset(FIXTURE / "prepared_dataset.json")

        validate_runtime_bindings(
            selection,
            run,
            checkpoint,
            trace,
            source_sha256=source.content_sha256,
            prepared_sha256=prepared.content_sha256,
        )
        self.assertEqual(trace.to_dict()["method_family"], "parallel_graph_token_set")

    def test_each_runtime_typed_negative_fails_closed(self) -> None:
        cases = (
            (load_episode_selection, "expected_failure_duplicate_episode.json", "duplicate_episode_id"),
            (load_run_identity, "expected_failure_invalid_seed.json", "invalid_seed"),
            (
                load_checkpoint_binding,
                "expected_failure_incomplete_resumable_state.json",
                "incomplete_resumable_state",
            ),
            (load_trace_envelope, "expected_failure_rank_state.json", "rank_state_mismatch"),
        )
        for loader, name, expected in cases:
            with self.subTest(name=name), self.assertRaises(
                RuntimeContractValidationError
            ) as captured:
                loader(FIXTURE / name)
            self.assertEqual(captured.exception.code, expected)

    def test_cross_binding_tamper_fails_after_structural_validation(self) -> None:
        selection, run, checkpoint, trace = self.load_runtime()
        source = load_source_identity(FIXTURE / "source_identity.json")
        prepared = load_prepared_dataset(FIXTURE / "prepared_dataset.json")
        document = trace.to_dict()
        document["run_binding"]["content_sha256"] = "0" * 64
        rebound = validate_trace_envelope(with_content_sha256(document))

        with self.assertRaises(RuntimeContractValidationError) as captured:
            validate_runtime_bindings(
                selection,
                run,
                checkpoint,
                rebound,
                source_sha256=source.content_sha256,
                prepared_sha256=prepared.content_sha256,
            )
        self.assertEqual(captured.exception.code, "trace_run_binding_mismatch")

    def test_native_payload_is_hash_bound_not_flattened(self) -> None:
        trace = load_trace_envelope(FIXTURE / "trace_envelope.json")
        document = trace.to_dict()
        self.assertEqual(document["payload_schema"], "sidscope.rpg_trained_trace_bundle.v2")
        self.assertNotIn("parallel_token_scores", document)
        self.assertRegex(document["payload_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
