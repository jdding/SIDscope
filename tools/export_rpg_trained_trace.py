#!/usr/bin/env python3
"""Export deidentified trained RPG parallel graph-decoding traces."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset


SCHEMA = "sidscope.rpg_trained_trace_bundle.v1"
SCHEMA_V2 = "sidscope.rpg_trained_trace_bundle.v2"
RANK_DIAGNOSTIC_SCHEMA = "sidscope.rpg_rank_depth_diagnostic.v1"
SOURCE_REVISION = "7dcf95ce9e08601810efdd1c850ed6dada5f97c2"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpg-source", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--prepared-dataset", type=Path)
    parser.add_argument("--prepared-root", type=Path)
    parser.add_argument("--episode-selection", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--training-manifest", type=Path, required=True)
    parser.add_argument(
        "--formal-training-runner",
        type=Path,
        help="Exact runner snapshot loaded by the recorded training invocation.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--episodes", type=int)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--rank-cutoff", type=int)
    parser.add_argument(
        "--published-rank-depth",
        type=int,
        help=(
            "Prepared v2 only: diagnostic ranked-item publication depth. Defaults to 100, "
            "capped only by the complete official final frontier."
        ),
    )
    parser.add_argument("--parallel-topk", type=int)
    parser.add_argument(
        "--target-universe-mode",
        choices=("bounded", "complete"),
        default="bounded",
        help=(
            "Publish only ranked-item resolution rows for a bounded public smoke, "
            "or the complete normalized-item/SID universe for external evidence."
        ),
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def rounded(value: float) -> float:
    return round(float(value), 10)


def main() -> None:
    args = parse_args()
    if args.episodes is not None and (args.episodes <= 0 or args.episodes > 256):
        raise SystemExit("episodes must be in [1, 256]")
    if args.published_rank_depth is not None and args.published_rank_depth <= 0:
        raise SystemExit("--published-rank-depth must be positive")
    source = args.rpg_source.resolve()
    sys.path.insert(0, str(source))

    started = time.time()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prepared = None
    selection = None
    if args.prepared_dataset is None:
        if args.episode_selection is not None or args.prepared_root is not None:
            raise SystemExit("prepared selection/root arguments require --prepared-dataset")
        if args.cache_dir is None:
            raise SystemExit("Beauty v1 mode requires --cache-dir")
        episodes_requested = args.episodes or 5
        rank_cutoff = args.rank_cutoff or 10
        if args.published_rank_depth is not None:
            raise SystemExit("--published-rank-depth is available only in prepared v2 mode")
        parallel_topk = args.parallel_topk or 5
        from genrec.pipeline import Pipeline

        config = {
            "cache_dir": str(args.cache_dir.resolve()) + "/",
            "log_dir": str(args.output.parent.resolve() / "trace_logs") + "/",
            "tensorboard_log_dir": str(args.output.parent.resolve() / "trace_tensorboard") + "/",
            "ckpt_dir": str(args.output.parent.resolve() / "trace_ckpt") + "/",
            "run_id": "rpg_beauty_trained_trace",
            "rand_seed": args.seed,
            "reproducibility": True,
            "category": "Beauty",
            "metadata": "sentence",
            "sent_emb_model": "sentence-transformers/sentence-t5-base",
            "sent_emb_dim": 768,
            "sent_emb_pca": 128,
            "n_codebook": 32,
            "codebook_size": 256,
            "lr": 0.01,
            "temperature": 0.03,
            "num_beams": 20,
            "n_edges": 200,
            "propagation_steps": 3,
        }
        pipeline = Pipeline(
            model_name="RPG",
            dataset_name="AmazonReviews2014",
            checkpoint_path=str(args.checkpoint.resolve()),
            config_dict=config,
        )
        selection_rows = None
    else:
        if args.cache_dir is not None or args.episodes is not None:
            raise SystemExit("v2 prepared mode forbids --cache-dir and --episodes; selection is explicit")
        if args.target_universe_mode != "complete":
            raise SystemExit("v2 prepared mode requires --target-universe-mode complete")
        if args.episode_selection is None:
            raise SystemExit("v2 prepared mode requires --episode-selection")
        from tools.rpg_non_ar_bridge import (
            build_official_runtime,
            canonical_hash as bridge_hash,
            validate_episode_selection,
            validate_prepared_dataset,
        )

        prepared = json.loads(args.prepared_dataset.read_text(encoding="utf-8"))
        selection = json.loads(args.episode_selection.read_text(encoding="utf-8"))
        validate_prepared_dataset(prepared)
        validate_episode_selection(selection, prepared)
        if prepared["training"].get("status", "complete") != "complete":
            raise SystemExit("prepared dataset training binding must be complete before export")
        if sha256_file(args.checkpoint) != prepared["training"]["checkpoint_sha256"]:
            raise SystemExit("checkpoint does not match prepared training binding")
        if sha256_file(args.training_manifest) != prepared["training"]["training_manifest_sha256"]:
            raise SystemExit("training manifest does not match prepared training binding")
        if args.seed != prepared["configuration"]["model_seed"]:
            raise SystemExit("--seed must equal prepared configuration.model_seed")
        prepared_root = (args.prepared_root or args.prepared_dataset.parent).resolve()
        pipeline = build_official_runtime(
            rpg_source=source,
            prepared=prepared,
            prepared_root=prepared_root,
            runtime_dir=args.output.parent / "prepared_trace_runtime",
            checkpoint=args.checkpoint,
        )
        episodes_requested = len(selection["rows"])
        selection_rows = selection["rows"]
        rank_cutoff = prepared["configuration"]["rank_cutoff"]
        parallel_topk = prepared["configuration"]["parallel_topk"]
        if args.rank_cutoff is not None and args.rank_cutoff != rank_cutoff:
            raise SystemExit("--rank-cutoff must match prepared configuration")
        if args.parallel_topk is not None and args.parallel_topk != parallel_topk:
            raise SystemExit("--parallel-topk must match prepared configuration")
        test_rows = pipeline.prepared_rows["splits"]["test"]
        for selected in selection_rows:
            observed = test_rows[selected["split_row_index"]]
            if observed["episode_id"] != selected["episode_id"]:
                raise SystemExit(f"episode id mismatch at test row {selected['split_row_index']}")
            if observed["normalized_item_ids"][-1] != selected["expected_target_normalized_item_id"]:
                raise SystemExit(f"target mismatch at test row {selected['split_row_index']}")
    device = torch.device(pipeline.config["device"])
    model = pipeline.model.to(device).eval()
    tokenizer = pipeline.tokenizer
    dataset = pipeline.raw_dataset
    if rank_cutoff > model.num_beams:
        raise RuntimeError("rank cutoff exceeds the official graph beam width")
    requested_published_rank_depth = None
    published_rank_depth = rank_cutoff
    ranking_diagnostic = None
    if prepared is not None:
        requested_published_rank_depth = args.published_rank_depth or 100
        if requested_published_rank_depth < rank_cutoff:
            raise RuntimeError("published rank depth cannot be below the evaluation cutoff")
        published_rank_depth = min(requested_published_rank_depth, model.num_beams)
        ranking_diagnostic = {
            "schema": RANK_DIAGNOSTIC_SCHEMA,
            "evaluation_cutoff": rank_cutoff,
            "requested_published_rank_depth": requested_published_rank_depth,
            "published_rank_depth": published_rank_depth,
            "available_resolved_rank_depth": model.num_beams,
            "publication_scope": (
                "complete_resolved_final_frontier"
                if published_rank_depth == model.num_beams
                else "fixed_depth"
            ),
            "absent_target_rank_state": "target_not_in_published_depth",
            "censoring": "right",
        }

    # Canonical target universe contains only normalized identity and SID rows.
    target_universe = []
    token_set_to_nodes: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for node_id in range(1, dataset.n_items):
        tokens = [int(value) for value in model.item_id2tokens[node_id].detach().cpu().tolist()]
        codes = [(token - 1) % int(pipeline.config["codebook_size"]) for token in tokens]
        normalized_id = node_id - 1
        target_universe.append(
            {
                "normalized_item_id": normalized_id,
                "semantic_codes": codes,
                "unordered_model_vocabulary_tokens": sorted(tokens),
            }
        )
        token_set_to_nodes[tuple(sorted(tokens))].append(normalized_id)
    target_universe_sha256 = canonical_hash(target_universe)

    model.init_graph()
    adjacency = model.adjacency.detach()
    adjacency_sha256 = sha256_bytes(
        adjacency.cpu().contiguous().numpy().astype(np.int64, copy=False).tobytes()
    )

    selected_indices = (
        list(range(episodes_requested))
        if selection_rows is None
        else [row["split_row_index"] for row in selection_rows]
    )
    trace_dataset = Subset(pipeline.tokenized_datasets["test"], selected_indices)
    loader = DataLoader(
        trace_dataset,
        batch_size=1,
        shuffle=False,
        collate_fn=tokenizer.collate_fn["test"],
    )
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    episodes: list[dict[str, Any]] = []
    hit_count = 0
    ndcg_sum = 0.0
    exact_rank_count = 0
    deeper_rank_count = 0
    right_censored_count = 0
    resolution_failure_count = 0
    for episode_index, raw_batch in enumerate(loader):
        selected_episode = None if selection_rows is None else selection_rows[episode_index]
        batch = {key: value.to(device) for key, value in raw_batch.items()}
        with torch.no_grad():
            output = model.forward(batch, return_loss=False)
            states = output.final_states.gather(
                dim=1,
                index=(batch["seq_lens"] - 1)
                .view(-1, 1, 1, 1)
                .expand(-1, 1, model.n_pred_head, model.config["n_embd"]),
            )
            states = F.normalize(states, dim=-1)
            embedding = F.normalize(model.gpt2.wte.weight[1:-1], dim=-1)
            embedding_by_head = torch.chunk(embedding, model.n_pred_head, dim=0)
            logits_by_head = [
                F.log_softmax(
                    torch.matmul(states[:, 0, head, :], embedding_by_head[head].T)
                    / model.temperature,
                    dim=-1,
                )
                for head in range(model.n_pred_head)
            ]
            token_logits = torch.cat(logits_by_head, dim=-1)

        parallel_heads = []
        for head, head_logits in enumerate(logits_by_head):
            values, indices = torch.topk(head_logits[0], parallel_topk)
            parallel_heads.append(
                {
                    "codebook": head,
                    "top_tokens": [
                        {
                            "model_vocabulary_token": int(index) + head * model.tokenizer.codebook_size + 1,
                            "log_probability": rounded(value),
                        }
                        for value, index in zip(values.detach().cpu(), indices.detach().cpu())
                    ],
                }
            )
        token_logits_sha256 = sha256_bytes(
            token_logits.detach().cpu().contiguous().numpy().astype(np.float32, copy=False).tobytes()
        )

        initial_nodes = torch.randint(
            1,
            dataset.n_items,
            (1, model.num_beams),
            dtype=torch.long,
            device=device,
        )
        initial_node_values = [int(value) for value in initial_nodes[0].detach().cpu().tolist()]
        frontier = initial_nodes
        visited = set(initial_node_values)
        propagation = []
        final_scores = None
        for step in range(model.propagation_steps):
            neighbors = torch.unique(adjacency[frontier].view(-1))
            visited.update(int(value) for value in neighbors.detach().cpu().tolist())
            candidate_token_indices = model.item_id2tokens[neighbors] - 1
            per_codebook = torch.gather(
                token_logits[0].unsqueeze(0).expand(neighbors.shape[0], -1),
                dim=-1,
                index=candidate_token_indices,
            )
            candidate_scores = per_codebook.mean(dim=-1)
            selected = torch.topk(candidate_scores, model.num_beams)
            next_frontier = neighbors[selected.indices]
            propagation.append(
                {
                    "step": step + 1,
                    "candidate_count": int(neighbors.shape[0]),
                    "candidates": [
                        {
                            "normalized_item_id": int(node) - 1,
                            "mean_log_probability": rounded(score),
                        }
                        for node, score in zip(
                            neighbors.detach().cpu().tolist(),
                            candidate_scores.detach().cpu().tolist(),
                        )
                    ],
                    "frontier": [int(value) - 1 for value in next_frontier.detach().cpu().tolist()],
                }
            )
            frontier = next_frontier.view(1, -1)
            final_scores = selected.values

        assert final_scores is not None
        ranked = []
        for rank, (node, score) in enumerate(
            zip(
                frontier[0][:published_rank_depth],
                final_scores[:published_rank_depth],
            ),
            start=1,
        ):
            node_id = int(node)
            tokens_tensor = model.item_id2tokens[node_id]
            tokens = [int(value) for value in tokens_tensor.detach().cpu().tolist()]
            codebook_scores = torch.gather(token_logits[0], 0, tokens_tensor - 1)
            resolved = token_set_to_nodes[tuple(sorted(tokens))]
            ranked.append(
                {
                    "rank": rank,
                    "normalized_item_id": node_id - 1,
                    "semantic_codes": [
                        (token - 1) % int(pipeline.config["codebook_size"]) for token in tokens
                    ],
                    "unordered_model_vocabulary_tokens": sorted(tokens),
                    "codebook_log_probabilities": [
                        rounded(value) for value in codebook_scores.detach().cpu().tolist()
                    ],
                    "sum_log_probability": rounded(codebook_scores.sum()),
                    "mean_log_probability": rounded(score),
                    "graph_valid": True,
                    "resolution_status": "unique_item_node" if len(resolved) == 1 else "ambiguous_item_nodes",
                    "resolved_normalized_item_ids": resolved,
                }
            )

        labels = batch["labels"][0]
        target_values = labels[labels >= 0]
        if target_values.numel() != 1:
            raise RuntimeError("test episode must contain exactly one target item")
        target_normalized = int(target_values.item()) - 1
        target_rank = next(
            (row["rank"] for row in ranked if row["normalized_item_id"] == target_normalized), None
        )
        if target_rank is not None and target_rank <= rank_cutoff:
            hit_count += 1
            ndcg_sum += 1.0 / math.log2(target_rank + 1)
        target_rank_state = None
        target_rank_lower_bound = None
        if prepared is not None:
            target_resolved_in_depth = any(
                target_normalized in row["resolved_normalized_item_ids"] for row in ranked
            )
            if target_rank is not None:
                target_rank_state = "observed_exact"
                exact_rank_count += 1
                deeper_rank_count += int(target_rank > rank_cutoff)
            elif target_resolved_in_depth:
                target_rank_state = "resolution_failure_within_published_depth"
                resolution_failure_count += 1
            else:
                target_rank_state = "target_not_in_published_depth"
                target_rank_lower_bound = published_rank_depth + 1
                right_censored_count += 1
        seq_len = int(batch["seq_lens"][0].item())
        context = [int(value) - 1 for value in batch["input_ids"][0, :seq_len].detach().cpu().tolist()]
        episode_row = {
                "trace_id": hashlib.sha256(
                    (
                        f"rpg-beauty-test-{episode_index}-{target_universe_sha256}"
                        if selected_episode is None
                        else f"{selected_episode['episode_id']}-{bridge_hash(prepared)}-{bridge_hash(selection)}"
                    ).encode("utf-8")
                ).hexdigest()[:20],
                "context_normalized_item_ids": context,
                "target_normalized_item_id": target_normalized,
                "decode_state_kind": "unordered_token_set_graph_propagation",
                "parallel_token_scores": {
                    "shape": [model.n_pred_head, model.tokenizer.codebook_size],
                    "float32_sha256": token_logits_sha256,
                    "per_codebook_topk": parallel_heads,
                },
                "initial_item_nodes": [
                    value - 1 for value in initial_node_values
                ],
                "initial_item_node_duplicates": model.num_beams - len(set(initial_node_values)),
                "propagation": propagation,
                "visited_item_node_count": len(visited),
                "ranked_items": ranked,
                "target_rank": target_rank,
                "termination_reason": "completed_configured_graph_propagation",
            }
        if prepared is not None:
            episode_row.update(
                {
                    "target_rank_state": target_rank_state,
                    "target_rank_lower_bound": target_rank_lower_bound,
                }
            )
        if selected_episode is None:
            episode_row["split"] = "test_leave_one_out"
        else:
            if target_normalized != selected_episode["expected_target_normalized_item_id"]:
                raise RuntimeError(
                    f"selected target mismatch for {selected_episode['episode_id']}: "
                    f"expected {selected_episode['expected_target_normalized_item_id']} observed {target_normalized}"
                )
            episode_row.update(
                {
                    "episode_id": selected_episode["episode_id"],
                    "selection_order": selected_episode["order"],
                    "split_row_index": selected_episode["split_row_index"],
                    "split_id": prepared["splits"]["test"]["split_id"],
                }
            )
        episodes.append(episode_row)

    cache_processed = (
        args.cache_dir / "AmazonReviews2014/Beauty/processed"
        if prepared is None
        else None
    )
    runner_path = Path(__file__).with_name("run_rpg_resumable_training.py")
    if not runner_path.is_file():
        runner_path = Path(__file__).with_name("rpg_resumable_train.py")
    formal_runner_path = (
        args.formal_training_runner.resolve()
        if args.formal_training_runner is not None
        else runner_path
    )
    if args.target_universe_mode == "complete":
        published_target_rows = target_universe
        target_visibility = "external_complete"
    else:
        published_ids = sorted(
            {
                resolved_id
                for episode in episodes
                for ranked_row in episode["ranked_items"]
                for resolved_id in ranked_row["resolved_normalized_item_ids"]
            }
        )
        published_target_rows = [target_universe[item_id] for item_id in published_ids]
        target_visibility = "bounded_rows_full_universe_hash_bound"

    bundle = {
        "schema": SCHEMA if prepared is None else SCHEMA_V2,
        "bundle_id": (
            f"rpg-beauty-trained-{episodes_requested}-episode-smoke"
            if prepared is None
            else f"rpg-{prepared['contract_id']}-{selection['selection_id']}"
        ),
        "method": "RPG",
        "dataset": "AmazonReviews2014/Beauty" if prepared is None else prepared["dataset"],
        "decode_state_kind": "unordered_token_set_graph_propagation",
        "source": {
            "url": "https://github.com/facebookresearch/RPG_KDD2025",
            "revision": SOURCE_REVISION,
            "license": "CC-BY-NC-4.0",
        },
        "configuration": {
            "n_codebooks": model.n_pred_head,
            "codebook_size": model.tokenizer.codebook_size,
            "num_beams": model.num_beams,
            "n_edges": model.n_edges,
            "propagation_steps": model.propagation_steps,
            "temperature": model.temperature,
            "seed": args.seed,
            "rank_cutoff": rank_cutoff,
        },
        "evidence": {
            "checkpoint_sha256": sha256_file(args.checkpoint),
            "training_manifest_sha256": sha256_file(args.training_manifest),
            "source_model_sha256": sha256_file(source / "genrec/models/RPG/model.py"),
            "formal_training_runner_sha256": sha256_file(formal_runner_path),
            "reproduction_runner_sha256": sha256_file(runner_path),
            "exporter_sha256": sha256_file(Path(__file__)),
            "verifier_sha256": sha256_file(
                Path(__file__).with_name("verify_rpg_trained_trace_bundle.py")
            ),
            "semantic_id_cache_sha256": (
                sha256_file(cache_processed / "sentence-t5-base_OPQ32,IVF1,PQ32x8.sem_ids")
                if prepared is None
                else prepared["artifacts"]["semantic_id_cache"]["sha256"]
            ),
            "item_mapping_sha256": (
                sha256_file(cache_processed / "id_mapping.json")
                if prepared is None
                else prepared["artifacts"]["item_mapping"]["sha256"]
            ),
            "interaction_sequences_sha256": (
                sha256_file(cache_processed / "all_item_seqs.json")
                if prepared is None
                else prepared["artifacts"]["interaction_sequences"]["sha256"]
            ),
            "adjacency_int64_sha256": adjacency_sha256,
            "split_id": (
                "AmazonReviews2014/Beauty:leave_one_out:test"
                if prepared is None
                else prepared["splits"]["test"]["split_id"]
            ),
            "training_boundary": (
                "official_architecture_full_beauty_training_output"
                if prepared is None
                else "official_rpg_architecture_prepared_dataset_training_output"
            ),
        },
        "target_universe": {
            "schema": "canonical_normalized_item_sid_rows.v1",
            "sha256": target_universe_sha256,
            "row_count": len(target_universe),
            "visibility": target_visibility,
            "rows": published_target_rows,
        },
        "episodes": episodes,
        "summary": {
            "episode_count": len(episodes),
            "hit_at_rank_cutoff": hit_count,
            "recall_at_rank_cutoff": hit_count / len(episodes),
            "elapsed_seconds": time.time() - started,
        },
    }
    if prepared is not None:
        if target_universe_sha256 != prepared["catalog"]["target_universe_sha256"]:
            raise RuntimeError("prepared target universe hash does not match official runtime rows")
        bundle["configuration"] = prepared["configuration"]
        bundle["source"] = prepared["source"]
        bundle["ranking_diagnostic"] = ranking_diagnostic
        bundle["summary"].update(
            {
                "ndcg_at_rank_cutoff": ndcg_sum / len(episodes),
                "exact_target_rank_count": exact_rank_count,
                "deeper_than_evaluation_cutoff_count": deeper_rank_count,
                "right_censored_target_rank_count": right_censored_count,
                "resolution_failure_within_published_depth_count": resolution_failure_count,
            }
        )
        bundle["evidence"].update(
            {
                "prepared_dataset_contract_sha256": bridge_hash(prepared),
                "episode_selection_manifest_sha256": bridge_hash(selection),
                "split_sha256": prepared["splits"]["test"]["sha256"],
            }
        )
    args.output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "pass",
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "episodes": len(episodes),
        "recall_at_rank_cutoff": bundle["summary"]["recall_at_rank_cutoff"],
        "elapsed_seconds": bundle["summary"]["elapsed_seconds"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
