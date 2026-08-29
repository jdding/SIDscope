#!/usr/bin/env python3
"""Construct and bounded-smoke the pinned official DiffGRM on prepared data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


REVISION = "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c"
LEGACY_VG_CACHE_FILES = {
    "item_id2tokens_sentence-t5-base_pca256_OPQ4,IVF1,PQ4x8_4d.npy": "84c2f41d9b9001d3ba3461fad552967655d09a4c322ed5c1ec57698b3d45b561",
    "sentence-t5-base_pca256.sent_emb": "e5c7cec648a5094d0c3a0ddc3e216133bb95d73b9b688b6790a057ca542adcfa",
    "sentence-t5-base_pca256_OPQ4,IVF1,PQ4x8.sem_ids": "202842cfa4f6e7df1119a57dde8915f7d4ab540bbe2fdfd60e30596c2219b7fc",
    "sentence-t5-base_raw_d768.sent_emb": "9bc9af0069852fe26fb94c7a6ff9e7b2a00c4e16049d3e762367dbc6ab8d386a",
    "tokens2item_sentence-t5-base_pca256_OPQ4,IVF1,PQ4x8_4d.pkl": "bac7e88f46a8eb015bc6a371f196f387be41b52583e10c7eb00c6ffc510ea8bf",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def materialize(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(source) != sha256_file(destination):
            raise ValueError("existing DiffGRM embedding cache hash mismatch")
        return
    try:
        os.link(source, destination)
    except OSError:
        shutil.copyfile(source, destination)


def verify_processed_cache(
    cache_dir: Path, manifest_path: Path | None = None
) -> dict[str, Any]:
    if manifest_path is None:
        manifest = {
            "schema": "sidscope.diffgrm_processed_cache_manifest.v1",
            "domain": "amazon_vg",
            "source_revision": REVISION,
            "files": LEGACY_VG_CACHE_FILES,
            "semantic_id_filename": "sentence-t5-base_pca256_OPQ4,IVF1,PQ4x8.sem_ids",
        }
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "sidscope.diffgrm_processed_cache_manifest.v1":
        raise ValueError("DiffGRM processed-cache manifest schema mismatch")
    if manifest.get("source_revision") != REVISION:
        raise ValueError("DiffGRM processed-cache source revision mismatch")
    expected = manifest.get("files")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("DiffGRM processed-cache manifest has no files")
    processed = cache_dir / "processed"
    observed = {path.name for path in processed.iterdir() if path.is_file()}
    if observed != set(expected):
        raise ValueError("DiffGRM processed cache file set mismatch")
    for filename, expected_sha256 in expected.items():
        if sha256_file(processed / filename) != expected_sha256:
            raise ValueError(f"DiffGRM processed cache hash mismatch: {filename}")
    semantic_id_filename = manifest.get("semantic_id_filename")
    if semantic_id_filename not in expected or not str(semantic_id_filename).endswith(".sem_ids"):
        raise ValueError("DiffGRM processed-cache semantic-ID filename mismatch")
    return manifest


def write_processed_cache_manifest(
    cache_dir: Path, output: Path, *, domain: str, catalog_rows: int
) -> dict[str, Any]:
    processed = cache_dir / "processed"
    files = {
        path.name: sha256_file(path)
        for path in sorted(processed.iterdir())
        if path.is_file()
    }
    semantic_ids = [name for name in files if name.endswith(".sem_ids")]
    if len(semantic_ids) != 1:
        raise ValueError("DiffGRM cache must contain exactly one Semantic-ID file")
    manifest = {
        "schema": "sidscope.diffgrm_processed_cache_manifest.v1",
        "domain": domain,
        "source_revision": REVISION,
        "catalog_rows": catalog_rows,
        "files": files,
        "semantic_id_filename": semantic_ids[0],
    }
    write(output, manifest)
    return manifest


def explicit_test_indices(selection: dict[str, Any], runtime: dict[str, Any]) -> list[int]:
    if selection.get("schema") != "sidscope.diffgrm_episode_selection.v1":
        raise ValueError("DiffGRM selection schema mismatch")
    selected = selection.get("episodes", [])
    if not selected or selection.get("first_n_fallback_allowed") is not False:
        raise ValueError("DiffGRM selection must be explicit and forbid first-N fallback")
    if sorted(row.get("selection_ordinal") for row in selected) != list(range(1, len(selected) + 1)):
        raise ValueError("DiffGRM selection ordinals must be contiguous")
    test_index = {
        str(row["episode_id"]): index for index, row in enumerate(runtime["splits"]["test"])
    }
    if len({str(row["episode_id"]) for row in selected}) != len(selected):
        raise ValueError("DiffGRM selection contains duplicate episodes")
    if any(str(row["episode_id"]) not in test_index for row in selected):
        raise ValueError("DiffGRM selection is not an explicit subset of prepared test")
    return [test_index[str(row["episode_id"])] for row in selected]


def run(args: argparse.Namespace) -> dict[str, Any]:
    sys.path.insert(0, str(args.upstream_source.resolve()))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from accelerate import Accelerator
    from torch.utils.data import DataLoader
    import torch
    from genrec.utils import get_config, init_seed
    from genrec.models.DIFF_GRM.tokenizer import DIFF_GRMTokenizer
    from genrec.models.DIFF_GRM.model import DIFF_GRM
    from genrec.models.DIFF_GRM.evaluator import DIFF_GRMEvaluator
    from diffgrm_prepared_dataset import DormantPreparedDataset

    source_revision = (args.upstream_source / ".pinned-revision").read_text().strip()
    if source_revision != REVISION:
        raise ValueError(f"DiffGRM source revision mismatch: {source_revision}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.cache_dir if args.cache_dir is not None else args.output_dir / "cache"
    raw_embedding = cache_dir / "processed" / "sentence-t5-base_raw_d768.sent_emb"
    materialize(args.embedding_source, raw_embedding)
    cache_manifest = None
    if args.mode == "train_smoke":
        if args.processed_cache_manifest is None:
            raise ValueError("bounded train smoke requires a processed-cache manifest")
        cache_manifest = verify_processed_cache(cache_dir, args.processed_cache_manifest)
    overrides = {
        "dataset": "DormantPreparedDataset", "category": args.domain,
        "cache_dir": str(cache_dir), "log_dir": str(args.output_dir / "logs"),
        "tensorboard_log_dir": str(args.output_dir / "tensorboard"),
        "rand_seed": args.seed, "num_proc": 1, "device": args.device,
        "n_digit": 4, "codebook_size": 256,
        "masking_strategy": "guided", "guided_refresh_each_step": False,
        "guided_select": "least", "guided_conf_metric": "msp",
        "encoder_n_layer": 1, "decoder_n_layer": 4, "n_head": 4,
        "n_embd": 256, "n_inner": 1024, "max_history_len": 50,
        "train_sliding": False, "lr": 0.003, "label_smoothing": 0.1,
        "sent_emb_model": "sentence-transformers/sentence-t5-base",
        "sent_emb_dim": 768, "sent_emb_pca": 256, "normalize_after_pca": True,
        "sent_emb_batch_size": 256, "sid_quantizer": "opq_pq",
        "opq_use_gpu": False, "faiss_omp_num_threads": args.faiss_threads,
        "force_regenerate_opq": args.force_regenerate_opq,
        "share_decoder_output_embedding": True,
        "beam_search_modes": ["confidence"], "topk": [5, 10],
    }
    config = get_config("DIFF_GRM", "AmazonReviews2014", None, overrides)
    accelerator = Accelerator()
    config["accelerator"] = accelerator
    config["device"] = torch.device(args.device)
    init_seed(args.seed, True)
    dataset = DormantPreparedDataset(config, args.runtime_manifest)
    tokenizer = DIFF_GRMTokenizer(config, dataset)
    tokenized = tokenizer.tokenize(dataset.split())
    model = DIFF_GRM(config, dataset, tokenizer).to(config["device"])
    if args.expected_catalog_rows is not None and dataset.n_items - 1 != args.expected_catalog_rows:
        raise ValueError("DiffGRM runtime catalog denominator mismatch")
    if args.mode == "preflight":
        train = tokenized["train"].select(range(min(2, len(tokenized["train"]))))
        batch = next(iter(DataLoader(train, batch_size=len(train), collate_fn=tokenizer.collate_fn["train"])))
        batch = {key: value.to(config["device"]) for key, value in batch.items()}
        with torch.no_grad():
            output = model(batch, return_loss=True)
        result = {
            "schema": "genrec_dormant.diffgrm_runtime_preflight.v1", "status": "pass",
            "source_revision": source_revision, "domain": args.domain,
            "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
            "embedding_sha256": sha256_file(args.embedding_source),
            "semantic_id_cache": str(next((cache_dir / "processed").glob("*.sem_ids"))),
            "catalog_rows": dataset.n_items - 1, "train_rows": len(tokenized["train"]),
            "validation_rows": len(tokenized["val"]), "test_rows": len(tokenized["test"]),
            "forward_loss_finite": bool(torch.isfinite(output.loss).item()),
            "model_parameters": model.n_parameters,
            "next_gate": "independent code review then bounded GPU checkpoint smoke",
        }
        output_name = "runtime_preflight.json"
    else:
        if args.device != "cuda":
            raise ValueError("bounded train smoke requires --device cuda")
        if args.selection is None:
            raise ValueError("bounded train smoke requires explicit episode selection")
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        runtime = json.loads(args.runtime_manifest.read_text(encoding="utf-8"))
        selected = selection.get("episodes", [])
        selected_indices = explicit_test_indices(selection, runtime)
        train_count = min(args.train_rows, len(tokenized["train"]))
        train = tokenized["train"].select(range(train_count))
        generator = torch.Generator().manual_seed(args.seed)
        loader = DataLoader(
            train, batch_size=args.train_batch_size, shuffle=True, generator=generator,
            collate_fn=tokenizer.collate_fn["train"],
        )
        optimizer = torch.optim.AdamW(model.parameters(), lr=config["lr"], weight_decay=0.0)
        losses: list[float] = []
        model.train()
        for batch in loader:
            batch = {key: value.to(config["device"]) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            output = model(batch, return_loss=True)
            if not torch.isfinite(output.loss):
                raise ValueError("non-finite loss in DiffGRM bounded smoke")
            output.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(output.loss.detach().cpu()))
            if len(losses) >= args.max_steps:
                break
        if len(losses) != args.max_steps:
            raise ValueError("bounded smoke did not complete requested update count")
        checkpoint = args.output_dir / "bounded_smoke_checkpoint.pt"
        torch.save({"model": model.state_dict(), "completed_steps": len(losses)}, checkpoint)
        checkpoint_sha256 = sha256_file(checkpoint)
        checkpoint_payload = torch.load(checkpoint, map_location=config["device"])
        if int(checkpoint_payload.get("completed_steps", -1)) != args.max_steps:
            raise ValueError("DiffGRM checkpoint completed-step binding mismatch")
        eval_model = DIFF_GRM(config, dataset, tokenizer).to(config["device"])
        eval_model.load_state_dict(checkpoint_payload["model"], strict=True)
        eval_rows = tokenized["test"].select(selected_indices)
        eval_loader = DataLoader(
            eval_rows, batch_size=1, shuffle=False, collate_fn=tokenizer.collate_fn["test"]
        )
        evaluator = DIFF_GRMEvaluator(config, tokenizer)
        per_episode = []
        eval_model.eval()
        config["current_split"] = "test"
        with torch.no_grad():
            for selected_row, batch in zip(selected, eval_loader):
                batch = {key: value.to(config["device"]) for key, value in batch.items()}
                predictions = eval_model.generate(batch, n_return_sequences=10, mode="confidence")
                metrics = evaluator.calculate_metrics(predictions, batch["labels"])
                rows = predictions[0].detach().cpu().tolist()
                per_episode.append({
                    "episode_id": selected_row["episode_id"],
                    "gap_bucket": selected_row["gap_bucket"],
                    "sid_code_hit_at_10": float(metrics["recall@10"][0]),
                    "sid_code_ndcg_at_10": float(metrics["ndcg@10"][0]),
                    "generated_sid_rows": rows,
                    "resolved_item_ids": [tokenizer.codebooks_to_item_id(row) for row in rows],
                })
        result = {
            "schema": "genrec_dormant.diffgrm_bounded_checkpoint_smoke.v1",
            "status": "pass", "scientific_result": False,
            "boundary": "runtime/checkpoint/selection smoke only",
            "source_revision": source_revision, "domain": args.domain,
            "processed_cache_manifest_sha256": sha256_file(args.processed_cache_manifest),
            "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
            "selection_sha256": sha256_file(args.selection),
            "embedding_sha256": sha256_file(args.embedding_source),
            "semantic_id_cache_sha256": sha256_file(next((cache_dir / "processed").glob("*.sem_ids"))),
            "checkpoint_sha256": checkpoint_sha256,
            "checkpoint_reloaded_strict": True,
            "train_rows": train_count, "completed_steps": len(losses),
            "initial_loss": losses[0], "final_loss": losses[-1],
            "episodes": len(per_episode),
            "sid_code_hit_at_10": sum(row["sid_code_hit_at_10"] for row in per_episode) / len(per_episode),
            "sid_code_ndcg_at_10": sum(row["sid_code_ndcg_at_10"] for row in per_episode) / len(per_episode),
            "per_episode": per_episode,
            "next_gate": "native masked trace export plus SIDScope verifier before formal training",
        }
        output_name = "bounded_smoke_manifest.json"
    write(args.output_dir / output_name, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--embedding-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--processed-cache-manifest", type=Path)
    parser.add_argument("--expected-catalog-rows", type=int)
    parser.add_argument("--mode", choices=["preflight", "train_smoke"], default="preflight")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--faiss-threads", type=int, default=32)
    parser.add_argument("--force-regenerate-opq", action="store_true")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--train-rows", type=int, default=512)
    parser.add_argument("--train-batch-size", type=int, default=64)
    parser.add_argument("--max-steps", type=int, default=8)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
