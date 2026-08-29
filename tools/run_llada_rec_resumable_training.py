#!/usr/bin/env python3
"""Run fixed-update LLaDA-Rec training with epoch-boundary recovery."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Iterator

import numpy as np

try:
    from tools.run_diffgrm_resumable_training import (
        atomic_json_write,
        atomic_torch_save,
        capture_rng_state,
        restore_rng_state,
        sha256_file,
        sha256_state_dict,
        trusted_torch_load,
    )
except ModuleNotFoundError:
    from run_diffgrm_resumable_training import (
        atomic_json_write,
        atomic_torch_save,
        capture_rng_state,
        restore_rng_state,
        sha256_file,
        sha256_state_dict,
        trusted_torch_load,
    )


SOURCE_REVISION = "83dbcd6061da9266adcd8f68b16d1de7cc2612f3"
RUNTIME_SCHEMA = "genrec_dormant.diffgrm_private_runtime.v1"
STATE_SCHEMA = "sidscope.llada_rec_generator_state.v1"
MANIFEST_SCHEMA = "sidscope.llada_rec_generator_training.v1"
SUMMARY_SCHEMA = "sidscope.llada_rec_generator_state_summary.v1"
SOURCE_HASHES = {
    "LLaDA/modeling_llada.py":
        "3b02d8a29d199295cee4ec3e55ee6892d110091b3d99e9720bed7fdca7ea1f36",
    "genrec/models/LLaDARec/config.yaml":
        "17362d7b1c34ec7e7a52713087bd71e7084eb8e081bf54a823c0fef274706b5a",
    "genrec/models/LLaDARec/model.py":
        "280b0332e1bef6ee3ae40011a9e481102f158a55e02118a492e8f1087f681133",
    "genrec/models/LLaDARec/tokenizer.py":
        "ff887fa391b6063c8bf4e777d295fdb8826d443dbb1aa7446d295b2d37c6e6e8",
    "genrec/tokenizers/MultiHeadVQVAE/config.yaml":
        "e0850bcd283525200d7a6cc174b01c4b1f4d69f0c79b1bbfb11f83b847b74092",
    "genrec/tokenizers/MultiHeadVQVAE/tokenizer.py":
        "377cc774bba53feb36f19f82fad69291d1c7f1890acaf9f2bd36cb9732b3b73a",
}


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def validate_source(source: Path) -> None:
    for relative, expected in SOURCE_HASHES.items():
        path = source / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"LLaDA-Rec pinned source mismatch: {relative}")


def load_semantic_ids(
    runtime_manifest: Path, semantic_ids_path: Path, *, expected_catalog_rows: int
) -> tuple[dict[str, list[int]], dict[str, Any]]:
    runtime = json.loads(runtime_manifest.read_text(encoding="utf-8"))
    if runtime.get("schema") != RUNTIME_SCHEMA:
        raise ValueError("LLaDA-Rec frozen runtime schema mismatch")
    catalog = runtime.get("catalog", [])
    if len(catalog) != expected_catalog_rows:
        raise ValueError("LLaDA-Rec frozen catalog denominator mismatch")
    normalized_to_runtime = {
        str(row["normalized_item_id"]): str(row["runtime_item_key"])
        for row in catalog
    }
    if len(normalized_to_runtime) != expected_catalog_rows:
        raise ValueError("LLaDA-Rec frozen catalog identity is not unique")
    semantic = json.loads(semantic_ids_path.read_text(encoding="utf-8"))
    if not isinstance(semantic, dict) or set(semantic) != set(normalized_to_runtime):
        raise ValueError("LLaDA-Rec semantic-ID catalog binding mismatch")
    runtime_codes: dict[str, list[int]] = {}
    groups: dict[tuple[int, ...], int] = {}
    for normalized_id, runtime_key in normalized_to_runtime.items():
        codes = semantic[normalized_id]
        if (
            not isinstance(codes, list)
            or len(codes) != 4
            or any(not isinstance(code, int) or code < 0 or code >= 256 for code in codes)
        ):
            raise ValueError("LLaDA-Rec semantic-ID row violates the 4x256 contract")
        runtime_codes[runtime_key] = list(codes)
        key = tuple(codes)
        groups[key] = groups.get(key, 0) + 1
    unique = len(groups)
    return runtime_codes, {
        "catalog_rows": expected_catalog_rows,
        "unique_semantic_ids": unique,
        "collision_excess": expected_catalog_rows - unique,
        "collision_group_count": sum(count > 1 for count in groups.values()),
        "max_collision_group_size": max(groups.values()),
    }


def expected_bindings(args: argparse.Namespace) -> dict[str, Any]:
    tools_dir = Path(__file__).resolve().parent
    return {
        "source_revision": SOURCE_REVISION,
        "source_files_sha256": SOURCE_HASHES,
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
        "prepared_dataset_sha256": sha256_file(args.prepared_dataset),
        "tokenizer_training_manifest_sha256": sha256_file(
            args.tokenizer_training_manifest
        ),
        "semantic_ids_sha256": sha256_file(args.semantic_ids),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "dataset_bridge_sha256": sha256_file(
            tools_dir / "llada_rec_prepared_dataset.py"
        ),
        "domain": args.domain,
        "catalog_rows": args.expected_catalog_rows,
        "tokenized_train_rows": args.expected_train_rows,
        "seed": args.seed,
        "target_steps": args.target_steps,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "warmup_steps": args.warmup_steps,
        "scheduler": "cosine",
        "architecture": {
            "max_item_seq_len": 20,
            "d_model": 256,
            "mlp_ratio": 4,
            "n_layers": 6,
            "n_heads": 8,
            "n_kv_heads": 8,
            "dropout_rate": 0.1,
            "history_mask_weight": 5.0,
            "generation_steps": 4,
            "test_beams": 50,
            "temperature": 1.0,
        },
        "training_boundary": "single_seed_fixed_update_screen_not_convergence_study",
    }


def validate_resume_payload(
    payload: dict[str, Any], bindings: dict[str, Any], *, verify_model_hash: bool = True
) -> None:
    if payload.get("schema") != STATE_SCHEMA or payload.get("bindings") != bindings:
        raise ValueError("LLaDA-Rec generator resume binding mismatch")
    steps = int(payload.get("completed_steps", -1))
    epochs = int(payload.get("completed_epochs", -1))
    records = payload.get("epoch_records", [])
    if steps < 0 or steps > int(bindings["target_steps"]) or epochs < 0:
        raise ValueError("LLaDA-Rec generator resume counters are inconsistent")
    if not isinstance(records, list) or len(records) != epochs:
        raise ValueError("LLaDA-Rec generator epoch ledger length mismatch")
    for field in ("model", "optimizer", "scheduler", "rng_state"):
        if field not in payload:
            raise ValueError(f"LLaDA-Rec generator resume state lacks {field}")
    previous = 0
    for expected_epoch, record in enumerate(records, start=1):
        if int(record.get("epoch", -1)) != expected_epoch:
            raise ValueError("LLaDA-Rec generator epoch ledger is not contiguous")
        current = int(record.get("completed_steps", -1))
        if current <= previous:
            raise ValueError("LLaDA-Rec generator epoch steps are not increasing")
        previous = current
    if records and previous != steps:
        raise ValueError("LLaDA-Rec generator epoch ledger does not reach resume step")
    if records and verify_model_hash:
        if records[-1].get("model_state_sha256") != sha256_state_dict(
            payload["model"]
        ):
            raise ValueError("LLaDA-Rec generator resume model hash mismatch")


def model_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "category": args.domain,
        "cache_dir": str(args.output_dir / "cache"),
        "base_result_dir": str(args.output_dir / "official_cache"),
        "log_dir": "logs",
        "tensorboard_log_dir": str(args.output_dir / "tensorboard"),
        "run_id": "sidscope_llada_rec",
        "run_time": "frozen",
        "rand_seed": args.seed,
        "reproducibility": True,
        "num_proc": 1,
        "metadata": "sentence",
        "tokenizer_name": "MultiHeadVQVAE",
        "sem_ids_path": "formal.sem_ids",
        "max_item_seq_len": 20,
        "lr": args.learning_rate,
        "weight_decay": args.weight_decay,
        "dropout_rate": 0.1,
        "d_model": 256,
        "mlp_ratio": 4,
        "n_layers": 6,
        "n_heads": 8,
        "n_kv_heads": 8,
        "his_mask_w": 5.0,
        "gen_steps": 4,
        "val_num_beams": 1,
        "num_beams": 50,
        "temperature": 1.0,
        "vq_n_codebooks": 4,
        "vq_codebook_size": 256,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.device != "cuda":
        raise ValueError("real LLaDA-Rec generator training requires CUDA")
    validate_source(args.upstream_source)
    tokenizer_manifest = json.loads(
        args.tokenizer_training_manifest.read_text(encoding="utf-8")
    )
    if (
        tokenizer_manifest.get("schema") != "sidscope.llada_rec_tokenizer_training.v1"
        or tokenizer_manifest.get("status") != "pass"
        or tokenizer_manifest.get("semantic_ids_sha256")
        != sha256_file(args.semantic_ids)
    ):
        raise ValueError("LLaDA-Rec formal tokenizer manifest binding mismatch")
    prepared = json.loads(args.prepared_dataset.read_text(encoding="utf-8"))
    if (
        prepared.get("schema") != "sidscope.llada_rec_prepared_dataset.v1"
        or prepared.get("source_revision") != SOURCE_REVISION
        or prepared.get("train_observed_catalog_count") != args.expected_catalog_rows
        or prepared.get("semantic_ids_sha256") != sha256_file(args.semantic_ids)
    ):
        raise ValueError("LLaDA-Rec prepared dataset binding mismatch")
    runtime_codes, sid_summary = load_semantic_ids(
        args.runtime_manifest,
        args.semantic_ids,
        expected_catalog_rows=args.expected_catalog_rows,
    )

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(args.upstream_source.resolve()))
    sys.path.insert(0, str((repo_root / "tools").resolve()))
    import torch
    from accelerate import Accelerator
    from torch.nn.utils import clip_grad_norm_
    from torch.optim import AdamW
    from torch.utils.data import DataLoader
    from transformers.optimization import get_scheduler
    from genrec.models.LLaDARec.model import LLaDARec
    from genrec.models.LLaDARec.tokenizer import LLaDARecTokenizer
    from genrec.utils import get_config, init_seed
    from llada_rec_prepared_dataset import DormantPreparedLLaDADataset

    args.output_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.output_dir / "last_state.pt"
    state_summary_path = args.output_dir / "state.json"
    final_checkpoint_path = args.output_dir / "formal_checkpoint.pt"
    manifest_path = args.output_dir / "training_manifest.json"
    invocation_manifest_path = args.output_dir / "invocation_manifest.json"
    expected = expected_bindings(args)

    init_seed(args.seed, True)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    config = get_config("LLaDARec", "AmazonReviews2023", None, model_overrides(args))
    config["accelerator"] = Accelerator()
    config["device"] = torch.device(args.device)
    dataset = DormantPreparedLLaDADataset(config, args.runtime_manifest)

    semantic_cache = (
        Path(config["base_result_dir"])
        / f"{config['dataset']}_{config['category']}"
        / f"TokenModel_Seq-{config['max_item_seq_len']}_{config['tokenizer_name']}"
        / "sem_ids"
        / str(config["sem_ids_path"])
    )
    atomic_json_write(semantic_cache, runtime_codes)
    with working_directory(args.upstream_source):
        tokenizer = LLaDARecTokenizer(config, dataset)
    tokenized = tokenizer.tokenize({"train": dataset.split()["train"]})["train"]
    if len(tokenized) != args.expected_train_rows:
        raise ValueError(
            "LLaDA-Rec tokenized train denominator mismatch: "
            f"expected {args.expected_train_rows}, observed {len(tokenized)}"
        )
    model = LLaDARec(config, dataset, tokenizer).to(config["device"])
    optimizer = AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    scheduler = get_scheduler(
        "cosine",
        optimizer=optimizer,
        num_warmup_steps=args.warmup_steps,
        num_training_steps=args.target_steps,
    )
    completed_steps = 0
    completed_epochs = 0
    records: list[dict[str, Any]] = []
    resumed = False
    if state_path.is_file():
        if not args.resume_if_present:
            raise ValueError("existing LLaDA-Rec generator state requires --resume-if-present")
        payload = trusted_torch_load(torch, state_path, map_location=config["device"])
        validate_resume_payload(payload, expected)
        model.load_state_dict(payload["model"], strict=True)
        optimizer.load_state_dict(payload["optimizer"])
        scheduler.load_state_dict(payload["scheduler"])
        restore_rng_state(torch, payload["rng_state"])
        completed_steps = int(payload["completed_steps"])
        completed_epochs = int(payload["completed_epochs"])
        records = list(payload["epoch_records"])
        resumed = True

    started = time.time()
    invocation_epochs = 0
    model.train()
    while completed_steps < args.target_steps:
        epoch = completed_epochs + 1
        generator = torch.Generator().manual_seed(args.seed + epoch)
        loader = DataLoader(
            tokenized,
            batch_size=args.batch_size,
            shuffle=True,
            generator=generator,
            collate_fn=tokenizer.collate_fn["train"],
            num_workers=0,
        )
        losses: list[float] = []
        history_losses: list[float] = []
        target_losses: list[float] = []
        for batch in loader:
            if completed_steps >= args.target_steps:
                break
            batch = {key: value.to(config["device"]) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            output = model(batch)
            if not torch.isfinite(output.loss):
                raise ValueError("non-finite loss in LLaDA-Rec generator training")
            output.loss.backward()
            clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            completed_steps += 1
            losses.append(float(output.loss.detach().cpu()))
            history_losses.append(float(output.his_mask_loss.detach().cpu()))
            target_losses.append(float(output.target_mask_loss.detach().cpu()))
            if completed_steps % args.log_interval == 0 or completed_steps == args.target_steps:
                print(json.dumps({
                    "event": "progress",
                    "epoch": epoch,
                    "completed_steps": completed_steps,
                    "target_steps": args.target_steps,
                    "loss": losses[-1],
                    "learning_rate": scheduler.get_last_lr()[0],
                }, sort_keys=True), flush=True)
        if not losses:
            raise ValueError("LLaDA-Rec generator epoch completed no batches")
        completed_epochs += 1
        model_hash = sha256_state_dict(model.state_dict())
        records.append({
            "epoch": completed_epochs,
            "completed_steps": completed_steps,
            "batches": len(losses),
            "mean_loss": sum(losses) / len(losses),
            "final_loss": losses[-1],
            "mean_history_mask_loss": sum(history_losses) / len(history_losses),
            "mean_target_mask_loss": sum(target_losses) / len(target_losses),
            "learning_rate": scheduler.get_last_lr()[0],
            "model_state_sha256": model_hash,
        })
        state = {
            "schema": STATE_SCHEMA,
            "status": "complete" if completed_steps == args.target_steps else "checkpointed",
            "bindings": expected,
            "completed_steps": completed_steps,
            "completed_epochs": completed_epochs,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "rng_state": capture_rng_state(torch),
            "epoch_records": records,
        }
        atomic_torch_save(torch, state_path, state)
        atomic_json_write(state_summary_path, {
            "schema": SUMMARY_SCHEMA,
            "status": state["status"],
            "completed_steps": completed_steps,
            "target_steps": args.target_steps,
            "completed_epochs": completed_epochs,
            "last_state_sha256": sha256_file(state_path),
            "model_state_sha256": model_hash,
            "last_epoch": records[-1],
        })
        invocation_epochs += 1
        if (
            completed_steps < args.target_steps
            and args.max_epochs_this_invocation is not None
            and invocation_epochs >= args.max_epochs_this_invocation
        ):
            result = {
                "schema": MANIFEST_SCHEMA,
                "status": "checkpointed",
                "bindings": expected,
                "semantic_id_summary": sid_summary,
                "completed_steps": completed_steps,
                "completed_epochs": completed_epochs,
                "tokenized_train_rows": len(tokenized),
                "last_state_sha256": sha256_file(state_path),
                "model_state_sha256": model_hash,
                "epoch_records": records,
                "resumed": resumed,
                "elapsed_seconds_this_process": time.time() - started,
                "next_action": "rerun with --resume-if-present and identical bindings",
            }
            atomic_json_write(invocation_manifest_path, result)
            return result

    final_payload = {
        "model": model.state_dict(),
        "completed_steps": completed_steps,
        "completed_epochs": completed_epochs,
        "model_state_sha256": records[-1]["model_state_sha256"],
        "bindings": expected,
    }
    atomic_torch_save(torch, final_checkpoint_path, final_payload)
    checkpoint_sha256 = sha256_file(final_checkpoint_path)
    reloaded = trusted_torch_load(torch, final_checkpoint_path, map_location=config["device"])
    reloaded_model = LLaDARec(config, dataset, tokenizer).to(config["device"])
    reloaded_model.load_state_dict(reloaded["model"], strict=True)
    if sha256_state_dict(reloaded_model.state_dict()) != reloaded["model_state_sha256"]:
        raise ValueError("LLaDA-Rec strict checkpoint reload hash mismatch")
    result = {
        "schema": MANIFEST_SCHEMA,
        "status": "pass",
        "scientific_scope": "single_seed_fixed_update_family_screen_not_convergence_study",
        "bindings": expected,
        "semantic_id_summary": sid_summary,
        "completed_steps": completed_steps,
        "completed_epochs": completed_epochs,
        "tokenized_train_rows": len(tokenized),
        "checkpoint_sha256": checkpoint_sha256,
        "last_state_sha256": sha256_file(state_path),
        "model_state_sha256": records[-1]["model_state_sha256"],
        "checkpoint_reloaded_strict": True,
        "epoch_records": records,
        "resumed": resumed,
        "elapsed_seconds_this_process": time.time() - started,
        "next_gate": "checkpoint_bound_five_episode_native_trace",
    }
    atomic_json_write(manifest_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--prepared-dataset", type=Path, required=True)
    parser.add_argument("--tokenizer-training-manifest", type=Path, required=True)
    parser.add_argument("--semantic-ids", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--domain", default="amazon_vg")
    parser.add_argument("--expected-catalog-rows", type=int, required=True)
    parser.add_argument("--expected-train-rows", type=int, required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--target-steps", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    parser.add_argument("--warmup-steps", type=int, default=1000)
    parser.add_argument("--log-interval", type=int, default=10)
    parser.add_argument("--max-epochs-this-invocation", type=int)
    parser.add_argument("--resume-if-present", action="store_true")
    args = parser.parse_args()
    if args.max_epochs_this_invocation is not None and args.max_epochs_this_invocation < 1:
        parser.error("--max-epochs-this-invocation must be positive")
    return args


def main() -> None:
    result = run(parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
