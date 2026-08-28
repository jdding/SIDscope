import copy
import json

import pytest
import torch

from tests import local_test_bootstrap  # noqa: F401
from tools.run_rpg_resumable_training import (
    LEDGER_SCHEMA,
    STATE_SCHEMA,
    audit_epoch_record_sidecar,
    atomic_json_write,
    atomic_torch_save,
    build_epoch_ledger,
    recover_epoch_records,
    sha256_state_dict,
    validate_epoch_records,
)


def epoch_record(epoch: int, step: int, batches: int, model_hash: str) -> dict:
    return {
        "epoch": epoch,
        "global_step": step,
        "mean_train_loss": 1.0 / epoch,
        "train_batches": batches,
        "eval_batches": 1,
        "val_metrics": {"ndcg@10": 0.0},
        "model_state_sha256": model_hash,
        "elapsed_seconds": 0.1,
    }


def checkpoint_with_records() -> dict:
    model = {"weight": torch.tensor([[1.0, 2.0]])}
    model_hash = sha256_state_dict(model)
    return {
        "schema": STATE_SCHEMA,
        "run_id": "fixture-run",
        "completed_epoch": 1,
        "global_step": 2,
        "model": model,
        "epoch_records": [epoch_record(1, 2, 2, model_hash)],
    }


def test_atomic_checkpoint_embeds_records_and_writes_hash_bound_ledger(tmp_path) -> None:
    state = checkpoint_with_records()
    state_path = tmp_path / "last_state.pt"
    ledger_path = tmp_path / "epoch_ledger.json"

    atomic_torch_save(state, state_path)
    ledger = build_epoch_ledger(run_id="fixture-run", state_path=state_path, state=state)
    atomic_json_write(ledger, ledger_path)

    observed = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert observed["schema"] == LEDGER_SCHEMA
    assert observed["completed_epoch"] == 1
    assert observed["global_step"] == 2
    assert observed["epoch_records"] == state["epoch_records"]


def test_interrupted_resume_recovers_records_without_final_manifest() -> None:
    state = checkpoint_with_records()

    records, source = recover_epoch_records(state, prior_manifest=None)

    assert source == "checkpoint_embedded"
    assert records == state["epoch_records"]


def test_checkpoint_newer_than_ledger_accepts_only_a_continuous_stale_prefix() -> None:
    state = checkpoint_with_records()
    second_model = {"weight": torch.tensor([[2.0, 3.0]])}
    second_hash = sha256_state_dict(second_model)
    checkpoint_records = state["epoch_records"] + [epoch_record(2, 4, 2, second_hash)]
    stale_ledger = {
        "schema": LEDGER_SCHEMA,
        "run_id": "fixture-run",
        "last_state_sha256": "1" * 64,
        "epoch_records": state["epoch_records"],
    }

    status = audit_epoch_record_sidecar(
        label="epoch ledger",
        sidecar=stale_ledger,
        expected_schema=LEDGER_SCHEMA,
        run_id="fixture-run",
        checkpoint_sha256="2" * 64,
        checkpoint_records=checkpoint_records,
    )
    assert status == "stale_prefix_recovered_from_checkpoint"

    divergent = copy.deepcopy(stale_ledger)
    divergent["epoch_records"][0]["model_state_sha256"] = "3" * 64
    with pytest.raises(RuntimeError, match="diverge"):
        audit_epoch_record_sidecar(
            label="epoch ledger",
            sidecar=divergent,
            expected_schema=LEDGER_SCHEMA,
            run_id="fixture-run",
            checkpoint_sha256="2" * 64,
            checkpoint_records=checkpoint_records,
        )


def test_legacy_resume_requires_matching_continuous_manifest() -> None:
    state = checkpoint_with_records()
    legacy = copy.deepcopy(state)
    del legacy["epoch_records"]

    with pytest.raises(RuntimeError, match="no embedded epoch records"):
        recover_epoch_records(legacy, prior_manifest=None)

    records, source = recover_epoch_records(
        legacy, {"epoch_records": state["epoch_records"]}
    )
    assert source == "legacy_run_manifest"
    assert records == state["epoch_records"]


def test_epoch_continuity_rejects_missing_epoch_step_or_model_hash() -> None:
    state = checkpoint_with_records()
    record = state["epoch_records"][0]
    bad_epoch = [dict(record, epoch=2)]
    bad_step = [dict(record, global_step=3)]
    bad_hash = [dict(record, model_state_sha256="0" * 64)]

    for records in (bad_epoch, bad_step, bad_hash):
        with pytest.raises(RuntimeError):
            validate_epoch_records(
                records,
                completed_epoch=1,
                global_step=2,
                model_state_sha256=record["model_state_sha256"],
            )
