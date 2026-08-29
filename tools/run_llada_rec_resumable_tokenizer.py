#!/usr/bin/env python3
"""Train the pinned LLaDA-Rec MultiHeadVQVAE on a frozen catalog."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

import numpy as np

try:
    from tools.run_diffgrm_resumable_training import (
        atomic_json_write, atomic_torch_save, capture_rng_state,
        restore_rng_state, sha256_file, sha256_state_dict, trusted_torch_load,
    )
except ModuleNotFoundError:  # Direct ``python tools/...`` execution.
    from run_diffgrm_resumable_training import (
        atomic_json_write, atomic_torch_save, capture_rng_state,
        restore_rng_state, sha256_file, sha256_state_dict, trusted_torch_load,
    )


REVISION = "83dbcd6061da9266adcd8f68b16d1de7cc2612f3"
RUNTIME_SCHEMA = "genrec_dormant.diffgrm_private_runtime.v1"
STATE_SCHEMA = "sidscope.llada_rec_tokenizer_state.v1"
MANIFEST_SCHEMA = "sidscope.llada_rec_tokenizer_training.v1"
SOURCE_HASHES = {
    "genrec/tokenizers/MultiHeadVQVAE/tokenizer.py":
        "377cc774bba53feb36f19f82fad69291d1c7f1890acaf9f2bd36cb9732b3b73a",
    "genrec/tokenizers/MultiHeadVQVAE/config.yaml":
        "e0850bcd283525200d7a6cc174b01c4b1f4d69f0c79b1bbfb11f83b847b74092",
}


def bindings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "source_revision": REVISION,
        "source_files_sha256": SOURCE_HASHES,
        "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
        "sentence_embeddings_sha256": sha256_file(args.sentence_embeddings),
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "domain": args.domain,
        "seed": args.seed,
        "catalog_rows": args.expected_catalog_rows,
        "embedding_dim": 768,
        "pca_dim": 128,
        "pca_whiten": True,
        "vq_n_codebooks": 4,
        "vq_codebook_size": 256,
        "vqvae_hidden_sizes": [512, 256],
        "vqvae_e_dim": 32,
        "vqvae_learning_rate": args.learning_rate,
        "vqvae_weight_decay": args.weight_decay,
        "vqvae_batch_size": args.batch_size,
        "vqvae_target_epochs": args.target_epochs,
        "vqvae_beta": 0.25,
        "vqvae_sinkhorn_epsilon": 0.003,
        "vqvae_sinkhorn_iters": 10,
        "kmeans_init": True,
        "kmeans_iters": 100,
        "selection_boundary": "frozen_train_only_catalog_only",
    }


def validate_source(source: Path) -> None:
    for relative, expected in SOURCE_HASHES.items():
        path = source / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"LLaDA-Rec pinned source mismatch: {relative}")


def validate_state(value: dict[str, Any], expected: dict[str, Any]) -> None:
    if value.get("schema") != STATE_SCHEMA or value.get("bindings") != expected:
        raise ValueError("LLaDA-Rec tokenizer resume binding mismatch")
    epochs = int(value.get("completed_epochs", -1))
    records = value.get("epoch_records", [])
    if epochs < 0 or epochs > int(expected["vqvae_target_epochs"]) or len(records) != epochs:
        raise ValueError("LLaDA-Rec tokenizer resume counters are inconsistent")
    if [int(row.get("epoch", -1)) for row in records] != list(range(1, epochs + 1)):
        raise ValueError("LLaDA-Rec tokenizer epoch ledger is not contiguous")
    for field in ("model", "optimizer", "rng_state"):
        if field not in value:
            raise ValueError(f"LLaDA-Rec tokenizer state lacks {field}")


def mark_quantizers_initialized(model: Any) -> None:
    for layer in model.vq.vq_layers:
        layer.initted = True


def collision_rate(model: Any, embeddings: Any, torch_module: Any, batch_size: int) -> float:
    model.eval()
    codes = []
    with torch_module.no_grad():
        for start in range(0, len(embeddings), batch_size):
            codes.append(model.get_indices(embeddings[start:start + batch_size], use_sk=False).cpu())
    values = torch_module.cat(codes).numpy()
    return 1.0 - len({tuple(int(x) for x in row) for row in values}) / len(values)


def generate_codes(model: Any, embeddings: Any, torch_module: Any, batch_size: int) -> np.ndarray:
    model.eval()
    chunks = []
    with torch_module.no_grad():
        for start in range(0, len(embeddings), batch_size):
            chunks.append(model.get_indices(embeddings[start:start + batch_size], use_sk=False).cpu())
        codes = torch_module.cat(chunks).numpy()
        for _ in range(30):
            groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
            for index, row in enumerate(codes):
                groups[tuple(int(x) for x in row)].append(index)
            collisions = [indices for indices in groups.values() if len(indices) > 1]
            if not collisions:
                break
            for indices in collisions:
                selected = embeddings[indices]
                replacement = model.get_indices(selected, use_sk=True).cpu().numpy()
                codes[np.asarray(indices)] = replacement
    return codes


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.device != "cuda":
        raise ValueError("real LLaDA-Rec tokenizer training requires CUDA")
    validate_source(args.upstream_source)
    runtime = json.loads(args.runtime_manifest.read_text(encoding="utf-8"))
    if runtime.get("schema") != RUNTIME_SCHEMA or runtime.get("domain") != args.domain:
        raise ValueError("LLaDA-Rec frozen runtime identity mismatch")
    catalog = runtime.get("catalog", [])
    if len(catalog) != args.expected_catalog_rows:
        raise ValueError("LLaDA-Rec catalog denominator mismatch")
    normalized_ids = [str(row["normalized_item_id"]) for row in catalog]
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("LLaDA-Rec normalized catalog identity is not unique")

    sys.path.insert(0, str(args.upstream_source.resolve()))
    import torch
    from sklearn.decomposition import PCA
    from torch.utils.data import DataLoader, TensorDataset
    from genrec.tokenizers.MultiHeadVQVAE.layers import MultiHeadVQVAE

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    raw = np.fromfile(args.sentence_embeddings, dtype=np.float32)
    expected_values = args.expected_catalog_rows * 768
    if raw.size != expected_values:
        raise ValueError("LLaDA-Rec sentence-embedding denominator mismatch")
    raw = raw.reshape(args.expected_catalog_rows, 768)
    pca = PCA(n_components=128, whiten=True)
    reduced = pca.fit_transform(raw).astype(np.float32, copy=False)
    device = torch.device(args.device)
    embeddings = torch.from_numpy(reduced).to(device)
    model = MultiHeadVQVAE(
        in_dim=128, num_emb_list=[256] * 4, e_dim=32, layers=[512, 256],
        dropout_prob=0.0, bn=False, loss_type="mse", quant_loss_weight=1.0,
        beta=0.25, kmeans_init=True, kmeans_iters=100,
        sk_epsilons=[0, 0, 0, 0.003], sk_iters=10,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    expected = bindings(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.output_dir / "last_state.pt"
    best_path = args.output_dir / "best_tokenizer.pt"
    records: list[dict[str, Any]] = []
    completed = 0
    best_collision = float("inf")
    best_epoch = 0
    resumed = False
    if state_path.is_file():
        if not args.resume_if_present:
            raise ValueError("existing LLaDA-Rec tokenizer state requires --resume-if-present")
        value = trusted_torch_load(torch, state_path, map_location=device)
        validate_state(value, expected)
        model.load_state_dict(value["model"], strict=True)
        mark_quantizers_initialized(model)
        optimizer.load_state_dict(value["optimizer"])
        restore_rng_state(torch, value["rng_state"])
        completed = int(value["completed_epochs"])
        records = list(value["epoch_records"])
        best_collision = float(value.get("best_collision_rate", float("inf")))
        best_epoch = int(value.get("best_epoch", 0))
        resumed = True
    started = time.time()
    invocation_start_epoch = completed
    dataset = TensorDataset(torch.from_numpy(reduced))
    while completed < args.target_epochs:
        epoch = completed + 1
        generator = torch.Generator().manual_seed(args.seed + epoch)
        loader = DataLoader(
            dataset, batch_size=args.batch_size, shuffle=True, generator=generator,
            num_workers=0, pin_memory=True,
        )
        model.train()
        losses: list[float] = []
        for (batch_cpu,) in loader:
            batch = batch_cpu.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            output, vq_loss, _, _ = model(batch)
            loss, _, _ = model.compute_loss(output, vq_loss, xs=batch)
            if not torch.isfinite(loss):
                raise ValueError("non-finite LLaDA-Rec tokenizer loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        completed = epoch
        record = {
            "epoch": epoch,
            "batches": len(losses),
            "mean_loss": sum(losses) / len(losses),
            "final_loss": losses[-1],
        }
        if epoch % args.validation_interval == 0 or epoch == args.target_epochs:
            observed_collision = collision_rate(model, embeddings, torch, args.batch_size)
            record["collision_rate"] = observed_collision
            if observed_collision < best_collision:
                best_collision = observed_collision
                best_epoch = epoch
                atomic_torch_save(torch, best_path, {
                    "model": model.state_dict(), "epoch": epoch,
                    "collision_rate": observed_collision, "bindings": expected,
                })
        records.append(record)
        stop_after_epoch = (
            completed < args.target_epochs
            and args.max_epochs_this_invocation is not None
            and completed - invocation_start_epoch >= args.max_epochs_this_invocation
        )
        if epoch % args.checkpoint_interval == 0 or epoch == args.target_epochs or stop_after_epoch:
            state = {
                "schema": STATE_SCHEMA, "bindings": expected,
                "completed_epochs": completed, "model": model.state_dict(),
                "optimizer": optimizer.state_dict(), "rng_state": capture_rng_state(torch),
                "epoch_records": records, "best_collision_rate": best_collision,
                "best_epoch": best_epoch,
            }
            atomic_torch_save(torch, state_path, state)
            atomic_json_write(args.output_dir / "state.json", {
                "schema": "sidscope.llada_rec_tokenizer_state_summary.v1",
                "status": "complete" if completed == args.target_epochs else "checkpointed",
                "completed_epochs": completed, "target_epochs": args.target_epochs,
                "best_epoch": best_epoch, "best_collision_rate": best_collision,
                "last_state_sha256": sha256_file(state_path), "last_epoch": record,
            })
        if completed % args.log_interval == 0 or completed == args.target_epochs:
            print(json.dumps({"event": "progress", **record}, sort_keys=True), flush=True)
        if stop_after_epoch:
            checkpointed = {
                "schema": MANIFEST_SCHEMA, "status": "checkpointed",
                "bindings": expected, "completed_epochs": completed,
                "best_epoch": best_epoch, "best_collision_rate": best_collision,
                "last_state_sha256": sha256_file(state_path),
                "epoch_records": records, "resumed": resumed,
                "elapsed_seconds_this_process": time.time() - started,
                "next_action": "rerun with --resume-if-present and identical frozen bindings",
            }
            atomic_json_write(args.output_dir / "invocation_manifest.json", checkpointed)
            return checkpointed

    best = trusted_torch_load(torch, best_path, map_location=device)
    if best.get("bindings") != expected:
        raise ValueError("LLaDA-Rec best-tokenizer binding mismatch")
    model.load_state_dict(best["model"], strict=True)
    mark_quantizers_initialized(model)
    codes = generate_codes(model, embeddings, torch, args.batch_size)
    semantic_ids = {
        normalized_id: [int(value) for value in row]
        for normalized_id, row in zip(normalized_ids, codes)
    }
    atomic_json_write(args.output_dir / "semantic_ids.json", semantic_ids)
    unique_codes = len({tuple(int(value) for value in row) for row in codes})
    manifest = {
        "schema": MANIFEST_SCHEMA, "status": "pass", "bindings": expected,
        "completed_epochs": completed, "best_epoch": int(best["epoch"]),
        "best_collision_rate": float(best["collision_rate"]),
        "checkpoint_reloaded_strict": True,
        "best_checkpoint_sha256": sha256_file(best_path),
        "last_state_sha256": sha256_file(state_path),
        "model_state_sha256": sha256_state_dict(model.state_dict()),
        "semantic_ids_sha256": sha256_file(args.output_dir / "semantic_ids.json"),
        "catalog_rows": len(codes), "unique_semantic_ids": unique_codes,
        "collision_excess": len(codes) - unique_codes,
        "epoch_records": records, "resumed": resumed,
        "elapsed_seconds_this_process": time.time() - started,
        "next_gate": "normalized item to position-offset vocabulary round-trip and generator smoke",
    }
    atomic_json_write(args.output_dir / "training_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--sentence-embeddings", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-catalog-rows", type=int, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--target-epochs", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--validation-interval", type=int, default=50)
    parser.add_argument("--checkpoint-interval", type=int, default=10)
    parser.add_argument("--log-interval", type=int, default=10)
    parser.add_argument("--resume-if-present", action="store_true")
    parser.add_argument("--max-epochs-this-invocation", type=int)
    args = parser.parse_args()
    for name in ("target_epochs", "batch_size", "validation_interval", "checkpoint_interval"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.max_epochs_this_invocation is not None and args.max_epochs_this_invocation < 1:
        parser.error("--max-epochs-this-invocation must be positive")
    return args


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
