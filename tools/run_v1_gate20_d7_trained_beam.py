#!/usr/bin/env python3
"""Run G20 trained-generator D7 traces with trie-constrained beam decoding."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import torch
except ImportError as exc:  # pragma: no cover - environment preflight covers this.
    torch = None  # type: ignore[assignment]
    TORCH_IMPORT_ERROR: Exception | None = exc
else:
    TORCH_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from sidinspector.d7_trace import (  # noqa: E402
    CONSTRAINED_SURVIVABLE,
    deterministic_label_check,
    label_traces,
    summarize_trace_labels,
)
from tools.run_v1_gate10_independent_utility import stable_mod  # noqa: E402
from tools.run_v1_gate12b_sequence_generator_anchor import (  # noqa: E402
    DEFAULT_G2_ROOT,
    SIDEncoding,
    SequenceSIDGenerator,
    _dummy_frames,
    _filter_row_data,
    _load_manifest,
    _select_manifest,
    _with_sequence_order,
    build_sid_encoding,
    make_training_examples,
    train_model,
)


CONTRACT_ID = "G20_D7_TRIE_CONSTRAINED_TRAINED_TRACE"
STRUCTURAL_SURVIVABLE = {
    "ambiguous_path",
    "duplicate_item",
    "duplicate_path",
    "prefix_loop",
    "stale_or_ooc",
}
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate20_d7_failure_rich_trace"
DEFAULT_RUNS_DIR = PROJECT_ROOT / "experiments/v1_evidence_chain/runs"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.sort_index(axis=1).sort_values(list(frame.columns), kind="stable").to_csv(index=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def effective_seed(base_seed: int, manifest_row: int, fold: int) -> int:
    return int(base_seed + manifest_row * 101 + fold)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


@dataclass(frozen=True)
class TrieIndex:
    children: dict[tuple[int, ...], tuple[int, ...]]
    code_to_items: dict[tuple[int, ...], tuple[int, ...]]
    code_to_sid_path: dict[tuple[int, ...], tuple[str, ...]]


@dataclass
class Beam:
    path: tuple[int, ...]
    score: float
    state: Any
    step_logprobs: tuple[float, ...]
    prefix_entropies: tuple[float, ...]


def build_trie_index(encoding: SIDEncoding) -> TrieIndex:
    children: dict[tuple[int, ...], set[int]] = {}
    code_to_items: dict[tuple[int, ...], list[int]] = {}
    code_to_sid_path: dict[tuple[int, ...], tuple[str, ...]] = {}
    for item, code in encoding.item_code.items():
        code_to_items.setdefault(code, []).append(int(item))
        original = encoding.item_sid_path[item]
        previous = code_to_sid_path.setdefault(code, original)
        if previous != original:
            raise ValueError(f"encoded path {code} maps to inconsistent original SID paths")
        for depth, token in enumerate(code):
            children.setdefault(code[:depth], set()).add(int(token))
    return TrieIndex(
        children={prefix: tuple(sorted(tokens)) for prefix, tokens in children.items()},
        code_to_items={code: tuple(sorted(items)) for code, items in code_to_items.items()},
        code_to_sid_path=code_to_sid_path,
    )


def trie_constrained_beam_decode(
    *,
    model: SequenceSIDGenerator,
    history: Any,
    trie: TrieIndex,
    depth: int,
    beam_width: int,
) -> list[Beam]:
    """Decode unique catalog paths while normalizing over valid trie children."""

    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    if beam_width <= 0:
        raise ValueError("beam_width must be positive")
    model.eval()
    with torch.no_grad():
        history_state = model.encode(history)
        initial_state = torch.tanh(model.initial_decoder(history_state))
        beams = [Beam((), 0.0, initial_state, (), ())]
        for level in range(depth):
            expanded: list[Beam] = []
            for beam in beams:
                allowed = trie.children.get(beam.path, ())
                if not allowed:
                    continue
                if level == 0:
                    previous = model.bos.unsqueeze(0)
                else:
                    previous_token = torch.as_tensor(
                        [beam.path[-1] + 1], dtype=torch.long, device=history.device
                    )
                    previous = model.token_embeddings[level - 1](previous_token)
                decoder_input = torch.cat([previous, history_state], dim=1)
                next_state = model.decoder_cell(decoder_input, beam.state)
                logits = model.heads[level](next_state).squeeze(0)
                allowed_tensor = torch.as_tensor(allowed, dtype=torch.long, device=history.device)
                allowed_logits = logits.index_select(0, allowed_tensor)
                log_probs = torch.log_softmax(allowed_logits, dim=0)
                probabilities = torch.exp(log_probs)
                entropy = float((-(probabilities * log_probs)).sum().detach().cpu())
                for offset, token in enumerate(allowed):
                    step_logprob = float(log_probs[offset].detach().cpu())
                    expanded.append(
                        Beam(
                            path=(*beam.path, int(token)),
                            score=beam.score + step_logprob,
                            state=next_state.clone(),
                            step_logprobs=(*beam.step_logprobs, step_logprob),
                            prefix_entropies=(*beam.prefix_entropies, entropy),
                        )
                    )
            beams = sorted(expanded, key=lambda beam: (-beam.score, beam.path))[:beam_width]
            if not beams:
                raise RuntimeError(f"trie-constrained decoding produced no beam at level {level}")
    return beams


def split_g20_events(interactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """Return model-train, evaluation-history, and test-target rows."""

    if "split" in interactions.columns:
        split = interactions["split"].astype(str).str.lower()
        observed = set(split.unique())
        required = {"train", "validation", "test"}
        if required.issubset(observed):
            model_train = interactions[split == "train"].copy()
            eval_history = interactions[split.isin({"train", "validation"})].copy()
            eval_targets = interactions[split == "test"].copy()
            return model_train, eval_history, eval_targets, "test_targets_train_plus_validation_history"
        raise ValueError(f"G20 explicit split must contain train/validation/test; observed={sorted(observed)}")
    ordered = _with_sequence_order(interactions)
    ordered = ordered.sort_values(["user_id", "_g12b_seq_order", "_g12b_row_order"], kind="stable")
    target_index = ordered.groupby("user_id", sort=False).tail(1).index
    eval_targets = ordered.loc[target_index].drop(columns=["_g12b_seq_order", "_g12b_row_order", "_g12b_order_source"])
    eval_history = ordered.drop(index=target_index).drop(
        columns=["_g12b_seq_order", "_g12b_row_order", "_g12b_order_source"]
    )
    return eval_history.copy(), eval_history.copy(), eval_targets.copy(), "chronological_last_event_fallback"


def bootstrap_user_rate(
    frame: pd.DataFrame,
    *,
    value_col: str,
    samples: int,
    seed: int,
) -> dict[str, float | int]:
    if frame.empty:
        return {"users": 0, "targets": 0, "rate": math.nan, "ci_low": math.nan, "ci_high": math.nan}
    user_values = {
        str(user): group[value_col].astype(float).to_numpy()
        for user, group in frame.groupby("user_id", sort=False)
    }
    users = sorted(user_values)
    data = frame[value_col].astype(float).to_numpy()
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(samples):
        sampled_users = rng.choice(users, size=len(users), replace=True)
        sampled_values = np.concatenate([user_values[str(user)] for user in sampled_users])
        estimates.append(float(np.mean(sampled_values)))
    return {
        "users": int(len(users)),
        "targets": int(len(data)),
        "rate": float(np.mean(data)),
        "ci_low": float(np.quantile(estimates, 0.025)),
        "ci_high": float(np.quantile(estimates, 0.975)),
    }


def determine_gate_status(
    *,
    stage: str,
    accounting_pass: bool,
    target_traces: int,
    trace_rows: int,
    beam_width: int,
    structural_nonzero: bool,
    outcome_variation: bool,
) -> tuple[str, str]:
    if stage == "preflight":
        status = "PASS_G20_LOCAL_PREFLIGHT" if accounting_pass else "FAIL_G20_LOCAL_PREFLIGHT"
        return status, "NOT_APPLICABLE"
    if stage == "canary":
        passed = accounting_pass and target_traces >= 100 and beam_width >= 20
        return ("PASS_G20_TRAINED_TRACE_CANARY" if passed else "FAIL_G20_TRAINED_TRACE_CANARY"), "NOT_APPLICABLE"
    run_complete = accounting_pass and target_traces >= 500 and trace_rows >= 10000
    status = "PASS_G20_PRIMARY_RUN_COMPLETE" if run_complete else "FAIL_G20_PRIMARY_INCOMPLETE"
    promotion = (
        "PENDING_G20_REPLICATION_AUDIT"
        if run_complete and structural_nonzero and outcome_variation
        else "BOUNDARY_G20_NOT_FAILURE_RICH"
    )
    return status, promotion


def evaluate_replicated_promotion(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Require the same structural D7 family in two independent completed folds."""

    completed = [result for result in results if result.get("status") == "PASS_G20_PRIMARY_RUN_COMPLETE"]
    folds = {int(result["configuration"]["fold"]) for result in completed}
    seeds = {int(result["configuration"]["effective_seed"]) for result in completed}
    family_sets: list[set[str]] = []
    for result in completed:
        counts = result["analysis"].get("failure_flag_target_counts", {})
        family_sets.append(
            {family for family in STRUCTURAL_SURVIVABLE if int(counts.get(family, 0)) > 0}
        )
    common = set.intersection(*family_sets) if family_sets else set()
    outcome_variation = bool(completed) and all(bool(result.get("target_outcome_variation")) for result in completed)
    passed = len(completed) >= 2 and len(folds) >= 2 and len(seeds) >= 2 and bool(common) and outcome_variation
    return {
        "schema": "sidinspector.g20.replicated_promotion.v1",
        "status": "PASS_G20_FAILURE_RICH_PAPER_PROMOTION" if passed else "BOUNDARY_G20_NOT_REPRODUCIBLE",
        "completed_runs": len(completed),
        "folds": sorted(folds),
        "effective_seeds": sorted(seeds),
        "common_structural_families": sorted(common),
        "outcome_variation_in_all_runs": outcome_variation,
        "replication_rule": "same_nonzero_structural_family_across_two_disjoint_folds_and_effective_seeds",
    }


