from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
import pickle

import numpy as np
import pytest

from tests import local_test_bootstrap  # noqa: F401
from tools.materialize_diffgrm_protocol_train_surface import materialize
from tools.prepare_diffgrm_protocol import _metadata_rows, load_test_protocol
from tools.run_diffgrm_runtime import verify_processed_cache
from tools.run_diffgrm_resumable_training import (
    expected_bindings,
    restore_rng_state,
    validate_resume_payload,
)
from tools.export_diffgrm_masked_trace import validate_training_binding


def _write_protocol(path: Path, users: list[int]) -> None:
    rows = len(users)
    np.savez(
        path,
        train_user_id=np.asarray(users),
        train_target_idx=np.asarray([2 + index % 2 for index in range(rows)]),
        train_seq_offsets=np.arange(rows + 1, dtype=np.int64),
        train_seq_values=np.asarray([1 + index % 3 for index in range(rows)]),
        item_num=np.asarray([4]),
        validation_user_id=np.asarray([999]),
        test_user_id=np.asarray([1000]),
    )


def test_materializes_latest_consumer_equivalent_train_surface(tmp_path: Path) -> None:
    protocol = tmp_path / "protocol.npz"
    _write_protocol(protocol, [7, 7, 9])
    vocab = tmp_path / "vocab.json"
    vocab.write_text(json.dumps({"padding_id": 0, "raw_to_index": {"a": 1, "b": 2, "c": 3}}))
    output = tmp_path / "train.pkl"

    report = materialize(protocol, vocab, output)
    with output.open("rb") as stream:
        surface = pickle.load(stream)

    assert report["source_train_rows"] == 3
    assert report["consumer_train_rows"] == 2
    assert report["validation_arrays_read"] is False
    assert report["test_arrays_read"] is False
    assert surface["train_samples"][0]["user_id"] == "7"
    assert surface["train_samples"][0]["seq_idx"] == [2]
    assert surface["train_observed_indices"] == [1, 2, 3]
    assert surface["idx_to_item"] == {1: "a", 2: "b", 3: "c"}
    assert "test_samples" not in surface


def test_rejects_noncontiguous_user_rows(tmp_path: Path) -> None:
    protocol = tmp_path / "protocol.npz"
    _write_protocol(protocol, [7, 9, 7])
    vocab = tmp_path / "vocab.json"
    vocab.write_text(json.dumps({"padding_id": 0, "raw_to_index": {"a": 1, "b": 2, "c": 3}}))
    with pytest.raises(ValueError, match="not contiguous"):
        materialize(protocol, vocab, tmp_path / "train.pkl")


def test_dataset_neutral_cache_manifest_is_fail_closed(tmp_path: Path) -> None:
    processed = tmp_path / "cache" / "processed"
    processed.mkdir(parents=True)
    sem_ids = processed / "codes.sem_ids"
    sem_ids.write_bytes(b"codes")
    manifest = tmp_path / "manifest.json"
    from tools.run_diffgrm_runtime import sha256_file

    manifest.write_text(json.dumps({
        "schema": "sidscope.diffgrm_processed_cache_manifest.v1",
        "domain": "steam",
        "source_revision": "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c",
        "catalog_rows": 3,
        "files": {"codes.sem_ids": sha256_file(sem_ids)},
        "semantic_id_filename": "codes.sem_ids",
    }))
    observed = verify_processed_cache(tmp_path / "cache", manifest)
    assert observed["domain"] == "steam"
    sem_ids.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_processed_cache(tmp_path / "cache", manifest)


def test_metadata_reader_accepts_safe_steam_python_literal(tmp_path: Path) -> None:
    metadata = tmp_path / "steam.json"
    metadata.write_text("{u'id': u'10', u'title': u'Example'}\n", encoding="utf-8")
    assert list(_metadata_rows(metadata)) == [{"id": "10", "title": "Example"}]


def test_metadata_reader_rejects_executable_literal(tmp_path: Path) -> None:
    metadata = tmp_path / "bad.json"
    metadata.write_text("__import__('os').system('false')\n", encoding="utf-8")
    with pytest.raises(ValueError, match="neither JSON nor a Python literal"):
        list(_metadata_rows(metadata))


