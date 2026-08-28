#!/usr/bin/env python3
"""Run RPG training with epoch-boundary resumability and auditable manifests.

This interoperability runner is intentionally kept outside the SIDScope MIT
package and the upstream RPG checkout.  It imports a pinned RPG checkout at
runtime without modifying or vendoring it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Optional

import numpy as np
import torch
from torch.nn.utils import clip_grad_norm_
from torch.optim import AdamW
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm
from transformers.optimization import get_scheduler


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SCHEMA = "sidscope.rpg_trained_closure_run.v1"
STATE_SCHEMA = "sidscope.rpg_resumable_state.v2"
LEGACY_STATE_SCHEMA = SCHEMA
LEDGER_SCHEMA = "sidscope.rpg_epoch_ledger.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpg-source", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--prepared-dataset", type=Path)
    parser.add_argument("--prepared-root", type=Path)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Hash-check the prepared contract and exit before constructing RPG runtime state.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--stop-after-epoch", type=int)
    parser.add_argument("--train-limit", type=int)
    parser.add_argument("--val-limit", type=int)
    parser.add_argument("--eval-max-batches", type=int)
    parser.add_argument("--train-batch-size", type=int, default=256)
    parser.add_argument("--eval-batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--warmup-steps", type=int, default=10000)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--save-every-epoch", action="store_true", default=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_state_dict(state: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tensor.dtype).encode("ascii"))
        digest.update(np.asarray(tensor.shape, dtype=np.int64).tobytes())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def capture_rng_state() -> dict[str, Any]:
    state: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()
    return state


def restore_rng_state(state: dict[str, Any]) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch_cpu"])
    if torch.cuda.is_available() and "torch_cuda" in state:
        torch.cuda.set_rng_state_all(state["torch_cuda"])


def atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def atomic_json_write(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_epoch_records(
    records: list[dict[str, Any]],
    *,
    completed_epoch: int,
    global_step: int,
    model_state_sha256: str,
) -> None:
    if len(records) != completed_epoch:
        raise RuntimeError("epoch record count does not match completed epoch")
    previous_step = 0
    for expected_epoch, record in enumerate(records, start=1):
        if record.get("epoch") != expected_epoch:
            raise RuntimeError("epoch records are not continuous")
        record_step = record.get("global_step")
        train_batches = record.get("train_batches")
        if not isinstance(record_step, int) or not isinstance(train_batches, int):
            raise RuntimeError("epoch record step fields must be integers")
        if train_batches <= 0 or record_step != previous_step + train_batches:
            raise RuntimeError("epoch record global steps are not continuous")
        record_hash = record.get("model_state_sha256")
        if not isinstance(record_hash, str) or len(record_hash) != 64:
            raise RuntimeError("epoch record model-state hash is invalid")
        previous_step = record_step
    if previous_step != global_step:
        raise RuntimeError("epoch records do not reach the checkpoint global step")
    if records and records[-1]["model_state_sha256"] != model_state_sha256:
        raise RuntimeError("epoch records do not match the checkpoint model state")


def recover_epoch_records(
    checkpoint: dict[str, Any], prior_manifest: Optional[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    completed_epoch = int(checkpoint["completed_epoch"])
    global_step = int(checkpoint["global_step"])
    model_state_sha256 = sha256_state_dict(checkpoint["model"])
    embedded = checkpoint.get("epoch_records")
    if embedded is not None:
        records = list(embedded)
        source = "checkpoint_embedded"
    elif prior_manifest is not None:
        records = list(prior_manifest.get("epoch_records", []))
        source = "legacy_run_manifest"
    elif completed_epoch == 0:
        records = []
        source = "empty_checkpoint"
    else:
        raise RuntimeError(
            "legacy resume checkpoint has no embedded epoch records and no matching run manifest"
        )
    validate_epoch_records(
        records,
        completed_epoch=completed_epoch,
        global_step=global_step,
        model_state_sha256=model_state_sha256,
    )
    return records, source


def audit_epoch_record_sidecar(
    *,
    label: str,
    sidecar: dict[str, Any],
    expected_schema: str,
    run_id: str,
    checkpoint_sha256: str,
    checkpoint_records: list[dict[str, Any]],
) -> str:
    if sidecar.get("schema") != expected_schema or sidecar.get("run_id") != run_id:
        raise RuntimeError(f"{label} identity does not match the resume checkpoint")
    records = list(sidecar.get("epoch_records", []))
    if records == checkpoint_records:
        if sidecar.get("last_state_sha256") != checkpoint_sha256:
            raise RuntimeError(f"{label} state hash does not match the resume checkpoint")
        return "exact"
    if records and checkpoint_records[: len(records)] == records:
        return "stale_prefix_recovered_from_checkpoint"
    raise RuntimeError(f"{label} epoch records diverge from the resume checkpoint")


def build_epoch_ledger(
    *,
    run_id: str,
    state_path: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    records = list(state["epoch_records"])
    validate_epoch_records(
        records,
        completed_epoch=int(state["completed_epoch"]),
        global_step=int(state["global_step"]),
        model_state_sha256=sha256_state_dict(state["model"]),
    )
    return {
        "schema": LEDGER_SCHEMA,
        "status": "checkpointed",
        "run_id": run_id,
        "state_schema": state["schema"],
        "completed_epoch": state["completed_epoch"],
        "global_step": state["global_step"],
        "model_state_sha256": records[-1]["model_state_sha256"] if records else None,
        "last_state_sha256": sha256_file(state_path),
        "epoch_records": records,
    }


def limit_dataset(dataset: Any, limit: Optional[int]) -> Any:
    if limit is None or limit >= len(dataset):
        return dataset
    if limit <= 0:
        raise ValueError("dataset limit must be positive")
    return Subset(dataset, range(limit))


def main() -> None:
    args = parse_args()
    source = args.rpg_source.resolve()
    if not (source / "genrec/models/RPG/model.py").is_file():
        raise SystemExit(f"invalid RPG source checkout: {source}")
    sys.path.insert(0, str(source))

    prepared = None
    prepared_root = None
    if args.prepared_dataset is not None:
        if args.cache_dir is not None:
            raise SystemExit("--cache-dir and --prepared-dataset are mutually exclusive")
        from tools.rpg_non_ar_bridge import (
            canonical_hash as bridge_hash,
            load_prepared_rows,
            validate_prepared_dataset,
            verify_source_checkout,
        )

        prepared = json.loads(args.prepared_dataset.read_text(encoding="utf-8"))
        prepared_root = (args.prepared_root or args.prepared_dataset.parent).resolve()
        prepared_result = validate_prepared_dataset(prepared)
        verify_source_checkout(source)
        if args.seed != prepared["configuration"]["model_seed"]:
            raise SystemExit("--seed must equal prepared configuration.model_seed")
        load_prepared_rows(prepared, prepared_root)
        if args.preflight_only:
            print(
                json.dumps(
                    {
                        "schema": "sidscope.rpg_prepared_training_preflight.v1",
                        "status": "pass",
                        "gpu_required": False,
                        "prepared_dataset_contract_sha256": bridge_hash(prepared),
                        "catalog_rows": prepared_result["catalog_rows"],
                        "test_split_id": prepared_result["test_split_id"],
                        "training_binding_status": prepared["training"].get("status", "complete"),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return
    elif args.preflight_only:
        raise SystemExit("--preflight-only requires --prepared-dataset")
    elif args.cache_dir is None:
        raise SystemExit("Beauty mode requires --cache-dir")

    from genrec.evaluator import Evaluator
    from genrec.utils import get_total_steps

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "last_state.pt"
    best_path = output_dir / "best_model_state.pt"
    manifest_path = output_dir / "run_manifest.json"
    ledger_path = output_dir / "epoch_ledger.json"
    prior_epoch_records: list[dict[str, Any]] = []
    prior_manifest_sha256 = None
    prior_manifest = None
    if args.resume_from and manifest_path.is_file():
        prior_manifest_sha256 = sha256_file(manifest_path)
        prior_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if prior_manifest.get("schema") != SCHEMA or prior_manifest.get("run_id") != args.run_id:
            raise RuntimeError("existing run manifest does not match the resume run")

    started = time.time()
    if prepared is None:
        from genrec.pipeline import Pipeline

        config = {
            "cache_dir": str(args.cache_dir.resolve()) + "/",
            "log_dir": str(output_dir / "logs") + "/",
            "tensorboard_log_dir": str(output_dir / "tensorboard") + "/",
            "ckpt_dir": str(output_dir / "upstream_ckpt") + "/",
            "run_id": args.run_id,
            "rand_seed": args.seed,
            "reproducibility": True,
            "category": "Beauty",
            "metadata": "sentence",
            "sent_emb_model": "sentence-transformers/sentence-t5-base",
            "sent_emb_dim": 768,
            "sent_emb_pca": 128,
            "n_codebook": 32,
            "codebook_size": 256,
            "train_batch_size": args.train_batch_size,
            "eval_batch_size": args.eval_batch_size,
            "lr": args.lr,
            "temperature": 0.03,
            "num_beams": 20,
            "n_edges": 200,
            "propagation_steps": 3,
            "warmup_steps": args.warmup_steps,
            "epochs": args.epochs,
            "steps": None,
            "patience": args.patience,
        }
        pipeline = Pipeline(
            model_name="RPG",
            dataset_name="AmazonReviews2014",
            checkpoint_path=None,
            config_dict=config,
        )
    else:
        from tools.rpg_non_ar_bridge import build_official_runtime, canonical_hash as bridge_hash

        pipeline = build_official_runtime(
            rpg_source=source,
            prepared=prepared,
            prepared_root=prepared_root,
            runtime_dir=output_dir / "prepared_runtime",
        )
        pipeline.config.update(
            {
                "train_batch_size": args.train_batch_size,
                "eval_batch_size": args.eval_batch_size,
                "lr": args.lr,
                "warmup_steps": args.warmup_steps,
                "epochs": args.epochs,
                "steps": None,
                "patience": args.patience,
                "topk": [prepared["configuration"]["rank_cutoff"]],
                "val_metric": f"ndcg@{prepared['configuration']['rank_cutoff']}",
            }
        )
        config = {
            "prepared_dataset_contract_sha256": bridge_hash(prepared),
            "dataset": prepared["dataset"],
            "configuration": prepared["configuration"],
            "train_batch_size": args.train_batch_size,
            "eval_batch_size": args.eval_batch_size,
            "lr": args.lr,
            "warmup_steps": args.warmup_steps,
            "epochs": args.epochs,
            "patience": args.patience,
            "train_limit": args.train_limit,
            "validation_limit": args.val_limit,
        }
    accelerator = pipeline.accelerator
    evaluator = Evaluator(pipeline.config, pipeline.tokenizer)

    train_dataset = limit_dataset(pipeline.tokenized_datasets["train"], args.train_limit)
    val_dataset = limit_dataset(pipeline.tokenized_datasets["val"], args.val_limit)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.train_batch_size,
        shuffle=True,
        collate_fn=pipeline.tokenizer.collate_fn["train"],
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.eval_batch_size,
        shuffle=False,
        collate_fn=pipeline.tokenizer.collate_fn["val"],
    )

    optimizer = AdamW(
        pipeline.model.parameters(), lr=args.lr, weight_decay=pipeline.config["weight_decay"]
    )
    total_steps = get_total_steps(pipeline.config, train_loader)
    scheduler = get_scheduler(
        name="cosine",
        optimizer=optimizer,
        num_warmup_steps=args.warmup_steps,
        num_training_steps=total_steps,
    )
    model, optimizer, train_loader, val_loader, scheduler = accelerator.prepare(
        pipeline.model, optimizer, train_loader, val_loader, scheduler
    )

    start_epoch = 0
    global_step = 0
    best_epoch = 0
    best_score = -1.0
    resumed = False
    resume_sha256 = None
    resume_epoch_record_source = None
    prior_manifest_record_status = None
    prior_ledger_record_status = None
    if args.resume_from:
        resume_path = args.resume_from.resolve()
        checkpoint = torch.load(resume_path, map_location="cpu", weights_only=False)
        if checkpoint.get("schema") not in {STATE_SCHEMA, LEGACY_STATE_SCHEMA}:
            raise RuntimeError("resume checkpoint schema mismatch")
        if checkpoint.get("run_contract") != config:
            raise RuntimeError("resume checkpoint run contract mismatch")
        if checkpoint.get("run_id") != args.run_id:
            raise RuntimeError("resume checkpoint run id mismatch")
        resume_sha256 = sha256_file(resume_path)
        prior_epoch_records, resume_epoch_record_source = recover_epoch_records(
            checkpoint, prior_manifest
        )
        if prior_manifest is not None:
            prior_manifest_record_status = audit_epoch_record_sidecar(
                label="run manifest",
                sidecar=prior_manifest,
                expected_schema=SCHEMA,
                run_id=args.run_id,
                checkpoint_sha256=resume_sha256,
                checkpoint_records=prior_epoch_records,
            )
        if ledger_path.is_file():
            prior_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            prior_ledger_record_status = audit_epoch_record_sidecar(
                label="epoch ledger",
                sidecar=prior_ledger,
                expected_schema=LEDGER_SCHEMA,
                run_id=args.run_id,
                checkpoint_sha256=resume_sha256,
                checkpoint_records=prior_epoch_records,
            )
        accelerator.unwrap_model(model).load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])
        start_epoch = int(checkpoint["completed_epoch"])
        global_step = int(checkpoint["global_step"])
        best_epoch = int(checkpoint["best_epoch"])
        best_score = float(checkpoint["best_val_score"])
        restore_rng_state(checkpoint["rng"])
        resumed = True

    n_epochs = math.ceil(total_steps / (len(train_loader) * accelerator.num_processes))
    stop_after = args.stop_after_epoch if args.stop_after_epoch is not None else n_epochs
    stop_after = min(stop_after, n_epochs)
    if stop_after < start_epoch:
        raise RuntimeError("stop-after-epoch is behind the completed resume epoch")

    epoch_records: list[dict[str, Any]] = []
    for epoch_index in range(start_epoch, stop_after):
        epoch_started = time.time()
        model.train()
        total_loss = 0.0
        observed_batches = 0
        progress = tqdm(train_loader, desc=f"Training - [Epoch {epoch_index + 1}]")
        for batch in progress:
            optimizer.zero_grad()
            output = model(batch)
            loss = output.loss
            accelerator.backward(loss)
            max_grad_norm = pipeline.config["max_grad_norm"]
            if max_grad_norm is not None:
                clip_grad_norm_(model.parameters(), max_grad_norm)
            optimizer.step()
            scheduler.step()
            total_loss += float(loss.item())
            observed_batches += 1
            global_step += 1

        model.eval()
        metric_rows: dict[str, list[torch.Tensor]] = {}
        evaluated_batches = 0
        for batch in tqdm(val_loader, desc="Eval - val"):
            if args.eval_max_batches is not None and evaluated_batches >= args.eval_max_batches:
                break
            with torch.no_grad():
                batch = {key: value.to(accelerator.device) for key, value in batch.items()}
                predictions = model.generate(batch, n_return_sequences=evaluator.maxk)
                results = evaluator.calculate_metrics(predictions, batch["labels"])
            for key, value in results.items():
                metric_rows.setdefault(key, []).append(value)
            evaluated_batches += 1
        metrics = {
            key: float(torch.cat(values).mean().item()) for key, values in metric_rows.items()
        }
        score = metrics[pipeline.config["val_metric"]]
        if score > best_score:
            best_score = score
            best_epoch = epoch_index + 1
            unwrapped = accelerator.unwrap_model(model)
            atomic_torch_save(unwrapped.state_dict(), best_path)

        unwrapped_state = {
            key: value.detach().cpu() for key, value in accelerator.unwrap_model(model).state_dict().items()
        }
        record = {
            "epoch": epoch_index + 1,
            "global_step": global_step,
            "mean_train_loss": total_loss / observed_batches,
            "train_batches": observed_batches,
            "eval_batches": evaluated_batches,
            "val_metrics": metrics,
            "model_state_sha256": sha256_state_dict(unwrapped_state),
            "elapsed_seconds": time.time() - epoch_started,
        }
        cumulative_epoch_records = prior_epoch_records + epoch_records + [record]
        state = {
            "schema": STATE_SCHEMA,
            "run_id": args.run_id,
            "source_revision": "7dcf95ce9e08601810efdd1c850ed6dada5f97c2",
            "run_contract": config,
            "completed_epoch": epoch_index + 1,
            "global_step": global_step,
            "best_epoch": best_epoch,
            "best_val_score": best_score,
            "model": unwrapped_state,
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "rng": capture_rng_state(),
            "epoch_records": cumulative_epoch_records,
        }
        atomic_torch_save(state, state_path)
        atomic_json_write(
            build_epoch_ledger(run_id=args.run_id, state_path=state_path, state=state),
            ledger_path,
        )
        epoch_records.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)
        if epoch_index + 1 - best_epoch >= args.patience:
            break

    final_unwrapped = accelerator.unwrap_model(model)
    final_state_hash = sha256_state_dict(final_unwrapped.state_dict())
    manifest = {
        "schema": SCHEMA,
        "status": "pass",
        "run_id": args.run_id,
        "source": {
            "revision": "7dcf95ce9e08601810efdd1c850ed6dada5f97c2",
            "license": "CC-BY-NC-4.0",
        },
        "runtime": {
            "python": sys.version,
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": str(accelerator.device),
        },
        "resume": {
            "resumed": resumed,
            "input_sha256": resume_sha256,
            "start_epoch": start_epoch,
            "prior_manifest_sha256": prior_manifest_sha256,
            "epoch_record_source": resume_epoch_record_source,
            "prior_manifest_record_status": prior_manifest_record_status,
            "prior_epoch_ledger_status": prior_ledger_record_status,
        },
        "contract": config,
        "dataset_limits": {"train": args.train_limit, "val": args.val_limit},
        "prepared_dataset_contract_sha256": (
            None if prepared is None else bridge_hash(prepared)
        ),
        "completed_epoch": epoch_records[-1]["epoch"] if epoch_records else start_epoch,
        "global_step": global_step,
        "best_epoch": best_epoch,
        "best_val_score": best_score,
        "final_model_state_sha256": final_state_hash,
        "last_state_sha256": sha256_file(state_path) if state_path.exists() else None,
        "epoch_ledger_sha256": sha256_file(ledger_path) if ledger_path.exists() else None,
        "best_model_sha256": sha256_file(best_path) if best_path.exists() else None,
        "epoch_records": prior_epoch_records + epoch_records,
        "invocation_epoch_records": epoch_records,
        "elapsed_seconds": time.time() - started,
    }
    validate_epoch_records(
        manifest["epoch_records"],
        completed_epoch=manifest["completed_epoch"],
        global_step=manifest["global_step"],
        model_state_sha256=manifest["final_model_state_sha256"],
    )
    atomic_json_write(manifest, manifest_path)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
