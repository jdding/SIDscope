#!/usr/bin/env python3
"""Run a fixed-budget DiffGRM screen with epoch-boundary recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from typing import Any

import numpy as np


SOURCE_REVISION = "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c"
SOURCE_TREE_SHA256 = "f0c40bb3e62ab8d0514a455d805ee97b84fd3ab5424f37e992a5e05479ec83ce"
STATE_SCHEMA = "genrec_dormant.diffgrm_recoverable_state.v1"
MANIFEST_SCHEMA = "genrec_dormant.diffgrm_fixed_budget_training.v1"
STATE_SUMMARY_SCHEMA = "genrec_dormant.diffgrm_training_state_summary.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_state_dict(state: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tensor.dtype).encode("ascii"))
        digest.update(np.asarray(tensor.shape, dtype=np.int64).tobytes())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def atomic_torch_save(torch_module: Any, path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch_module.save(payload, temporary)
    os.replace(temporary, path)


def trusted_torch_load(torch_module: Any, path: Path, *, map_location: Any) -> dict[str, Any]:
    """Load only this runner's hash-bound state, including non-tensor RNG objects."""

    try:
        value = torch_module.load(path, map_location=map_location, weights_only=False)
    except TypeError:  # PyTorch before the weights_only argument.
        value = torch_module.load(path, map_location=map_location)
    if not isinstance(value, dict):
        raise ValueError("DiffGRM checkpoint payload must be an object")
    return value


def capture_rng_state(torch_module: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch_module.get_rng_state(),
    }
    if torch_module.cuda.is_available():
        value["torch_cuda"] = torch_module.cuda.get_rng_state_all()
    return value


def restore_rng_state(torch_module: Any, value: dict[str, Any]) -> None:
    random.setstate(value["python"])
    np.random.set_state(value["numpy"])
    # A CUDA map_location is correct for model and optimizer tensors but also
    # moves the serialized CPU RNG ByteTensor. PyTorch requires RNG state
    # tensors on CPU even when training on CUDA.
    torch_module.set_rng_state(value["torch_cpu"].cpu())
    if torch_module.cuda.is_available() and "torch_cuda" in value:
        torch_module.cuda.set_rng_state_all(
            [state.cpu() for state in value["torch_cuda"]]
        )


def expected_bindings(args: argparse.Namespace) -> dict[str, Any]:
    tools_dir = Path(__file__).resolve().parent
    if len(args.entrypoint_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in args.entrypoint_sha256
    ):
        raise ValueError("entrypoint SHA-256 must be lowercase hexadecimal")
    return {
        "source_revision": SOURCE_REVISION,
        "source_tree_sha256": SOURCE_TREE_SHA256,
        "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
        "prepared_dataset_sha256": sha256_file(args.prepared_dataset),
        "semantic_id_cache_sha256": sha256_file(args.semantic_id_cache),
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "processed_cache_manifest_sha256": sha256_file(args.processed_cache_manifest),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "dataset_bridge_sha256": sha256_file(tools_dir / "diffgrm_prepared_dataset.py"),
        "runtime_helper_sha256": sha256_file(tools_dir / "run_diffgrm_runtime.py"),
        "entrypoint_sha256": args.entrypoint_sha256,
        "domain": args.domain,
        "seed": args.seed,
        "target_steps": args.target_steps,
        "train_batch_size": args.train_batch_size,
        "learning_rate": args.learning_rate,
        "warmup_steps": args.warmup_steps,
        "scheduler": "cosine",
        "screening_boundary": "fixed_update_screen_not_convergence_study",
    }


