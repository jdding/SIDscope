#!/usr/bin/env python3
"""Export a checkpoint-bound native masked-state DiffGRM trace bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Optional


REVISION = "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c"
SOURCE_TREE_SHA256 = "f0c40bb3e62ab8d0514a455d805ee97b84fd3ab5424f37e992a5e05479ec83ce"
TRACE_SCHEMA = "sidscope.diffgrm_masked_trace_bundle.v2"
ADAPTER_VERSION = "sidscope.diffgrm_adapter.v1"
MASK_TOKEN = -1
N_DIGIT = 4
CODEBOOK_SIZE = 256
BUCKETS = ("short", "30-90d", "90-180d", "180-365d", ">365d")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def model_overrides(args: argparse.Namespace, torch_module: Any) -> dict[str, Any]:
    return {
        "dataset": "DormantPreparedDataset",
        "category": args.domain,
        "cache_dir": str(args.cache_dir),
        "log_dir": str(args.output_dir / "logs"),
        "tensorboard_log_dir": str(args.output_dir / "tensorboard"),
        "rand_seed": args.seed,
        "num_proc": 1,
        "device": args.device,
        "n_digit": N_DIGIT,
        "codebook_size": CODEBOOK_SIZE,
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
        "lr": 0.003,
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
        "current_split": "test",
        "device_object": str(torch_module.device(args.device)),
    }


def validate_selection(selection: dict[str, Any], runtime: dict[str, Any]) -> list[int]:
    if selection.get("schema") != "sidscope.diffgrm_episode_selection.v1":
        raise ValueError("DiffGRM selection schema mismatch")
    rows = selection.get("episodes", [])
    if not rows or selection.get("first_n_fallback_allowed") is not False:
        raise ValueError("trace requires a non-empty explicit episode selection")
    if [int(row.get("selection_ordinal", -1)) for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("selection ordinals must be contiguous and one-based")
    buckets = [str(row.get("gap_bucket")) for row in rows]
    if len(rows) % len(BUCKETS):
        raise ValueError("selection must be exactly balanced across five frozen buckets")
    per_bucket = len(rows) // len(BUCKETS)
    if buckets != [bucket for bucket in BUCKETS for _ in range(per_bucket)]:
        raise ValueError("selection must contain equal contiguous blocks of all five buckets")
    test_index = {
        str(row["episode_id"]): index for index, row in enumerate(runtime["splits"]["test"])
    }
    ids = [str(row["episode_id"]) for row in rows]
    if len(set(ids)) != len(ids) or any(episode_id not in test_index for episode_id in ids):
        raise ValueError("selection has duplicate or absent test episodes")
    return [test_index[episode_id] for episode_id in ids]


def trusted_torch_load(torch_module: Any, path: Path, *, map_location: Any) -> Any:
    """Load only our own checkpoint while remaining compatible with old PyTorch."""

    try:
        return torch_module.load(path, map_location=map_location, weights_only=False)
    except TypeError:
        return torch_module.load(path, map_location=map_location)


def validate_training_binding(
    training_manifest: dict[str, Any], checkpoint: Path, expected_steps: int,
    *, domain: str, processed_cache_manifest_sha256: str,
) -> None:
    """Bind diagnostic traces to the completed formal training closure."""

    if training_manifest.get("status") != "pass":
        raise ValueError("training manifest is not a strict PASS")
    if int(training_manifest.get("completed_steps", -1)) != expected_steps:
        raise ValueError("training manifest completed-step binding mismatch")
    declared_checkpoint = training_manifest.get("formal_checkpoint_sha256")
    if declared_checkpoint is not None and declared_checkpoint != sha256_file(checkpoint):
        raise ValueError("training manifest checkpoint SHA-256 mismatch")
    if declared_checkpoint is None and expected_steps != 8:
        raise ValueError("formal trace requires a checkpoint-bound training manifest")
    bindings = training_manifest.get("bindings", {})
    if bindings.get("domain") != domain:
        raise ValueError("training manifest domain binding mismatch")
    if bindings.get("processed_cache_manifest_sha256") != processed_cache_manifest_sha256:
        raise ValueError("training manifest processed-cache binding mismatch")


def catalog_resolution(prepared: dict[str, Any]) -> dict[tuple[int, ...], list[str]]:
    result: dict[tuple[int, ...], list[str]] = {}
    for row in prepared.get("catalog", []):
        codes = tuple(int(value) for value in row["semantic_codes"])
        result.setdefault(codes, []).append(str(row["normalized_item_id"]))
    for values in result.values():
        values.sort()
    return result


def position_topk(
    log_probs: Any,
    masked_positions: list[int],
    topk: int = 2,
    *,
    selected_position: Optional[int] = None,
    selected_token: Optional[int] = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position in masked_positions:
        values, tokens = log_probs[position].topk(topk)
        candidates = {
            int(token): float(value)
            for value, token in zip(values.detach().cpu(), tokens.detach().cpu())
        }
        if position == selected_position and selected_token is not None:
            candidates[int(selected_token)] = float(log_probs[position, selected_token])
        rows.append({
            "position": position,
            "candidates": [
                {
                    "codebook_token_id": token,
                    "log_probability": value,
                }
                for token, value in sorted(candidates.items(), key=lambda row: row[1], reverse=True)
            ],
        })
    return rows


def expansion_record(
    *,
    beam_id: str,
    parent_beam_id: str,
    pre_codes: list[int],
    position: int,
    token: int,
    token_log_probability: float,
    cumulative_log_probability: float,
    per_position_topk: list[dict[str, Any]],
    retained: bool,
) -> dict[str, Any]:
    post_codes = list(pre_codes)
    post_codes[position] = token
    return {
        "beam_id": beam_id,
        "parent_beam_id": parent_beam_id,
        "pre_codes": pre_codes,
        "masked_positions_before": [i for i, value in enumerate(pre_codes) if value == MASK_TOKEN],
        "per_position_topk": per_position_topk,
        "selected_unmask_position": position,
        "selected_codebook_token_id": token,
        "selected_log_probability": token_log_probability,
        "confidence": math.exp(token_log_probability),
        "cumulative_log_probability": cumulative_log_probability,
        "post_codes": post_codes,
        "masked_positions_after": [i for i, value in enumerate(post_codes) if value == MASK_TOKEN],
        "retained": retained,
        "prune_reason": None if retained else "beam_score_pruned",
    }


def guided_noising_views(model: Any, encoder_hidden: Any, labels: Any, torch_module: Any) -> list[dict[str, Any]]:
    full_mask = torch_module.ones(1, N_DIGIT, dtype=torch_module.bool, device=labels.device)
    decoder_input = torch_module.zeros(1, N_DIGIT, dtype=torch_module.long, device=labels.device)
    with torch_module.no_grad():
        logits = model.forward_decoder_only({
            "decoder_input_ids": decoder_input,
            "encoder_hidden": encoder_hidden,
            "mask_positions": full_mask.float(),
        }, digit=None, use_cache=False).logits
    confidence = torch_module.softmax(logits, dim=-1).max(dim=-1).values
    order = torch_module.argsort(confidence, dim=1, descending=False)[0].detach().cpu().tolist()
    views = []
    for ordinal in range(1, N_DIGIT + 1):
        positions = sorted(int(value) for value in order[:ordinal])
        weights = [1.0 if position in positions else 0.0 for position in range(N_DIGIT)]
        views.append({
            "view_ordinal": ordinal,
            "timestep": ordinal / N_DIGIT,
            "mask_positions": positions,
            "mask_weights": weights,
        })
    return views


def trace_confidence_decode(model: Any, encoder_hidden: Any, tokenizer: Any, torch_module: Any) -> dict[str, Any]:
    from genrec.models.DIFF_GRM.beam import expand_cross_kv_for_beams

    beam_config = model.config["vectorized_beam_search"]
    split_config = beam_config["test"]
    beam_act = int(split_config["beam_act"])
    beam_max = int(split_config["beam_max"])
    if beam_act != 256 or beam_max != 256:
        raise ValueError("formal trace requires the official test beam_act=beam_max=256")
    neg_inf = float(beam_config["neg_inf_fp32"])
    device = encoder_hidden.device
    mask_positions = torch_module.ones(1, N_DIGIT, device=device)
    initial = model.forward_decoder_only({
        "decoder_input_ids": torch_module.zeros(1, N_DIGIT, dtype=torch_module.long, device=device),
        "encoder_hidden": encoder_hidden,
        "mask_positions": mask_positions,
    }, digit=None, use_cache=True)
    initial_log_probs = torch_module.log_softmax(initial.logits, dim=-1)
    flat = initial_log_probs.view(1, -1)
    top_scores, top_indices = torch_module.topk(flat, k=beam_act)
    positions = top_indices // CODEBOOK_SIZE
    tokens = top_indices % CODEBOOK_SIZE
    active_states = torch_module.full(
        (beam_act, N_DIGIT), MASK_TOKEN, dtype=torch_module.long, device=device
    )
    active_states[torch_module.arange(beam_act, device=device), positions[0]] = tokens[0]
    active_scores = top_scores[0]
    active_ids = [f"s1_b{index:03d}" for index in range(beam_act)]
    step1_expansions = [
        expansion_record(
            beam_id=active_ids[index],
            parent_beam_id="root",
            pre_codes=[MASK_TOKEN] * N_DIGIT,
            position=int(positions[0, index]),
            token=int(tokens[0, index]),
            token_log_probability=float(top_scores[0, index]),
            cumulative_log_probability=float(top_scores[0, index]),
            per_position_topk=position_topk(
                initial_log_probs[0],
                list(range(N_DIGIT)),
                selected_position=int(positions[0, index]),
                selected_token=int(tokens[0, index]),
            ),
            retained=True,
        )
        for index in range(beam_act)
    ]
    steps = [{
        "denoising_step": 1,
        "nfe": 1,
        "forward_calls": 1,
        "logits_evaluated": N_DIGIT * CODEBOOK_SIZE,
        "candidate_expansion_count": len(step1_expansions),
        "eligible_candidate_count": N_DIGIT * CODEBOOK_SIZE,
        "visited_state_count": 1 + beam_act,
        "retained_beam_ids": list(active_ids),
        "expanded_candidates": step1_expansions,
    }]

    encoder_expanded = encoder_hidden.unsqueeze(1).repeat(1, beam_max, 1, 1)
    encoder_expanded = encoder_expanded.view(-1, encoder_hidden.size(1), encoder_hidden.size(2))
    kv_cache = expand_cross_kv_for_beams(initial.past_key_values, beam_act)

    for step_number in (2, 3):
        current_masks = active_states.eq(MASK_TOKEN)
        decoder_input = torch_module.clamp(active_states, min=0)
        outputs = model.forward_decoder_only({
            "decoder_input_ids": decoder_input,
            "encoder_hidden": encoder_expanded[:beam_act],
            "mask_positions": current_masks.float(),
        }, digit=None, past_key_values=kv_cache, use_cache=True)
        log_probs = torch_module.log_softmax(
            outputs.logits.view(1, beam_act, N_DIGIT, CODEBOOK_SIZE), dim=-1
        )[0]
        masked = log_probs + (~current_masks).unsqueeze(-1) * neg_inf
        joint = active_scores[:, None, None] + masked
        best_scores, flat_indices = torch_module.topk(joint.reshape(-1), k=beam_act)
        parent_indices = flat_indices // (N_DIGIT * CODEBOOK_SIZE)
        remaining = flat_indices % (N_DIGIT * CODEBOOK_SIZE)
        selected_positions = remaining // CODEBOOK_SIZE
        selected_tokens = remaining % CODEBOOK_SIZE
        new_states = active_states[parent_indices].clone()
        new_states[torch_module.arange(beam_act, device=device), selected_positions] = selected_tokens
        new_ids = [f"s{step_number}_b{index:03d}" for index in range(beam_act)]
        retained: list[dict[str, Any]] = []
        represented_parents: set[int] = set()
        for index in range(beam_act):
            parent = int(parent_indices[index])
            represented_parents.add(parent)
            pre = active_states[parent].detach().cpu().tolist()
            pos = int(selected_positions[index])
            tok = int(selected_tokens[index])
            token_lp = float(log_probs[parent, pos, tok])
            retained.append(expansion_record(
                beam_id=new_ids[index],
                parent_beam_id=active_ids[parent],
                pre_codes=pre,
                position=pos,
                token=tok,
                token_log_probability=token_lp,
                cumulative_log_probability=float(best_scores[index]),
                per_position_topk=position_topk(
                    log_probs[parent],
                    [i for i, value in enumerate(pre) if value == MASK_TOKEN],
                    selected_position=pos,
                    selected_token=tok,
                ),
                retained=True,
            ))
        pruned: list[dict[str, Any]] = []
        for parent in range(beam_act):
            if parent in represented_parents:
                continue
            local = joint[parent].reshape(-1)
            local_index = int(torch_module.argmax(local))
            pos = local_index // CODEBOOK_SIZE
            tok = local_index % CODEBOOK_SIZE
            pre = active_states[parent].detach().cpu().tolist()
            token_lp = float(log_probs[parent, pos, tok])
            pruned.append(expansion_record(
                beam_id=f"s{step_number}_p{parent:03d}",
                parent_beam_id=active_ids[parent],
                pre_codes=pre,
                position=pos,
                token=tok,
                token_log_probability=token_lp,
                cumulative_log_probability=float(local[local_index]),
                per_position_topk=position_topk(
                    log_probs[parent],
                    [i for i, value in enumerate(pre) if value == MASK_TOKEN],
                    selected_position=pos,
                    selected_token=tok,
                ),
                retained=False,
            ))
        steps.append({
            "denoising_step": step_number,
            "nfe": 1,
            "forward_calls": 1,
            "logits_evaluated": beam_act * N_DIGIT * CODEBOOK_SIZE,
            "candidate_expansion_count": len(retained) + len(pruned),
            "eligible_candidate_count": int(current_masks.sum().item()) * CODEBOOK_SIZE,
            "visited_state_count": 1 + beam_act * step_number,
            "retained_beam_ids": list(new_ids),
            "expanded_candidates": retained + pruned,
        })
        active_states = new_states
        active_scores = best_scores
        active_ids = new_ids

    current_masks = active_states.eq(MASK_TOKEN)
    if not bool(current_masks.sum(dim=1).eq(1).all()):
        raise ValueError("DiffGRM final step expected exactly one mask per active beam")
    final_outputs = model.forward_decoder_only({
        "decoder_input_ids": torch_module.clamp(active_states, min=0),
        "encoder_hidden": encoder_expanded[:beam_act],
        "mask_positions": current_masks.float(),
    }, digit=None, past_key_values=kv_cache, use_cache=True)
    final_log_probs = torch_module.log_softmax(
        final_outputs.logits.view(beam_act, N_DIGIT, CODEBOOK_SIZE), dim=-1
    )
    final_positions = torch_module.argmax(current_masks.float(), dim=-1)
    row_indices = torch_module.arange(beam_act, device=device)
    chosen_log_probs, chosen_tokens = torch_module.max(
        final_log_probs[row_indices, final_positions], dim=-1
    )
    final_states = active_states.clone()
    final_states[row_indices, final_positions] = chosen_tokens
    final_scores = active_scores + chosen_log_probs
    final_ids = [f"s4_b{index:03d}" for index in range(beam_act)]
    final_expansions = []
    for index in range(beam_act):
        pre = active_states[index].detach().cpu().tolist()
        position = int(final_positions[index])
        token = int(chosen_tokens[index])
        final_expansions.append(expansion_record(
            beam_id=final_ids[index],
            parent_beam_id=active_ids[index],
            pre_codes=pre,
            position=position,
            token=token,
            token_log_probability=float(chosen_log_probs[index]),
            cumulative_log_probability=float(final_scores[index]),
            per_position_topk=position_topk(
                final_log_probs[index],
                [position],
                selected_position=position,
                selected_token=token,
            ),
            retained=True,
        ))
    steps.append({
        "denoising_step": 4,
        "nfe": 1,
        "forward_calls": 1,
        "logits_evaluated": beam_act * N_DIGIT * CODEBOOK_SIZE,
        "candidate_expansion_count": len(final_expansions),
        "eligible_candidate_count": beam_act * CODEBOOK_SIZE,
        "visited_state_count": 1 + beam_act * 4,
        "retained_beam_ids": final_ids,
        "expanded_candidates": final_expansions,
    })
    order = torch_module.argsort(final_scores, descending=True)
    return {
        "steps": steps,
        "final_states": final_states[order].detach().cpu().tolist(),
        "final_scores": final_scores[order].detach().cpu().tolist(),
        "final_ids": [final_ids[int(index)] for index in order.detach().cpu()],
        # The pinned upstream decoder falls back to active_beam_ids[0] when
        # every final tuple is illegal.  That is the original beam-tensor row,
        # not the highest-scoring row after argsort.
        "all_invalid_fallback_state": final_states[0].detach().cpu().tolist(),
        "beam_act": beam_act,
    }


def resolve_frontier(
    traced: dict[str, Any],
    resolution: dict[tuple[int, ...], list[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[list[int]]]:
    raw_rows: list[dict[str, Any]] = []
    seen_codes: set[tuple[int, ...]] = set()
    official_unique: list[list[int]] = []
    ranked_items: list[dict[str, Any]] = []
    seen_items: set[str] = set()
    for ordinal, (codes_value, score, beam_id) in enumerate(zip(
        traced["final_states"], traced["final_scores"], traced["final_ids"]
    ), start=1):
        codes = tuple(int(value) for value in codes_value)
        matches = resolution.get(codes, [])
        duplicate = codes in seen_codes
        seen_codes.add(codes)
        raw_rows.append({
            "raw_rank": ordinal,
            "beam_id": beam_id,
            "semantic_codes": list(codes),
            "cumulative_log_probability": float(score),
            "raw_validity": "catalog_exact_match" if matches else "invalid_raw_tuple",
            "resolved_normalized_item_ids": list(matches),
            "resolution_state": "unresolved" if not matches else "unique" if len(matches) == 1 else "collision",
            "projection_state": "projection_not_applicable",
            "raw_duplicate": duplicate,
            "raw_generation_success": bool(matches),
        })
        if matches and not duplicate:
            official_unique.append(list(codes))
            for normalized_id in matches:
                if normalized_id in seen_items:
                    continue
                seen_items.add(normalized_id)
                ranked_items.append({
                    "rank": len(ranked_items) + 1,
                    "normalized_item_id": normalized_id,
                    "score": float(score),
                })
                if len(ranked_items) >= 256:
                    break
    if official_unique:
        while len(official_unique) < 10:
            official_unique.append(list(official_unique[-1]))
    else:
        official_unique = [list(traced["all_invalid_fallback_state"])] * 10
    return raw_rows, ranked_items[:256], official_unique[:10]


def run(args: argparse.Namespace) -> dict[str, Any]:
    # CUDA GEMM determinism must be configured before torch initializes CUDA.
    # The trace is compared with a second execution of the pinned upstream
    # decoder, so an unset CUBLAS workspace can turn near-tied legal frontiers
    # into false method-equivalence failures.
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    sys.path.insert(0, str(args.upstream_source.resolve()))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from accelerate import Accelerator
    from torch.utils.data import DataLoader
    import torch
    from genrec.utils import get_config, init_seed
    from genrec.models.DIFF_GRM.tokenizer import DIFF_GRMTokenizer
    from genrec.models.DIFF_GRM.model import DIFF_GRM
    from diffgrm_prepared_dataset import DormantPreparedDataset
    from run_diffgrm_runtime import verify_processed_cache

    torch.use_deterministic_algorithms(True)

    if (args.upstream_source / ".pinned-revision").read_text().strip() != REVISION:
        raise ValueError("DiffGRM source revision mismatch")
    if args.device != "cuda":
        raise ValueError("real masked trace export requires CUDA")
    cache_manifest = verify_processed_cache(args.cache_dir, args.processed_cache_manifest)
    if cache_manifest.get("domain") != args.domain:
        raise ValueError("DiffGRM processed-cache domain mismatch")
    if int(cache_manifest.get("catalog_rows", -1)) != args.expected_catalog_rows:
        raise ValueError("DiffGRM processed-cache catalog denominator mismatch")
    runtime = json.loads(args.runtime_manifest.read_text(encoding="utf-8"))
    prepared = json.loads(args.prepared_dataset.read_text(encoding="utf-8"))
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    selected_indices = validate_selection(selection, runtime)
    if selection.get("prepared_dataset_contract_sha256") != canonical_sha256(prepared):
        raise ValueError("selection-to-prepared canonical binding mismatch")
    overrides = model_overrides(args, torch)
    config = get_config("DIFF_GRM", "AmazonReviews2014", None, overrides)
    accelerator = Accelerator()
    config["accelerator"] = accelerator
    config["device"] = torch.device(args.device)
    config["current_split"] = "test"
    init_seed(args.seed, True)
    dataset = DormantPreparedDataset(config, args.runtime_manifest)
    if dataset.n_items - 1 != args.expected_catalog_rows:
        raise ValueError("DiffGRM runtime catalog denominator mismatch")
    if len(prepared.get("catalog", [])) != args.expected_catalog_rows:
        raise ValueError("DiffGRM prepared catalog denominator mismatch")
    tokenizer = DIFF_GRMTokenizer(config, dataset)
    tokenized = tokenizer.tokenize(dataset.split())
    training_manifest = json.loads(args.training_manifest.read_text(encoding="utf-8"))
    validate_training_binding(
        training_manifest,
        args.checkpoint,
        args.expected_completed_steps,
        domain=args.domain,
        processed_cache_manifest_sha256=sha256_file(args.processed_cache_manifest),
    )
    checkpoint_payload = trusted_torch_load(
        torch, args.checkpoint, map_location=config["device"]
    )
    if int(checkpoint_payload.get("completed_steps", -1)) != args.expected_completed_steps:
        raise ValueError("checkpoint completed-step binding mismatch")
    model = DIFF_GRM(config, dataset, tokenizer).to(config["device"])
    model.load_state_dict(checkpoint_payload["model"], strict=True)
    model.eval()
    selected_rows = tokenized["test"].select(selected_indices)
    loader = DataLoader(selected_rows, batch_size=1, shuffle=False, collate_fn=tokenizer.collate_fn["test"])
    resolution = catalog_resolution(prepared)
    episodes: list[dict[str, Any]] = []
    total_logits = 0
    total_candidates = 0
    total_visited = 0
    from genrec.models.DIFF_GRM.beam import fast_beam_search_for_eval

    for episode_ordinal, (selected_row, batch) in enumerate(
        zip(selection["episodes"], loader), start=1
    ):
        started = time.perf_counter()
        batch = {key: value.to(config["device"]) for key, value in batch.items()}
        with torch.no_grad():
            encoder_hidden = model.forward(batch, return_loss=False).hidden_states
            noising = guided_noising_views(model, encoder_hidden, batch["labels"], torch)
            traced = trace_confidence_decode(model, encoder_hidden, tokenizer, torch)
            # Compare against the pinned upstream decoder on the exact same encoder
            # state. Calling model.generate here would run the encoder a second time;
            # near-tied CUDA scores can then change ordering even though the traced
            # decoder is method-faithful. The shared-state comparison isolates the
            # audited surface: native parallel denoising, legality filtering, and
            # ordered de-duplication.
            official = fast_beam_search_for_eval(
                model=model,
                encoder_hidden=encoder_hidden,
                beam_size=10,
                max_len=model.n_digit,
                tokenizer=tokenizer,
                mode="confidence",
                rand_cfg=model.config.get("random_beam", {}),
            )
        raw_rows, ranked_items, expected_official = resolve_frontier(traced, resolution)
        observed_official = official[0].detach().cpu().tolist()
        if observed_official != expected_official:
            write_json(args.output_dir / "official_equivalence_failure.json", {
                "schema": "sidscope.diffgrm_official_equivalence_failure.v1",
                "episode_ordinal": episode_ordinal,
                "episode_id": str(selected_row["episode_id"]),
                "expected_from_native_trace": expected_official,
                "observed_from_pinned_upstream_decoder": observed_official,
                "checkpoint_sha256": sha256_file(args.checkpoint),
                "selection_sha256": sha256_file(args.selection),
            })
            raise ValueError("native traced frontier does not reproduce official filtered top-10")
        target = str(selected_row["target_normalized_item_id"])
        target_rank = next(
            (int(row["rank"]) for row in ranked_items if row["normalized_item_id"] == target),
            None,
        )
        target_generated = any(target in row["resolved_normalized_item_ids"] for row in raw_rows)
        if not target_generated:
            failure = "generation_search_miss"
        elif target_rank is None or target_rank > 10:
            failure = "ranking_conversion_miss"
        else:
            failure = None
        episodes.append({
            "episode_id": str(selected_row["episode_id"]),
            "target_normalized_item_id": target,
            "gap_bucket": str(selected_row["gap_bucket"]),
            "forward_noising_ocn": noising,
            "attempts": [{
                "attempt_id": "confidence-1",
                "reverse_process": "confidence_guided_parallel_position_decoding",
                "initial_state": [MASK_TOKEN] * N_DIGIT,
                "steps": traced["steps"],
                "raw_final_beams": raw_rows,
            }],
            "ranked_items": ranked_items,
            "target_generated_raw": target_generated,
            "target_resolved": target_generated,
            "target_rank": target_rank,
            "target_rank_state": "observed_exact" if target_rank is not None else "right_censored_beyond_published_depth",
            "termination": "completed",
            "failure_label": failure,
            "latency_ms": (time.perf_counter() - started) * 1000.0,
            "official_filtered_sid_rows": observed_official,
        })
        total_logits += sum(int(step["logits_evaluated"]) for step in traced["steps"])
        total_candidates += sum(int(step["candidate_expansion_count"]) for step in traced["steps"])
        total_visited += int(traced["steps"][-1]["visited_state_count"])
        print(
            f"[DIFFGRM_TRACE] episode={episode_ordinal}/{len(selection['episodes'])} "
            f"id={selected_row['episode_id']} official_top10=PASS",
            flush=True,
        )

    hit_count = sum(
        int(episode["target_rank"] is not None and episode["target_rank"] <= 10)
        for episode in episodes
    )
    ndcg_sum = sum(
        1.0 / math.log2(episode["target_rank"] + 1)
        if episode["target_rank"] is not None and episode["target_rank"] <= 10 else 0.0
        for episode in episodes
    )
    unique_candidates = sum(
        len({tuple(row["semantic_codes"]) for row in episode["attempts"][0]["raw_final_beams"]})
        for episode in episodes
    )
    duplicate_candidates = sum(
        sum(int(row["raw_duplicate"]) for row in episode["attempts"][0]["raw_final_beams"])
        for episode in episodes
    )
    trace_configuration = {
        "domain": args.domain,
        "n_digit": N_DIGIT,
        "codebook_size": CODEBOOK_SIZE,
        "mask_token": MASK_TOKEN,
        "decode_mode": "confidence",
        "adaptive_unmasking": True,
        "beam_act": 256,
        "beam_max": 256,
        "dedup_capture_point": "before_official_legality_filter_dedup_and_padding",
        "seed": args.seed,
    }
    semantic_id_cache = args.cache_dir / "processed" / cache_manifest["semantic_id_filename"]
    evidence = {
        "source_revision": REVISION,
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "configuration_sha256": canonical_sha256(trace_configuration),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "training_manifest_sha256": sha256_file(args.training_manifest),
        "semantic_id_cache_sha256": sha256_file(semantic_id_cache),
        "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
        "prepared_dataset_file_sha256": sha256_file(args.prepared_dataset),
        "episode_selection_file_sha256": sha256_file(args.selection),
        "producer_sha256": sha256_file(Path(__file__)),
        "upstream_source_tree_sha256": SOURCE_TREE_SHA256,
    }
    bundle = {
        "schema": TRACE_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "route_id": "diffgrm_www2026",
        "trace_id": args.trace_id or f"diffgrm-{args.domain}-s{args.seed}-{len(episodes)}ep",
        "source_revision": REVISION,
        "upstream_source_tree_sha256": SOURCE_TREE_SHA256,
        "prepared_dataset_contract_sha256": canonical_sha256(prepared),
        "episode_selection_manifest_sha256": canonical_sha256(selection),
        "prepared_dataset_file_sha256": sha256_file(args.prepared_dataset),
        "episode_selection_file_sha256": sha256_file(args.selection),
        "evidence_kind": args.evidence_kind,
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "completed_training_steps": args.expected_completed_steps,
        "runtime_manifest_sha256": sha256_file(args.runtime_manifest),
        "processed_cache_manifest_sha256": sha256_file(args.processed_cache_manifest),
        "processed_cache_files_sha256": dict(sorted(cache_manifest["files"].items())),
        "producer_sha256": sha256_file(Path(__file__)),
        "configuration": trace_configuration,
        "evidence": evidence,
        "ranking_diagnostic": {
            "evaluation_cutoff": 10,
            "published_rank_depth": 256,
            "absent_target_state": "right_censored_beyond_published_depth",
        },
        "episodes": episodes,
        "summary": {
            "hit_at_10": hit_count / len(episodes),
            "ndcg_at_10": ndcg_sum / len(episodes),
            "recall_at_10_semantics": "single_target_hit_at_10_alias",
            "target_support_count": len(episodes),
            "generation_search_miss_count": sum(int(episode["failure_label"] == "generation_search_miss") for episode in episodes),
            "resolution_loss_count": 0,
            "ranking_conversion_miss_count": sum(int(episode["failure_label"] == "ranking_conversion_miss") for episode in episodes),
            "unique_candidate_count": unique_candidates,
            "duplicate_candidate_count": duplicate_candidates,
            "nfe": N_DIGIT * len(episodes),
            "forward_calls": N_DIGIT * len(episodes),
            "logits_evaluated": total_logits,
            "candidate_expansion_count": total_candidates,
            "visited_state_count": total_visited,
        },
    }
    write_json(args.output_dir / "trained_trace_bundle.json", bundle)
    expected_failure_path = args.output_dir / "expected_failure_unknown_parent.json"
    expected_failure_sha256 = None
    if args.write_expected_failure:
        expected_failure = copy.deepcopy(bundle)
        expected_failure["episodes"][0]["attempts"][0]["steps"][1]["expanded_candidates"][0]["parent_beam_id"] = "missing-parent"
        write_json(expected_failure_path, expected_failure)
        expected_failure_sha256 = sha256_file(expected_failure_path)
    result = {
        "schema": "genrec_dormant.diffgrm_real_trace_export.v1",
        "status": "pass",
        "episode_count": len(episodes),
        "gap_buckets": [episode["gap_bucket"] for episode in episodes],
        "bundle_sha256": sha256_file(args.output_dir / "trained_trace_bundle.json"),
        "expected_failure_sha256": expected_failure_sha256,
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "official_top10_equivalence": True,
        "scientific_result": False,
        "evidence_boundary": "balanced diagnostic subset; not a population performance estimate",
        "next_gate": (
            "SIDScope core validator positive PASS plus typed unknown_parent_beam rejection"
            if args.write_expected_failure
            else "SIDScope core validator positive PASS and compact bottleneck analysis"
        ),
    }
    write_json(args.output_dir / "trace_export_manifest.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--prepared-dataset", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--training-manifest", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--processed-cache-manifest", type=Path, required=True)
    parser.add_argument("--expected-catalog-rows", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--expected-completed-steps", type=int, default=8)
    parser.add_argument("--faiss-threads", type=int, default=32)
    parser.add_argument(
        "--evidence-kind",
        choices=(
            "checkpoint_bound_trained_smoke",
            "checkpoint_bound_trained_diagnostic",
        ),
        default="checkpoint_bound_trained_smoke",
    )
    parser.add_argument("--trace-id")
    parser.set_defaults(write_expected_failure=True)
    parser.add_argument(
        "--skip-expected-failure",
        action="store_false",
        dest="write_expected_failure",
        help="omit the duplicate negative bundle for large positive diagnostics",
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