def prepare_fold(
    *,
    row: pd.Series,
    manifest_row: int,
    sid: pd.DataFrame,
    interactions: pd.DataFrame,
    fold: int,
    folds: int,
    max_users: int,
    max_user_items: int,
    max_history_items: int,
    train_targets_per_user: int,
    max_train_samples: int,
    epochs: int,
    batch_size: int,
    embedding_dim: int,
    hidden_dim: int,
    decoder_dim: int,
    dropout: float,
    learning_rate: float,
    weight_decay: float,
    seed: int,
    device: str,
    num_workers: int,
) -> tuple[SIDEncoding, TrieIndex, SequenceSIDGenerator, dict[str, Any], pd.DataFrame, pd.DataFrame]:
    sid = sid.copy()
    sid["item_id"] = sid["item_id"].astype(int)
    encoding = build_sid_encoding(sid)
    trie = build_trie_index(encoding)
    item_ids = set(encoding.item_to_index)
    train, eval_history, eval_targets, split_protocol = split_g20_events(interactions)
    train = train[train["item_id"].astype(int).isin(item_ids)].copy()
    eval_history = eval_history[eval_history["item_id"].astype(int).isin(item_ids)].copy()
    eval_targets = eval_targets[eval_targets["item_id"].astype(int).isin(item_ids)].copy()
    train_sizes = train[["user_id", "item_id"]].drop_duplicates().groupby("user_id").size()
    eligible = train_sizes[(train_sizes >= 2) & (train_sizes <= max_user_items)].index
    eligible_users = sorted(
        set(eligible).intersection(set(eval_targets["user_id"])),
        key=lambda user: stable_mod(user, 2**31 - 1),
    )
    if max_users > 0:
        eligible_users = eligible_users[:max_users]
    train_users = [user for user in eligible_users if stable_mod(user, folds) != fold]
    eval_users = [user for user in eligible_users if stable_mod(user, folds) == fold]
    if folds == 1:
        train_users = eligible_users
        eval_users = eligible_users
    if not train_users or not eval_users:
        raise ValueError(f"insufficient users for {row['label']} fold {fold}")
    generator_train = train[train["user_id"].isin(train_users)].copy()
    eval_train = eval_history[eval_history["user_id"].isin(eval_users)].copy()
    eval_holdout = eval_targets[eval_targets["user_id"].isin(eval_users)].copy()
    examples, train_user_count = make_training_examples(
        train=generator_train,
        users=train_users,
        encoding=encoding,
        max_history_items=max_history_items,
        targets_per_user=train_targets_per_user,
        max_train_samples=max_train_samples,
    )
    if not examples:
        raise ValueError(f"no training examples for {row['label']} fold {fold}")
    resolved_seed = effective_seed(seed, manifest_row, fold)
    model, train_info = train_model(
        encoding=encoding,
        examples=examples,
        epochs=epochs,
        batch_size=batch_size,
        embedding_dim=embedding_dim,
        hidden_dim=hidden_dim,
        decoder_dim=decoder_dim,
        dropout=dropout,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        seed=resolved_seed,
        device=device,
        num_workers=num_workers,
    )
    train_info.update(
        {
            "eligible_users": len(eligible_users),
            "generator_train_users": train_user_count,
            "generator_train_examples": len(examples),
            "base_seed": int(seed),
            "effective_seed": resolved_seed,
            "split_protocol": split_protocol,
            "split_counts": {
                "model_train_rows": int(len(train)),
                "evaluation_history_rows": int(len(eval_history)),
                "test_target_rows": int(len(eval_targets)),
            },
        }
    )
    return encoding, trie, model, train_info, eval_train, eval_holdout


