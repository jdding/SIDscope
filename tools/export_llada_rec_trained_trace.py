#!/usr/bin/env python3
"""Export native checkpoint-bound LLaDA-Rec adaptive-unmasking traces."""

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


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

try:
    from tools.run_diffgrm_resumable_training import (  # noqa: E402
        atomic_json_write, sha256_file, sha256_state_dict, trusted_torch_load,
    )
    from tools.run_llada_rec_resumable_training import (  # noqa: E402
        SOURCE_REVISION, load_semantic_ids, model_overrides, validate_source,
        working_directory,
    )
except ModuleNotFoundError:
    from run_diffgrm_resumable_training import (  # type: ignore[no-redef]
        atomic_json_write, sha256_file, sha256_state_dict, trusted_torch_load,
    )
    from run_llada_rec_resumable_training import (  # type: ignore[no-redef]
        SOURCE_REVISION, load_semantic_ids, model_overrides, validate_source,
        working_directory,
    )


BUCKETS = ("short", "30-90d", "90-180d", "180-365d", ">365d")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_inputs(
    prepared: dict[str, Any],
    selection: dict[str, Any],
    runtime: dict[str, Any],
    semantic_ids: dict[str, Any],
) -> None:
    if prepared.get("schema") != "sidscope.llada_rec_prepared_dataset.v1":
        raise ValueError("LLaDA-Rec prepared schema mismatch")
    if prepared.get("source_revision") != SOURCE_REVISION:
        raise ValueError("LLaDA-Rec prepared source revision mismatch")
    if selection.get("schema") != "sidscope.llada_rec_episode_selection.v1":
        raise ValueError("LLaDA-Rec selection schema mismatch")
    if selection.get("prepared_dataset_contract_sha256") != canonical_hash(prepared):
        raise ValueError("LLaDA-Rec selection prepared binding mismatch")
    if selection.get("first_n_fallback_allowed") is not False:
        raise ValueError("LLaDA-Rec selection must reject first-N fallback")
    if runtime.get("schema") != "genrec_dormant.diffgrm_private_runtime.v1":
        raise ValueError("LLaDA-Rec runtime schema mismatch")
    normalized = {str(row["normalized_item_id"]) for row in prepared.get("catalog", [])}
    if normalized != set(semantic_ids):
        raise ValueError("LLaDA-Rec prepared/semantic-ID universe mismatch")
    test = {str(row["episode_id"]): row for row in runtime["splits"]["test"]}
    indexed = {str(row["episode_id"]): row for row in prepared["episode_index"]}
    seen: set[str] = set()
    episodes = selection.get("episodes", [])
    for ordinal, selected in enumerate(episodes, start=1):
        episode_id = str(selected.get("episode_id"))
        if int(selected.get("selection_ordinal", -1)) != ordinal:
            raise ValueError("LLaDA-Rec selection ordinals are not contiguous")
        if episode_id in seen:
            raise ValueError("LLaDA-Rec selection contains a duplicate episode")
        if episode_id not in test or episode_id not in indexed:
            raise ValueError("LLaDA-Rec selected episode is outside frozen test")
        if str(selected.get("target_normalized_item_id")) != str(
            indexed[episode_id]["target_normalized_item_id"]
        ):
            raise ValueError("LLaDA-Rec selection target mismatch")
        if selected.get("generator_input_contains_bucket_or_label") is not False:
            raise ValueError("LLaDA-Rec generator input leaks evaluator fields")
        seen.add(episode_id)