def test_frozen_split_protocol_maps_numeric_buckets_without_first_n(tmp_path: Path) -> None:
    protocol = tmp_path / "split.npz"
    np.savez(
        protocol,
        test_user_id=np.asarray([10, 11, 12, 13, 14]),
        test_target_idx=np.asarray([2, 2, 2, 2, 2]),
        test_gap_days=np.asarray([1, 40, 100, 200, 500], dtype=np.float32),
        test_bucket=np.asarray([0, 1, 2, 3, 4], dtype=np.uint8),
        test_seq_offsets=np.asarray([0, 1, 2, 3, 4, 5]),
        test_seq_values=np.asarray([1, 1, 1, 1, 1]),
    )
    with np.load(protocol, allow_pickle=False) as value:
        episode_ids, _, _, _, _, buckets = load_test_protocol(value)
    assert episode_ids.tolist() == ["10", "11", "12", "13", "14"]
    assert buckets.tolist() == ["short", "30-90d", "90-180d", "180-365d", ">365d"]


def test_recoverable_training_binds_domain_and_processed_cache(tmp_path: Path) -> None:
    inputs = {}
    for name in (
        "runtime_manifest", "prepared_dataset", "semantic_id_cache",
        "source_manifest", "processed_cache_manifest",
    ):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        inputs[name] = path
    args = Namespace(
        **inputs,
        entrypoint_sha256="a" * 64,
        domain="steam",
        seed=2024,
        target_steps=770,
        train_batch_size=256,
        learning_rate=0.003,
        warmup_steps=100,
    )
    bindings = expected_bindings(args)
    assert bindings["domain"] == "steam"
    assert len(bindings["processed_cache_manifest_sha256"]) == 64

    payload = {
        "schema": "genrec_dormant.diffgrm_recoverable_state.v1",
        "bindings": bindings,
        "completed_steps": 3,
        "completed_epochs": 1,
        "model": {},
        "optimizer": {},
        "scheduler": {},
        "rng_state": {},
        "epoch_records": [{
            "epoch": 1,
            "completed_steps": 3,
            "model_state_sha256": "b" * 64,
        }],
    }
    validate_resume_payload(payload, bindings, verify_model_hash=False)
    divergent = dict(bindings, domain="amazon_vg")
    with pytest.raises(ValueError, match="frozen bindings mismatch"):
        validate_resume_payload(payload, divergent, verify_model_hash=False)


def test_trace_exporter_binds_training_domain_and_cache(tmp_path: Path) -> None:
    from tools.export_diffgrm_masked_trace import sha256_file

    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"checkpoint")
    manifest = {
        "status": "pass",
        "completed_steps": 10000,
        "formal_checkpoint_sha256": sha256_file(checkpoint),
        "bindings": {
            "domain": "steam",
            "processed_cache_manifest_sha256": "c" * 64,
        },
    }
    validate_training_binding(
        manifest,
        checkpoint,
        10000,
        domain="steam",
        processed_cache_manifest_sha256="c" * 64,
    )
    with pytest.raises(ValueError, match="domain binding mismatch"):
        validate_training_binding(
            manifest,
            checkpoint,
            10000,
            domain="amazon_vg",
            processed_cache_manifest_sha256="c" * 64,
        )


def test_rng_restore_normalizes_map_location_tensors_to_cpu() -> None:
    class State:
        def __init__(self) -> None:
            self.cpu_calls = 0

        def cpu(self) -> "State":
            self.cpu_calls += 1
            return self

    class Cuda:
        def __init__(self) -> None:
            self.value = None

        @staticmethod
        def is_available() -> bool:
            return True

        def set_rng_state_all(self, value: object) -> None:
            self.value = value

    class Torch:
        def __init__(self) -> None:
            self.cuda = Cuda()
            self.value = None

        def set_rng_state(self, value: object) -> None:
            self.value = value

    cpu_state = State()
    cuda_state = State()
    torch = Torch()
    restore_rng_state(torch, {
        "python": __import__("random").getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": cpu_state,
        "torch_cuda": [cuda_state],
    })
    assert torch.value is cpu_state
    assert torch.cuda.value == [cuda_state]
    assert cpu_state.cpu_calls == 1
    assert cuda_state.cpu_calls == 1