def export_traces(
    *,
    row: pd.Series,
    manifest_row: int,
    encoding: SIDEncoding,
    trie: TrieIndex,
    model: SequenceSIDGenerator,
    eval_train: pd.DataFrame,
    eval_holdout: pd.DataFrame,
    fold: int,
    folds: int,
    max_history_items: int,
    max_eval_targets: int,
    beam_width: int,
    mapping_revision: str,
    checkpoint_sha256: str,
    configuration_sha256: str,
    base_seed: int,
    effective_seed_value: int,
    split_protocol: str,
    device: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    train_ordered = _with_sequence_order(eval_train)
    holdout_ordered = _with_sequence_order(eval_holdout)
    train_source = str(train_ordered["_g12b_order_source"].iloc[0]) if not train_ordered.empty else ""
    holdout_source = str(holdout_ordered["_g12b_order_source"].iloc[0]) if not holdout_ordered.empty else ""
    comparable_order = bool(train_source == holdout_source and train_source != "stable_input_order")
    train_groups = {user: group.copy() for user, group in train_ordered.groupby("user_id", sort=False)}
    holdout_groups = {user: group.copy() for user, group in holdout_ordered.groupby("user_id", sort=False)}
    users = sorted(set(train_groups).intersection(holdout_groups), key=lambda user: stable_mod(user, 2**31 - 1))
    rows: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    target_count = 0
    started = time.perf_counter()
    for user in users:
        user_train = train_groups[user].sort_values(["_g12b_seq_order", "_g12b_row_order"], kind="stable")
        user_holdout = holdout_groups[user].sort_values(["_g12b_seq_order", "_g12b_row_order"], kind="stable")
        for target_index, (_, target_row) in enumerate(user_holdout.iterrows()):
            if max_eval_targets > 0 and target_count >= max_eval_targets:
                break
            target = int(target_row["item_id"])
            if target not in encoding.item_code:
                continue
            if comparable_order:
                target_order = float(target_row["_g12b_seq_order"])
                history_frame = user_train[user_train["_g12b_seq_order"].astype(float) < target_order]
            else:
                target_order = math.nan
                history_frame = user_train
            history_items = [
                int(item) for item in history_frame["item_id"].tolist() if int(item) in encoding.item_to_index
            ]
            if not history_items or target in set(history_items):
                continue
            history_tail = history_items[-max_history_items:] if max_history_items > 0 else history_items
            history_indices = [encoding.item_to_index[item] for item in history_tail]
            history_tensor = torch.as_tensor([history_indices], dtype=torch.long, device=device)
            beams = trie_constrained_beam_decode(
                model=model,
                history=history_tensor,
                trie=trie,
                depth=len(encoding.level_cols),
                beam_width=beam_width,
            )
            target_code = encoding.item_code[target]
            target_path_rank = next((rank for rank, beam in enumerate(beams, 1) if beam.path == target_code), None)
            target_path_survived = target_path_rank is not None
            target_items = trie.code_to_items[target_code]
            target_uniquely_addressable = len(target_items) == 1
            target_item_uniquely_hit = bool(target_path_survived and target_uniquely_addressable)
            trace_id = (
                f"{row['dataset']}::{row['label']}::fold{fold}::user{user}::"
                f"target{target}::index{target_index}"
            )
            outcomes.append(
                {
                    "trace_id": trace_id,
                    "user_id": str(user),
                    "target_item_id": target,
                    "target_path_rank": target_path_rank,
                    "target_path_survived": target_path_survived,
                    "target_uniquely_addressable": target_uniquely_addressable,
                    "target_item_uniquely_hit": target_item_uniquely_hit,
                    "target_missed": not target_path_survived,
                    "target_ambiguous": bool(target_path_survived and not target_uniquely_addressable),
                }
            )
            for rank, beam in enumerate(beams, 1):
                resolved_items = trie.code_to_items[beam.path]
                rows.append(
                    {
                        "artifact_id": str(row["label"]),
                        "mapping_revision": mapping_revision,
                        "dataset": str(row["dataset"]),
                        "label": str(row["label"]),
                        "method": str(row["method"]),
                        "manifest_row": int(manifest_row),
                        "fold": int(fold),
                        "folds": int(folds),
                        "trace_id": trace_id,
                        "user_id": str(user),
                        "target_item_id": target,
                        "target_order": target_order,
                        "rank": rank,
                        "sid_path": "-".join(trie.code_to_sid_path[beam.path]),
                        "generated_code": json.dumps(beam.path),
                        "score": beam.score,
                        "step_logprob": json.dumps(beam.step_logprobs),
                        "prefix_entropy": json.dumps(beam.prefix_entropies),
                        "resolved_item_ids_exporter": ";".join(str(item) for item in resolved_items),
                        "resolved_item_count_exporter": len(resolved_items),
                        "target_item_in_resolved_set": target in resolved_items,
                        "target_path_survived": target_path_survived,
                        "target_item_uniquely_hit": target_item_uniquely_hit,
                        "target_missed": not target_path_survived,
                        "beam_width": beam_width,
                        "decoding_mode": "trie_constrained_beam",
                        "trace_source": "g20_trained_sequence_generator",
                        "model": "gru_history_autoregressive_sid_sequence_generator",
                        "checkpoint_sha256": checkpoint_sha256,
                        "configuration_sha256": configuration_sha256,
                        "score_semantics": "sum_trie_child_log_softmax",
                        "base_seed": base_seed,
                        "effective_seed": effective_seed_value,
                        "history_count": len(history_items),
                        "split_protocol": split_protocol,
                        "temporal_history_mode": (
                            "per_target_history" if comparable_order else "full_train_history_no_explicit_order"
                        ),
                    }
                )
            target_count += 1
        if max_eval_targets > 0 and target_count >= max_eval_targets:
            break
    traces = pd.DataFrame(rows)
    outcome_frame = pd.DataFrame(outcomes)
    if traces.empty or outcome_frame.empty:
        raise RuntimeError("G20 produced no target traces")
    traces.attrs["decode_sec"] = time.perf_counter() - started
    return traces, outcome_frame


def analyze_traces(
    *,
    sid: pd.DataFrame,
    traces: pd.DataFrame,
    outcomes: pd.DataFrame,
    bootstrap_samples: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    active = {str(value) for value in sid["item_id"].dropna().astype(int)}
    labels = label_traces(sid=sid, traces=traces, active_item_ids=active)
    deterministic = deterministic_label_check(sid=sid, traces=traces, active_item_ids=active)
    merged = traces.merge(labels, on=["trace_id", "user_id", "rank"], how="left", validate="one_to_one")
    def canonical_resolution(value: Any) -> str:
        if value is None or pd.isna(value) or not str(value):
            return ""
        return ";".join(sorted(str(value).split(";"), key=lambda item: (not item.isdigit(), item)))

    exporter_resolution = merged["resolved_item_ids_exporter"].map(canonical_resolution)
    labeler_resolution = merged["resolved_item_ids"].map(canonical_resolution)
    resolution_match = bool((exporter_resolution == labeler_resolution).all())
    flag_families = sorted({flag for value in labels["failure_flags"] for flag in str(value).split("|") if flag})
    flag_rows: list[dict[str, Any]] = []
    for label_row in labels.itertuples(index=False):
        present = {flag for flag in str(label_row.failure_flags).split("|") if flag}
        flag_rows.append({"trace_id": str(label_row.trace_id), **{family: int(family in present) for family in flag_families}})
    trace_flags = pd.DataFrame(flag_rows).groupby("trace_id", as_index=False)[flag_families].max()
    target_analysis = outcomes.merge(trace_flags, on="trace_id", how="left")
    for column in trace_flags.columns:
        if column != "trace_id":
            target_analysis[column] = pd.to_numeric(target_analysis[column], errors="coerce").fillna(0).astype(int)
    family_rates: dict[str, dict[str, Any]] = {}
    for family in sorted(CONSTRAINED_SURVIVABLE - {"valid_hit"}):
        if family == "high_uncertainty" and not labels["max_prefix_entropy"].notna().any():
            family_rates[family] = {
                "available": False,
                "reason": "prefix_entropy_not_exported",
                "users": int(target_analysis["user_id"].nunique()),
                "targets": int(len(target_analysis)),
                "rate": None,
                "ci_low": None,
                "ci_high": None,
            }
            continue
        values = target_analysis[family] if family in target_analysis else pd.Series(np.zeros(len(target_analysis)))
        rate_frame = target_analysis[["user_id"]].copy()
        rate_frame[family] = values.to_numpy()
        family_rates[family] = bootstrap_user_rate(
            rate_frame, value_col=family, samples=bootstrap_samples, seed=seed + len(family_rates) * 97
        )
        if family == "high_uncertainty":
            family_rates[family]["available"] = True
    for outcome in ("target_missed", "target_ambiguous", "target_path_survived", "target_item_uniquely_hit"):
        family_rates[outcome] = bootstrap_user_rate(
            target_analysis[["user_id", outcome]],
            value_col=outcome,
            samples=bootstrap_samples,
            seed=seed + len(family_rates) * 97,
        )
    overlap_rows: list[dict[str, Any]] = []
    overlap_families = [family for family in flag_families if family != "valid_hit"]
    for left_index, left in enumerate(overlap_families):
        for right in overlap_families[left_index:]:
            both = target_analysis[left].astype(bool) & target_analysis[right].astype(bool)
            overlap_rows.append(
                {
                    "failure_left": left,
                    "failure_right": right,
                    "target_count": int(both.sum()),
                    "target_rate": float(both.mean()),
                }
            )
    overlap = pd.DataFrame(overlap_rows)
    strata_rows: list[dict[str, Any]] = []
    for family in overlap_families:
        for missed, group in target_analysis.groupby("target_missed", dropna=False):
            strata_rows.append(
                {
                    "failure_family": family,
                    "target_missed": bool(missed),
                    "targets": int(len(group)),
                    "family_target_count": int(group[family].sum()),
                    "family_target_rate": float(group[family].mean()),
                }
            )
    outcome_strata = pd.DataFrame(strata_rows)
    summary = summarize_trace_labels(labels)
    result = {
        "deterministic_label_check": bool(deterministic),
        "exporter_labeler_resolution_match": resolution_match,
        "trace_rows": int(len(traces)),
        "target_traces": int(traces["trace_id"].nunique()),
        "beam_widths": sorted(int(value) for value in traces["beam_width"].unique()),
        "decoding_modes": sorted(str(value) for value in traces["decoding_mode"].unique()),
        "invalid_path_rows": int((labels["primary_failure"] == "invalid_path").sum()),
        "unique_paths_per_trace": bool(not traces.duplicated(["trace_id", "sid_path"]).any()),
        "family_rates": family_rates,
        "primary_failure_counts": {
            str(row.primary_failure): int(row.rows) for row in summary.itertuples(index=False)
        },
        "failure_flag_target_counts": {
            family: int(target_analysis[family].sum()) for family in overlap_families
        },
        "bootstrap_unit": "user_cluster",
    }
    return merged, target_analysis, overlap, outcome_strata, result


def enforce_g20_contract(
    *,
    traces: pd.DataFrame,
    outcomes: pd.DataFrame,
    analysis: dict[str, Any],
    beam_width: int,
    mapping_revision: str,
    checkpoint_sha256: str,
    configuration_sha256: str,
    effective_seed_value: int,
    split_protocol: str,
) -> None:
    required = {
        "artifact_id",
        "mapping_revision",
        "dataset",
        "fold",
        "decoding_mode",
        "trace_id",
        "user_id",
        "target_item_id",
        "sid_path",
        "rank",
        "score",
        "step_logprob",
        "prefix_entropy",
        "beam_width",
        "checkpoint_sha256",
        "configuration_sha256",
        "score_semantics",
        "base_seed",
        "effective_seed",
        "split_protocol",
    }
    missing = sorted(required - set(traces.columns))
    if missing:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: missing trace fields {missing}")
    if traces.empty or outcomes.empty:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: empty traces or outcomes")
    if set(traces["decoding_mode"].astype(str)) != {"trie_constrained_beam"}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: decoding mode is not exclusively trie constrained")
    if set(traces["mapping_revision"].astype(str)) != {mapping_revision}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: mapping revision drift")
    if set(traces["checkpoint_sha256"].astype(str)) != {checkpoint_sha256}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: checkpoint identity drift")
    if set(traces["configuration_sha256"].astype(str)) != {configuration_sha256}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: configuration identity drift")
    if set(traces["score_semantics"].astype(str)) != {"sum_trie_child_log_softmax"}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: score semantics drift")
    if set(traces["effective_seed"].astype(int)) != {effective_seed_value}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: effective seed drift")
    if set(traces["split_protocol"].astype(str)) != {split_protocol}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: split protocol drift")
    if set(traces["beam_width"].astype(int)) != {beam_width}:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: beam-width metadata drift")
    target_ids = set(outcomes["trace_id"].astype(str))
    trace_ids = set(traces["trace_id"].astype(str))
    if target_ids != trace_ids or outcomes["trace_id"].duplicated().any():
        raise RuntimeError(f"{CONTRACT_ID} FAIL: target outcome join is not one-to-one and complete")
    expected_ranks = list(range(1, beam_width + 1))
    for trace_id, group in traces.groupby("trace_id", sort=False):
        if sorted(group["rank"].astype(int).tolist()) != expected_ranks:
            raise RuntimeError(f"{CONTRACT_ID} FAIL: incomplete ranks for trace {trace_id}")
    if not bool(analysis.get("deterministic_label_check")):
        raise RuntimeError(f"{CONTRACT_ID} FAIL: D7 labels are not deterministic")
    if not bool(analysis.get("exporter_labeler_resolution_match")):
        raise RuntimeError(f"{CONTRACT_ID} FAIL: exporter and labeler reverse lookups disagree")
    if int(analysis.get("invalid_path_rows", -1)) != 0:
        raise RuntimeError(f"{CONTRACT_ID} FAIL: constrained decoder emitted invalid paths")
    if not bool(analysis.get("unique_paths_per_trace")):
        raise RuntimeError(f"{CONTRACT_ID} FAIL: duplicate beam paths were emitted")


def write_report(result: dict[str, Any], output_root: Path) -> None:
    lines = [
        "# G20 D7 Trained Beam Result",
        "",
        f"- status: `{result['status']}`",
        f"- stage: `{result['stage']}`",
        f"- artifact: `{result['artifact_id']}`",
        f"- decoding: `trie_constrained_beam`",
        f"- target traces: `{result['analysis']['target_traces']}`",
        f"- per-beam rows: `{result['analysis']['trace_rows']}`",
        f"- deterministic labels: `{str(result['analysis']['deterministic_label_check']).lower()}`",
        f"- bootstrap unit: `{result['analysis']['bootstrap_unit']}`",
        f"- paper promotion: `{result['paper_promotion_status']}`",
        "",
        "## Failure And Outcome Rates",
        "",
        "| Family/outcome | Rate | 95% user-cluster bootstrap CI |",
        "| --- | ---: | ---: |",
    ]
    for name, row in result["analysis"]["family_rates"].items():
        if row.get("available", True):
            lines.append(f"| `{name}` | {row['rate']:.4f} | [{row['ci_low']:.4f}, {row['ci_high']:.4f}] |")
        else:
            lines.append(f"| `{name}` | unavailable | {row['reason']} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This run demonstrates trained, constrained D7 trace observability and outcome joins. "
            "It does not establish a generator failure mechanism or D1--D5 predictivity.",
        ]
    )
    (output_root / "G20_RESULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g2-root", type=Path, default=DEFAULT_G2_ROOT)
    parser.add_argument("--manifest-path", type=Path)
    parser.add_argument("--path-rewrite", action="append", default=[])
    parser.add_argument("--artifact-label", default="grid_faithful_p5_beauty")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--run-id", default="R806_g20_d7_trained_beam")
    parser.add_argument("--stage", choices=("preflight", "canary", "primary"), default="preflight")
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--folds", type=int, default=2)
    parser.add_argument("--max-users", type=int, default=6000)
    parser.add_argument("--max-user-items", type=int, default=200)
    parser.add_argument("--max-history-items", type=int, default=50)
    parser.add_argument("--train-targets-per-user", type=int, default=3)
    parser.add_argument("--max-train-samples", type=int, default=50000)
    parser.add_argument("--max-eval-targets", type=int, default=500)
    parser.add_argument("--beam-width", type=int, default=20)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--embedding-dim", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--decoder-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--dummy", action="store_true")
    parser.add_argument("--validate-inputs-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    args.output_root.mkdir(parents=True, exist_ok=True)
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    if args.dummy:
        row, manifest_row, sid, interactions = _dummy_frames()
        args.artifact_label = str(row["label"])
        args.folds = 1
        args.fold = 0
        args.max_users = 100
        args.max_train_samples = 200
        args.max_eval_targets = min(args.max_eval_targets, 20)
        args.epochs = 1
        args.batch_size = 8
        args.embedding_dim = 32
        args.hidden_dim = 64
        args.decoder_dim = 64
        args.device = "cpu"
        args.bootstrap_samples = min(args.bootstrap_samples, 100)
        mapping_revision = frame_sha256(sid)
        interactions_revision = frame_sha256(interactions)
        mapping_path = "dummy_in_memory"
        interactions_path = "dummy_in_memory"
    else:
        manifest = _load_manifest(args.g2_root, args.manifest_path, args.path_rewrite)
        selected = _select_manifest(manifest, [args.artifact_label], 1)
        manifest_row, row = next(selected.iterrows())
        sid, _, interactions = _filter_row_data(row)
        mapping_file = Path(str(row["sid_assignments"]))
        mapping_revision = sha256(mapping_file)
        mapping_path = str(mapping_file)
        interactions_file = Path(str(row["interactions"]))
        interactions_revision = sha256(interactions_file)
        interactions_path = str(interactions_file)
    if args.validate_inputs_only:
        result = {
            "schema": "sidinspector.g20.input_preflight.v1",
            "status": "pass",
            "artifact_id": str(row["label"]),
            "mapping_path": mapping_path,
            "mapping_revision": mapping_revision,
            "sid_rows": int(len(sid)),
            "interaction_rows": int(len(interactions)),
            "interactions_path": interactions_path,
            "interactions_revision": interactions_revision,
        }
        (args.output_root / "g20_input_preflight.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    started = time.perf_counter()
    encoding, trie, model, train_info, eval_train, eval_holdout = prepare_fold(
        row=row,
        manifest_row=int(manifest_row),
        sid=sid,
        interactions=interactions,
        fold=args.fold,
        folds=args.folds,
        max_users=args.max_users,
        max_user_items=args.max_user_items,
        max_history_items=args.max_history_items,
        train_targets_per_user=args.train_targets_per_user,
        max_train_samples=args.max_train_samples,
        epochs=args.epochs,
        batch_size=args.batch_size,
        embedding_dim=args.embedding_dim,
        hidden_dim=args.hidden_dim,
        decoder_dim=args.decoder_dim,
        dropout=args.dropout,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        seed=args.seed,
        device=args.device,
        num_workers=args.num_workers,
    )
    resolved_seed = int(train_info["effective_seed"])
    split_protocol = str(train_info["split_protocol"])
    configuration = json_safe(
        {
            "contract": CONTRACT_ID,
            "artifact_id": str(row["label"]),
            "dataset": str(row["dataset"]),
            "manifest_row": int(manifest_row),
            "fold": args.fold,
            "folds": args.folds,
            "stage": args.stage,
            "mapping_revision": mapping_revision,
            "interactions_revision": interactions_revision,
            "split_protocol": split_protocol,
            "split_counts": train_info["split_counts"],
            "base_seed": args.seed,
            "effective_seed": resolved_seed,
            "beam_width": args.beam_width,
            "max_eval_targets": args.max_eval_targets,
            "bootstrap_samples": args.bootstrap_samples,
            "requested_device": args.device,
            "resolved_device": train_info["device"],
            "num_workers": args.num_workers,
            "training": {
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "embedding_dim": args.embedding_dim,
                "hidden_dim": args.hidden_dim,
                "decoder_dim": args.decoder_dim,
                "dropout": args.dropout,
                "learning_rate": args.learning_rate,
                "weight_decay": args.weight_decay,
                "max_users": args.max_users,
                "max_user_items": args.max_user_items,
                "max_history_items": args.max_history_items,
                "train_targets_per_user": args.train_targets_per_user,
                "max_train_samples": args.max_train_samples,
            },
            "model": "gru_history_autoregressive_sid_sequence_generator",
            "score_semantics": "sum_trie_child_log_softmax",
        }
    )
    configuration_hash = json_sha256(configuration)
    checkpoint_path = args.output_root / "g20_model.pt"
    torch.save(
        {
            "contract": CONTRACT_ID,
            "artifact_id": str(row["label"]),
            "mapping_revision": mapping_revision,
            "interactions_revision": interactions_revision,
            "configuration": configuration,
            "configuration_sha256": configuration_hash,
            "split_protocol": split_protocol,
            "model_state_dict": model.state_dict(),
            "level_vocab_sizes": encoding.level_vocab_sizes,
            "base_seed": args.seed,
            "effective_seed": resolved_seed,
        },
        checkpoint_path,
    )
    checkpoint_hash = sha256(checkpoint_path)
    traces, outcomes = export_traces(
        row=row,
        manifest_row=int(manifest_row),
        encoding=encoding,
        trie=trie,
        model=model,
        eval_train=eval_train,
        eval_holdout=eval_holdout,
        fold=args.fold,
        folds=args.folds,
        max_history_items=args.max_history_items,
        max_eval_targets=args.max_eval_targets,
        beam_width=args.beam_width,
        mapping_revision=mapping_revision,
        checkpoint_sha256=checkpoint_hash,
        configuration_sha256=configuration_hash,
        base_seed=args.seed,
        effective_seed_value=resolved_seed,
        split_protocol=split_protocol,
        device=train_info["device"],
    )
    labeled, target_analysis, overlap, outcome_strata, analysis = analyze_traces(
        sid=sid,
        traces=traces,
        outcomes=outcomes,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    enforce_g20_contract(
        traces=traces,
        outcomes=outcomes,
        analysis=analysis,
        beam_width=args.beam_width,
        mapping_revision=mapping_revision,
        checkpoint_sha256=checkpoint_hash,
        configuration_sha256=configuration_hash,
        effective_seed_value=resolved_seed,
        split_protocol=split_protocol,
    )
    trace_path = args.output_root / "g20_trained_beam_traces.csv"
    labeled_path = args.output_root / "g20_labeled_beam_traces.csv"
    target_path = args.output_root / "g20_target_outcomes.csv"
    summary_path = args.output_root / "g20_label_summary.csv"
    overlap_path = args.output_root / "g20_failure_overlap.csv"
    strata_path = args.output_root / "g20_failure_outcome_strata.csv"
    traces.to_csv(trace_path, index=False)
    labeled.to_csv(labeled_path, index=False)
    target_analysis.to_csv(target_path, index=False)
    overlap.to_csv(overlap_path, index=False)
    outcome_strata.to_csv(strata_path, index=False)
    summarize_trace_labels(label_traces(sid=sid, traces=traces)).to_csv(summary_path, index=False)
    constrained_nonzero = any(
        row_data["rate"] > 0
        for name, row_data in analysis["family_rates"].items()
        if name in STRUCTURAL_SURVIVABLE
    )
    outcome_variation = bool(target_analysis["target_missed"].nunique() > 1)
    accounting_pass = bool(
        analysis["deterministic_label_check"]
        and analysis["exporter_labeler_resolution_match"]
        and analysis["invalid_path_rows"] == 0
        and analysis["unique_paths_per_trace"]
        and analysis["trace_rows"] == analysis["target_traces"] * args.beam_width
    )
    status, paper_promotion_status = determine_gate_status(
        stage=args.stage,
        accounting_pass=accounting_pass,
        target_traces=int(analysis["target_traces"]),
        trace_rows=int(analysis["trace_rows"]),
        beam_width=args.beam_width,
        structural_nonzero=constrained_nonzero,
        outcome_variation=outcome_variation,
    )
    result = json_safe(
        {
            "schema": "sidinspector.g20.trained_beam_trace.v1",
            "run_id": args.run_id,
            "gate": "G20",
            "status": status,
            "stage": args.stage,
            "artifact_id": str(row["label"]),
            "method": str(row["method"]),
            "dataset": str(row["dataset"]),
            "manifest_row": int(manifest_row),
            "mapping_path": mapping_path,
            "mapping_revision": mapping_revision,
            "interactions_path": interactions_path,
            "interactions_revision": interactions_revision,
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": checkpoint_hash,
            "configuration": configuration,
            "configuration_sha256": configuration_hash,
            "train": train_info,
            "analysis": analysis,
            "accounting_pass": accounting_pass,
            "paper_promotion_status": paper_promotion_status,
            "constrained_failure_family_nonzero": constrained_nonzero,
            "target_outcome_variation": outcome_variation,
            "elapsed_sec": time.perf_counter() - started,
            "artifacts": {
                "raw_traces": str(trace_path),
                "labeled_traces": str(labeled_path),
                "target_outcomes": str(target_path),
                "label_summary": str(summary_path),
                "failure_overlap": str(overlap_path),
                "failure_outcome_strata": str(strata_path),
            },
            "claim_boundary": (
                "D7 trained trie-constrained trace observability and outcome accounting only; "
                "no generator failure mechanism or D1-D5 predictivity claim."
            ),
        }
    )
    result_path = args.output_root / "g20_result.json"
    run_path = args.runs_dir / f"{args.run_id}.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result, args.output_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if status.startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