def _rank_candidates(
    final_rows: list[dict[str, Any]], token_to_items: dict[tuple[int, ...], list[str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    grouped: dict[tuple[int, ...], dict[str, Any]] = {}
    for row in final_rows:
        tokens = tuple(int(value) for value in row["model_vocabulary_tokens"])
        current = grouped.get(tokens)
        if current is None or float(row["score_log_probability"]) > float(
            current["score_log_probability"]
        ):
            grouped[tokens] = row
    groups = []
    dense = []
    seen_items: set[str] = set()
    invalid = 0
    duplicates = len(final_rows) - len(grouped)
    for tuple_rank, row in enumerate(
        sorted(
            grouped.values(),
            key=lambda value: (-float(value["score_log_probability"]), value["beam_id"]),
        ),
        start=1,
    ):
        tokens = tuple(int(value) for value in row["model_vocabulary_tokens"])
        matches = token_to_items.get(tokens, [])
        if not matches:
            invalid += 1
        groups.append({
            "tuple_rank": tuple_rank,
            "beam_id": row["beam_id"],
            "model_vocabulary_tokens": list(tokens),
            "score_log_probability": row["score_log_probability"],
            "generation_order": row["generation_order"],
            "resolved_normalized_item_ids": matches,
            "resolution_status": (
                "unresolved_semantic_id"
                if not matches
                else "unique_item"
                if len(matches) == 1
                else "ambiguous_semantic_id"
            ),
        })
        for normalized_id in matches:
            if normalized_id in seen_items:
                continue
            seen_items.add(normalized_id)
            dense.append({
                "rank": len(dense) + 1,
                "normalized_item_id": normalized_id,
                "score_log_probability": row["score_log_probability"],
                "source_tuple_rank": tuple_rank,
            })
    return groups, dense, {
        "raw_candidate_count": len(final_rows),
        "unique_raw_tuple_count": len(grouped),
        "duplicate_raw_tuple_count": duplicates,
        "invalid_raw_tuple_count": invalid,
    }


def trace_episode(
    *, model: Any, tokenizer: Any, dataset: Any, sequence: list[str],
    episode_id: str, target_normalized_id: str, gap_bucket: str,
    beam_size: int, top_k_per_position: int, torch_module: Any,
    token_to_items: dict[tuple[int, ...], list[str]],
) -> dict[str, Any]:
    input_items = sequence[-21:-1]
    input_ids = [dataset.item2id[item] for item in input_items]
    input_ids = [0] * (20 - len(input_ids)) + input_ids
    item_tensor = torch_module.tensor([input_ids], dtype=torch_module.long, device=model.config["device"])
    history_tokens = model.item_id2tokens[item_tensor].reshape(1, -1)
    attention_mask = history_tokens != 0
    all_ids, all_attention, beam_scores, beam_offset = model.prepare_beam_search_inputs(
        history_tokens, attention_mask, 1, beam_size
    )
    n_digit = tokenizer.n_digit
    history_width = all_ids.shape[1] - n_digit
    active_ids = ["root"] + [f"inactive-root-{index}" for index in range(1, beam_size)]
    active_orders = [[] for _ in range(beam_size)]
    initial_target = all_ids[0, -n_digit:].detach().cpu().tolist()
    steps = []
    candidate_expansions = 0
    logits_evaluated = 0
    started = time.perf_counter()
    num_transferred = 0
    for refinement_step in range(1, model.gen_steps + 1):
        transfer_count = n_digit // model.gen_steps
        if refinement_step == model.gen_steps:
            transfer_count = n_digit - num_transferred
        outputs = model.llada_forward(
            input_ids=all_ids, attention_mask=all_attention.long()
        )
        logits = outputs.logits / model.temperature
        logits_evaluated += int(logits.numel())
        transfer_index = model.get_transfer_index(all_ids, logits, transfer_count)
        for within_step in range(transfer_count):
            selected_absolute = transfer_index[:, within_step]
            vocab_size = logits.shape[-1]
            selected_logits = logits.gather(
                index=selected_absolute[:, None, None].expand(-1, 1, vocab_size), dim=1
            ).squeeze(1)
            full_log_probs = torch_module.log_softmax(selected_logits, dim=-1)
            full_probs = torch_module.softmax(selected_logits, dim=-1)
            target_positions = selected_absolute - history_width
            valid_tokens = model.posValidTokens[target_positions]
            valid_tokens = valid_tokens.masked_fill(valid_tokens == 0, model.mask_token_id)
            valid_log_probs = full_log_probs.gather(index=valid_tokens, dim=1)
            valid_log_probs = valid_log_probs.masked_fill(
                valid_tokens == model.mask_token_id, -math.inf
            )
            cumulative = valid_log_probs + beam_scores[:, None]
            valid_width = cumulative.shape[1]
            candidate_expansions += int(torch_module.isfinite(cumulative).sum().item())
            flattened = cumulative.reshape(1, beam_size * valid_width)
            next_scores, next_flat = torch_module.topk(
                flattened, 2 * beam_size, dim=1, largest=True, sorted=True
            )
            parent_indices = torch_module.div(
                next_flat, valid_width, rounding_mode="floor"
            )
            token_indices = next_flat % valid_width
            retained_scores = next_scores[:, :beam_size].reshape(-1)
            retained_parents = parent_indices[:, :beam_size].reshape(-1)
            retained_token_indices = token_indices[:, :beam_size].reshape(-1)

            previous_ids = all_ids
            previous_active_ids = active_ids
            previous_orders = active_orders
            parent_global = retained_parents + beam_offset
            all_ids = previous_ids[parent_global].clone()
            selected_for_child = selected_absolute[parent_global]
            valid_for_child = model.posValidTokens[
                selected_for_child - history_width
            ]
            chosen_tokens = valid_for_child.gather(
                index=retained_token_indices[:, None], dim=1
            ).squeeze(1)
            child_index = torch_module.arange(beam_size, device=all_ids.device)
            all_ids[child_index, selected_for_child] = chosen_tokens
            beam_scores = retained_scores

            transitions = []
            new_ids = []
            new_orders = []
            for rank in range(beam_size):
                parent = int(retained_parents[rank].item())
                position = int((selected_for_child[rank] - history_width).item())
                token = int(chosen_tokens[rank].item())
                beam_id = f"s{refinement_step}a{within_step + 1}b{rank + 1}"
                parent_id = previous_active_ids[parent]
                pre = previous_ids[parent, -n_digit:].detach().cpu().tolist()
                post = all_ids[rank, -n_digit:].detach().cpu().tolist()
                top_values, top_indices = torch_module.topk(
                    valid_log_probs[parent],
                    min(top_k_per_position, int(torch_module.isfinite(valid_log_probs[parent]).sum().item())),
                )
                top_tokens = valid_tokens[parent].gather(0, top_indices)
                order = previous_orders[parent] + [position]
                transitions.append({
                    "beam_id": beam_id,
                    "parent_beam_id": parent_id,
                    "pre_tokens": pre,
                    "pre_masked_positions": [i for i, value in enumerate(pre) if value == model.mask_token_id],
                    "selected_positions": [position],
                    "predicted_tokens": [token],
                    "position_selection_confidence": float(
                        full_probs[parent, :,].max(dim=-1).values.item()
                    ),
                    "selected_token_log_probability": float(
                        full_log_probs[parent, token].item()
                    ),
                    "top_k_tokens": [int(value) for value in top_tokens.detach().cpu().tolist()],
                    "top_k_log_probabilities": [float(value) for value in top_values.detach().cpu().tolist()],
                    "remasked_positions": [],
                    "post_tokens": post,
                    "post_masked_positions": [i for i, value in enumerate(post) if value == model.mask_token_id],
                    "beam_score_log_probability": float(beam_scores[rank].item()),
                    "generation_order": order,
                    "retained_rank": rank + 1,
                })
                new_ids.append(beam_id)
                new_orders.append(order)
            active_ids = new_ids
            active_orders = new_orders
            steps.append({
                "refinement_step": refinement_step,
                "within_step_action": within_step + 1,
                "expanded_candidate_count": int(torch_module.isfinite(cumulative).sum().item()),
                "retained_beam_count": beam_size,
                "pruned_candidate_count": int(torch_module.isfinite(cumulative).sum().item()) - beam_size,
                "transitions": transitions,
            })
        num_transferred += transfer_count

    final_rows = [{
        "beam_id": active_ids[index],
        "model_vocabulary_tokens": all_ids[index, -n_digit:].detach().cpu().tolist(),
        "score_log_probability": float(beam_scores[index].item()),
        "generation_order": active_orders[index],
    } for index in range(beam_size)]
    groups, ranked, counts = _rank_candidates(final_rows, token_to_items)
    target_rank = next(
        (row["rank"] for row in ranked if row["normalized_item_id"] == target_normalized_id),
        None,
    )
    return {
        "episode_id": episode_id,
        "split": "test",
        "gap_bucket": gap_bucket,
        "target_normalized_item_id": target_normalized_id,
        "context_normalized_item_count": len(input_items),
        "initial_mask_state": initial_target,
        "steps": steps,
        "final_candidate_groups": groups,
        "ranked_items": ranked,
        "target_rank": target_rank,
        "target_rank_state": "exact" if target_rank is not None else "right_censored_beyond_beam_frontier",
        "hit_at_10": target_rank is not None and target_rank <= 10,
        "ndcg_at_10": (
            1.0 / math.log2(target_rank + 1)
            if target_rank is not None and target_rank <= 10
            else 0.0
        ),
        "generation_search_miss": target_rank is None,
        "resolution_loss": False,
        "ranking_conversion_miss": target_rank is not None and target_rank > 10,
        "candidate_summary": counts,
        "compute": {
            "nfe": model.gen_steps,
            "forward_calls": model.gen_steps,
            "logits_evaluated": logits_evaluated,
            "candidate_expansion_count": candidate_expansions,
            "visited_state_count": 1 + beam_size * model.gen_steps,
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        },
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    validate_source(args.upstream_source)
    prepared = load(args.prepared_dataset)
    selection = load(args.selection)
    runtime = load(args.runtime_manifest)
    semantic = load(args.semantic_ids)
    validate_inputs(prepared, selection, runtime, semantic)
    runtime_codes, _ = load_semantic_ids(
        args.runtime_manifest, args.semantic_ids,
        expected_catalog_rows=args.expected_catalog_rows,
    )
    sys.path.insert(0, str(args.upstream_source.resolve()))
    sys.path.insert(0, str((ROOT / "tools").resolve()))
    import torch
    from accelerate import Accelerator
    from genrec.models.LLaDARec.model import LLaDARec
    from genrec.models.LLaDARec.tokenizer import LLaDARecTokenizer
    from genrec.utils import get_config
    from llada_rec_prepared_dataset import DormantPreparedLLaDADataset

    config_args = argparse.Namespace(
        domain=args.domain,
        output_dir=args.output.parent / "runtime_cache",
        seed=args.seed,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    config = get_config("LLaDARec", "AmazonReviews2023", None, model_overrides(config_args))
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
    model = LLaDARec(config, dataset, tokenizer).to(config["device"])
    checkpoint = trusted_torch_load(torch, args.checkpoint, map_location=config["device"])
    bindings = checkpoint.get("bindings", {})
    if (
        bindings.get("source_revision") != SOURCE_REVISION
        or bindings.get("prepared_dataset_sha256") != sha256_file(args.prepared_dataset)
        or bindings.get("semantic_ids_sha256") != sha256_file(args.semantic_ids)
    ):
        raise ValueError("LLaDA-Rec checkpoint evidence binding mismatch")
    model.load_state_dict(checkpoint["model"], strict=True)
    declared_model_hash = checkpoint.get("model_state_sha256")
    if declared_model_hash is None and checkpoint.get("epoch_records"):
        declared_model_hash = checkpoint["epoch_records"][-1].get("model_state_sha256")
    if declared_model_hash != sha256_state_dict(model.state_dict()):
        raise ValueError("LLaDA-Rec checkpoint model-state hash mismatch")
    model.eval()

    token_to_items: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for row in prepared["catalog"]:
        token_to_items[tuple(int(value) for value in row["model_vocabulary_tokens"])].append(
            str(row["normalized_item_id"])
        )
    for matches in token_to_items.values():
        matches.sort()
    test_rows = {str(row["episode_id"]): row for row in runtime["splits"]["test"]}
    episodes = []
    with torch.no_grad():
        for selected in selection["episodes"]:
            episode_id = str(selected["episode_id"])
            episodes.append(trace_episode(
                model=model,
                tokenizer=tokenizer,
                dataset=dataset,
                sequence=[str(value) for value in test_rows[episode_id]["item_seq"]],
                episode_id=episode_id,
                target_normalized_id=str(selected["target_normalized_item_id"]),
                gap_bucket=str(selected["gap_bucket"]),
                beam_size=args.beam_size,
                top_k_per_position=args.top_k_per_position,
                torch_module=torch,
                token_to_items=token_to_items,
            ))
    count = len(episodes)
    bundle = {
        "schema": "sidscope.llada_rec_trained_trace.v2",
        "route_id": "llada_rec",
        "adapter_version": "sidscope.llada_rec_adapter.v2",
        "source_revision": SOURCE_REVISION,
        "decode_state_kind": "masked_parallel_adaptive_unmasking",
        "remasking_supported_by_pinned_source": False,
        "evaluation_cutoff": 10,
        "published_rank_depth": args.beam_size,
        "prepared_dataset_contract_sha256": canonical_hash(prepared),
        "episode_selection_manifest_sha256": canonical_hash(selection),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "training_manifest_sha256": sha256_file(args.training_manifest),
        "semantic_ids_sha256": sha256_file(args.semantic_ids),
        "episodes": episodes,
        "summary": {
            "episode_count": count,
            "five_bucket_counts": {
                bucket: sum(row["gap_bucket"] == bucket for row in episodes)
                for bucket in BUCKETS
            },
            "hit_at_10": sum(bool(row["hit_at_10"]) for row in episodes) / count,
            "ndcg_at_10": sum(float(row["ndcg_at_10"]) for row in episodes) / count,
            "exact_target_rank_count": sum(row["target_rank"] is not None for row in episodes),
            "right_censored_target_rank_count": sum(row["target_rank"] is None for row in episodes),
            "invalid_raw_tuple_count": sum(row["candidate_summary"]["invalid_raw_tuple_count"] for row in episodes),
            "duplicate_raw_tuple_count": sum(row["candidate_summary"]["duplicate_raw_tuple_count"] for row in episodes),
            "compute": {
                field: sum(row["compute"][field] for row in episodes)
                for field in (
                    "nfe", "forward_calls", "logits_evaluated",
                    "candidate_expansion_count", "visited_state_count", "latency_ms",
                )
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--prepared-dataset", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--semantic-ids", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--training-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain", default="amazon_vg")
    parser.add_argument("--expected-catalog-rows", type=int, default=17396)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--beam-size", type=int, default=50)
    parser.add_argument("--top-k-per-position", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