def validate_resume_payload(
    payload: dict[str, Any], bindings: dict[str, Any], *, verify_model_hash: bool = True
) -> None:
    if payload.get("schema") != STATE_SCHEMA:
        raise ValueError("DiffGRM resume-state schema mismatch")
    if payload.get("bindings") != bindings:
        raise ValueError("DiffGRM resume-state frozen bindings mismatch")
    steps = int(payload.get("completed_steps", -1))
    epochs = int(payload.get("completed_epochs", -1))
    records = payload.get("epoch_records", [])
    if steps < 0 or steps > int(bindings["target_steps"]) or epochs < 0 or len(records) != epochs:
        raise ValueError("DiffGRM resume-state counters are inconsistent")
    for field in ("model", "optimizer", "scheduler", "rng_state"):
        if field not in payload:
            raise ValueError(f"DiffGRM resume state lacks {field}")
    previous = 0
    for expected_epoch, record in enumerate(records, start=1):
        if int(record.get("epoch", -1)) != expected_epoch:
            raise ValueError("DiffGRM epoch records are not contiguous")
        if int(record.get("completed_steps", -1)) <= previous:
            raise ValueError("DiffGRM epoch step records are not increasing")
        previous = int(record["completed_steps"])
    if records and previous != steps:
        raise ValueError("DiffGRM epoch records do not reach the resume step")
    if records and verify_model_hash:
        observed_model_hash = sha256_state_dict(payload["model"])
        if records[-1].get("model_state_sha256") != observed_model_hash:
            raise ValueError("DiffGRM resume model does not match the final epoch record")


def model_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "dataset": "DormantPreparedDataset",
        "category": args.domain,
        "cache_dir": str(args.cache_dir),
        "log_dir": str(args.output_dir / "logs"),
        "tensorboard_log_dir": str(args.output_dir / "tensorboard"),
        "rand_seed": args.seed,
        "num_proc": 1,
        "device": "cuda",
        "n_digit": 4,
        "codebook_size": 256,
        "masking_strategy": "guided",
        "guided_refresh_each_step": False,
        "guided_select": "least",
        "guided_conf_metric": "msp",
        "encoder_n_layer": 1,
        "decoder_n_layer": 4,
        "n_head": 4,
        "n_embd": 256,
        "n_inner": 1024,
        "max_history_len": 50,
        "train_sliding": False,
        "lr": args.learning_rate,
        "weight_decay": 0.0,
        "warmup_steps": args.warmup_steps,
        "label_smoothing": 0.1,
        "sent_emb_model": "sentence-transformers/sentence-t5-base",
        "sent_emb_dim": 768,
        "sent_emb_pca": 256,
        "normalize_after_pca": True,
        "sent_emb_batch_size": 256,
        "sid_quantizer": "opq_pq",
        "opq_use_gpu": False,
        "faiss_omp_num_threads": args.faiss_threads,
        "force_regenerate_opq": False,
        "share_decoder_output_embedding": True,
        "beam_search_modes": ["confidence"],
        "topk": [5, 10],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.device != "cuda":
        raise ValueError("formal DiffGRM screen requires CUDA")
    sys.path.insert(0, str(args.upstream_source.resolve()))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import torch
    from accelerate import Accelerator
    from torch.nn.utils import clip_grad_norm_
    from torch.optim import AdamW
    from torch.utils.data import DataLoader
    from transformers.optimization import get_scheduler
    from genrec.utils import get_config, init_seed
    from genrec.models.DIFF_GRM.model import DIFF_GRM
    from genrec.models.DIFF_GRM.tokenizer import DIFF_GRMTokenizer
    from diffgrm_prepared_dataset import DormantPreparedDataset
    from run_diffgrm_runtime import verify_processed_cache

    if (args.upstream_source / ".pinned-revision").read_text().strip() != SOURCE_REVISION:
        raise ValueError("DiffGRM source revision mismatch")
    cache_manifest = verify_processed_cache(args.cache_dir, args.processed_cache_manifest)
    semantic_id_filename = cache_manifest["semantic_id_filename"]
    if args.semantic_id_cache.name != semantic_id_filename:
        raise ValueError("DiffGRM Semantic-ID cache filename differs from manifest")
    if sha256_file(args.semantic_id_cache) != cache_manifest["files"][semantic_id_filename]:
        raise ValueError("DiffGRM semantic-ID cache mismatch")
    if int(cache_manifest.get("catalog_rows", -1)) != args.expected_catalog_rows:
        raise ValueError("DiffGRM processed-cache catalog denominator mismatch")
    bindings = expected_bindings(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.output_dir / "last_state.pt"
    state_summary_path = args.output_dir / "state.json"
    final_checkpoint_path = args.output_dir / "formal_checkpoint.pt"
    manifest_path = args.output_dir / "training_manifest.json"
    invocation_manifest_path = args.output_dir / "invocation_manifest.json"

    init_seed(args.seed, True)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    config = get_config("DIFF_GRM", "AmazonReviews2014", None, model_overrides(args))
    config["accelerator"] = Accelerator()
    config["device"] = torch.device(args.device)
    dataset = DormantPreparedDataset(config, args.runtime_manifest)
    tokenizer = DIFF_GRMTokenizer(config, dataset)
    tokenized = tokenizer.tokenize(dataset.split())
    train = tokenized["train"]
    if len(train) != args.expected_train_rows:
        raise ValueError(
            f"DiffGRM train denominator mismatch: expected {args.expected_train_rows}, observed {len(train)}"
        )
    model = DIFF_GRM(config, dataset, tokenizer).to(config["device"])
    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.0)
    scheduler = get_scheduler(
        "cosine",
        optimizer=optimizer,
        num_warmup_steps=args.warmup_steps,
        num_training_steps=args.target_steps,
    )
    completed_steps = 0
    completed_epochs = 0
    epoch_records: list[dict[str, Any]] = []
    resumed = False
    if state_path.is_file():
        if not args.resume_if_present:
            raise ValueError("existing DiffGRM state requires --resume-if-present")
        payload = trusted_torch_load(torch, state_path, map_location=config["device"])
        validate_resume_payload(payload, bindings)
        model.load_state_dict(payload["model"], strict=True)
        optimizer.load_state_dict(payload["optimizer"])
        scheduler.load_state_dict(payload["scheduler"])
        completed_steps = int(payload["completed_steps"])
        completed_epochs = int(payload["completed_epochs"])
        epoch_records = list(payload["epoch_records"])
        restore_rng_state(torch, payload["rng_state"])
        resumed = True
    started_at = time.time()
    invocation_epochs = 0
    model.train()
    while completed_steps < args.target_steps:
        epoch = completed_epochs + 1
        generator = torch.Generator().manual_seed(args.seed + epoch)
        loader = DataLoader(
            train,
            batch_size=args.train_batch_size,
            shuffle=True,
            generator=generator,
            collate_fn=tokenizer.collate_fn["train"],
            num_workers=0,
        )
        losses: list[float] = []
        for batch in loader:
            if completed_steps >= args.target_steps:
                break
            batch = {key: value.to(config["device"]) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            output = model(batch, return_loss=True)
            if not torch.isfinite(output.loss):
                raise ValueError("non-finite loss in formal DiffGRM training")
            output.loss.backward()
            clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            completed_steps += 1
            losses.append(float(output.loss.detach().cpu()))
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
            raise ValueError("formal DiffGRM epoch completed no batches")
        completed_epochs += 1
        model_hash = sha256_state_dict(model.state_dict())
        epoch_records.append({
            "epoch": completed_epochs,
            "completed_steps": completed_steps,
            "batches": len(losses),
            "mean_loss": sum(losses) / len(losses),
            "final_loss": losses[-1],
            "learning_rate": scheduler.get_last_lr()[0],
            "model_state_sha256": model_hash,
        })
        state = {
            "schema": STATE_SCHEMA,
            "status": "complete" if completed_steps == args.target_steps else "checkpointed",
            "bindings": bindings,
            "completed_steps": completed_steps,
            "completed_epochs": completed_epochs,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "rng_state": capture_rng_state(torch),
            "epoch_records": epoch_records,
        }
        atomic_torch_save(torch, state_path, state)
        atomic_json_write(state_summary_path, {
            "schema": STATE_SUMMARY_SCHEMA,
            "status": state["status"],
            "completed_steps": completed_steps,
            "target_steps": args.target_steps,
            "completed_epochs": completed_epochs,
            "last_state_sha256": sha256_file(state_path),
            "model_state_sha256": model_hash,
            "last_epoch": epoch_records[-1],
        })
        invocation_epochs += 1
        if (
            completed_steps < args.target_steps
            and args.max_epochs_this_invocation is not None
            and invocation_epochs >= args.max_epochs_this_invocation
        ):
            checkpointed = {
                "schema": MANIFEST_SCHEMA,
                "status": "checkpointed",
                "scientific_scope": "single_seed_fixed_update_family_screen_not_convergence_study",
                "bindings": bindings,
                "completed_steps": completed_steps,
                "completed_epochs": completed_epochs,
                "train_rows": len(train),
                "last_state_sha256": sha256_file(state_path),
                "model_state_sha256": model_hash,
                "epoch_records": epoch_records,
                "resumed": resumed,
                "elapsed_seconds_this_process": time.time() - started_at,
                "next_action": "rerun with --resume-if-present and the same frozen bindings",
            }
            atomic_json_write(invocation_manifest_path, checkpointed)
            return checkpointed

    final_payload = {
        "model": model.state_dict(),
        "completed_steps": completed_steps,
        "completed_epochs": completed_epochs,
        "model_state_sha256": epoch_records[-1]["model_state_sha256"],
        "bindings": bindings,
    }
    atomic_torch_save(torch, final_checkpoint_path, final_payload)
    final_checkpoint_sha256 = sha256_file(final_checkpoint_path)
    reloaded = trusted_torch_load(torch, final_checkpoint_path, map_location=config["device"])
    reloaded_model = DIFF_GRM(config, dataset, tokenizer).to(config["device"])
    reloaded_model.load_state_dict(reloaded["model"], strict=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "status": "pass",
        "scientific_scope": "single_seed_fixed_update_family_screen_not_convergence_study",
        "bindings": bindings,
        "completed_steps": completed_steps,
        "completed_epochs": completed_epochs,
        "train_rows": len(train),
        "checkpoint_reloaded_strict": True,
        "formal_checkpoint_sha256": final_checkpoint_sha256,
        "last_state_sha256": sha256_file(state_path),
        "model_state_sha256": epoch_records[-1]["model_state_sha256"],
        "epoch_records": epoch_records,
        "resumed": resumed,
        "elapsed_seconds_this_process": time.time() - started_at,
        "next_gate": "checkpoint-bound one-per-bucket trace then exact 250-row balanced native diagnostic",
    }
    atomic_json_write(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--prepared-dataset", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--entrypoint-sha256", required=True)
    parser.add_argument("--semantic-id-cache", type=Path, required=True)
    parser.add_argument("--processed-cache-manifest", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--expected-train-rows", type=int, required=True)
    parser.add_argument("--expected-catalog-rows", type=int, required=True)
    parser.add_argument("--target-steps", type=int, default=10000)
    parser.add_argument("--train-batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--warmup-steps", type=int, default=10000)
    parser.add_argument("--faiss-threads", type=int, default=32)
    parser.add_argument("--log-interval", type=int, default=25)
    parser.add_argument("--resume-if-present", action="store_true")
    parser.add_argument(
        "--max-epochs-this-invocation",
        type=int,
        help="Operational interruption boundary; excluded from frozen scientific bindings.",
    )
    args = parser.parse_args()
    if args.max_epochs_this_invocation is not None and args.max_epochs_this_invocation < 1:
        parser.error("--max-epochs-this-invocation must be positive")
    return args


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
