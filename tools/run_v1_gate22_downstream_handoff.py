#!/usr/bin/env python3
"""Evaluate the DACT 0.6-to-0.7 SID repair as a three-state generator handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import torch
except ImportError as exc:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    TORCH_IMPORT_ERROR: Exception | None = exc
else:
    TORCH_IMPORT_ERROR = None

try:
    import transformers
except ImportError:  # pragma: no cover
    transformers = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.run_v1_gate20_d7_trained_beam import json_safe, sha256  # noqa: E402
from tools.run_v1_gate21_tiger_d7_trace import (  # noqa: E402
    DEFAULT_DACT_ROOT,
    MODEL_CONFIG,
    build_trie,
    load_mapping,
    load_model,
    sid_frame,
    source_revision,
)
from sidinspector.trace_analysis import analyze_traces  # noqa: E402


CONTRACT_ID = "G22_DACT_THREE_STATE_GENERATOR_HANDOFF"
PRIMARY_SEEDS = (2025, 2026, 2027)
COMMON_RECOVERY_FRACTION = 0.90
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate22_diagnose_repair_reaudit/downstream"
DEFAULT_EXPECTED_INPUTS = (
    PROJECT_ROOT
    / "experiments/v1_evidence_chain/gate22_diagnose_repair_reaudit/G22_EXPECTED_INPUT_SHA256.json"
)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def stable_key(*parts: Any) -> int:
    payload = "::".join(str(part) for part in parts)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


def validate_expected_inputs(
    *, expected_path: Path, dact_root: Path, paths: dict[str, Path]
) -> dict[str, Any]:
    if not expected_path.exists():
        raise FileNotFoundError(f"G22 expected-input manifest is missing: {expected_path}")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    mapping_audit = json.loads(paths["mapping_audit_result"].read_text(encoding="utf-8"))
    if mapping_audit.get("status") != "PASS_G22_MAPPING_REAUDIT":
        raise RuntimeError("G22 downstream handoff requires a PASS_G22_MAPPING_REAUDIT input")
    observed_assets = {
        "source_revision": source_revision(dact_root),
        **{f"{name}_sha256": sha256(path) for name, path in paths.items()},
    }
    runtime = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "torch": str(torch.__version__),
        "transformers": str(transformers.__version__) if transformers is not None else "unavailable",
    }
    mismatches = {
        key: {"expected": expected.get(key), "observed": value}
        for key, value in observed_assets.items()
        if expected.get(key) != value
    }
    allowed_profiles = expected.get("allowed_runtime_profiles", [])
    matched_profile = next(
        (
            profile
            for profile in allowed_profiles
            if all(runtime[key] == str(profile.get(key)) for key in ("python", "torch", "transformers"))
        ),
        None,
    )
    if matched_profile is None:
        mismatches["runtime_profile"] = {"expected": allowed_profiles, "observed": runtime}
    if mismatches:
        raise RuntimeError(f"G22 expected-input mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return {
        "status": "PASS",
        "manifest": str(expected_path),
        **observed_assets,
        **runtime,
        "runtime_profile": matched_profile.get("name"),
    }


def load_period_examples(test_path: Path, *, max_targets: int) -> list[dict[str, Any]]:
    frame = pd.read_parquet(test_path)
    required = {"user", "history", "target"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"period test split missing columns: {missing}")
    rows = []
    for row_index, row in enumerate(frame.itertuples(index=False)):
        history = [int(item) for item in list(row.history)]
        if not history:
            raise ValueError(f"period test row {row_index} has empty history")
        rows.append(
            {
                "released_row_index": row_index,
                "user_id": str(row.user),
                "history_items": history,
                "target_item_id": int(row.target),
            }
        )
    rows.sort(key=lambda row: (stable_key(row["user_id"], row["target_item_id"]), row["released_row_index"]))
    if max_targets > 0:
        rows = rows[:max_targets]
    return rows


def encode_state_history(
    examples: list[dict[str, Any]],
    item_to_code: dict[int, tuple[int, ...]],
    *,
    max_history_items: int,
) -> tuple[Any, Any, list[int]]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    depth = len(next(iter(item_to_code.values())))
    encoded: list[list[int]] = []
    masks: list[list[int]] = []
    missing_counts: list[int] = []
    for example in examples:
        history = example["history_items"][-max_history_items:]
        missing_count = sum(int(item not in item_to_code) for item in history)
        codes = [item_to_code.get(item, (0,) * depth) for item in history]
        codes = [(0,) * depth] * (max_history_items - len(codes)) + codes
        flat = [token for code in codes for token in code]
        encoded.append(flat)
        masks.append([int(token != 0) for token in flat])
        missing_counts.append(missing_count)
    return (
        torch.tensor(encoded, dtype=torch.long),
        torch.tensor(masks, dtype=torch.long),
        missing_counts,
    )


def evaluate_state(
    *,
    model: Any,
    state_name: str,
    examples: list[dict[str, Any]],
    item_to_code: dict[int, tuple[int, ...]],
    reverse: dict[tuple[int, ...], tuple[int, ...]],
    constraint_fn: Any,
    new_item_ids: set[int],
    beam_width: int,
    batch_size: int,
    max_history_items: int,
    device: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    depth = len(next(iter(item_to_code.values())))
    beam_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    model.eval()
    for start in range(0, len(examples), batch_size):
        batch = examples[start : start + batch_size]
        input_ids, attention_mask, history_missing = encode_state_history(
            batch, item_to_code, max_history_items=max_history_items
        )
        with torch.no_grad():
            generated = model.generate(
                input_ids=input_ids.to(device),
                attention_mask=attention_mask.to(device),
                num_beams=beam_width,
                prefix_allowed_tokens_fn=constraint_fn,
                return_dict_in_generate=True,
                output_scores=True,
            )
        sequences = generated.sequences.detach().cpu().reshape(len(batch), beam_width, -1)
        sequence_scores = generated.sequences_scores.detach().cpu().reshape(len(batch), beam_width)
        for batch_index, example in enumerate(batch):
            decoded = []
            for beam_index in range(beam_width):
                sequence = tuple(int(token) for token in sequences[batch_index, beam_index].tolist()[1 : 1 + depth])
                score = float(sequence_scores[batch_index, beam_index])
                if len(sequence) != depth or 0 in sequence:
                    raise RuntimeError(f"{state_name} constrained beam produced an incomplete SID")
                decoded.append((score, sequence))
            decoded.sort(key=lambda value: (-value[0], value[1]))
            scores = np.asarray([score for score, _ in decoded], dtype=float)
            if not np.isfinite(scores).all() or np.any(scores[:-1] < scores[1:] - 1e-12):
                raise RuntimeError(f"{state_name} beam scores violate the declared order")
            target = int(example["target_item_id"])
            target_code = item_to_code.get(target)
            target_rank = None
            if target_code is not None:
                target_rank = next(
                    (rank for rank, (_, code) in enumerate(decoded, start=1) if code == target_code), None
                )
            target_resolved = reverse.get(target_code, ()) if target_code is not None else ()
            unique_rank = target_rank if len(target_resolved) == 1 else None
            target_stratum = "new" if target in new_item_ids else "common"
            trace_id = f"G22::{state_name}::row{example['released_row_index']}"
            outcome_rows.append(
                {
                    "trace_id": trace_id,
                    "state": state_name,
                    "released_row_index": int(example["released_row_index"]),
                    "user_id": example["user_id"],
                    "target_item_id": target,
                    "target_stratum": target_stratum,
                    "target_mapped": target_code is not None,
                    "target_path_rank": target_rank,
                    "target_unique_item_rank": unique_rank,
                    "target_path_survived": target_rank is not None,
                    "target_uniquely_addressable": len(target_resolved) == 1,
                    "target_item_uniquely_hit": unique_rank is not None,
                    "target_missed": target_rank is None,
                    "target_ambiguous": bool(target_rank is not None and len(target_resolved) > 1),
                    "target_address_ambiguity": len(target_resolved),
                    "history_missing_item_count": history_missing[batch_index],
                    "history_contains_new_item": any(item in new_item_ids for item in example["history_items"]),
                    "decoding_mode": "constrained",
                }
            )
            for rank, (score, code) in enumerate(decoded, start=1):
                resolved = reverse.get(code, ())
                beam_rows.append(
                    {
                        "trace_id": trace_id,
                        "state": state_name,
                        "user_id": example["user_id"],
                        "target_item_id": target,
                        "rank": rank,
                        "score": score,
                        "sid_path": "-".join(str(token) for token in code),
                        "resolved_item_count": len(resolved),
                        "resolved_item_ids_exporter": ";".join(str(item) for item in resolved),
                        "target_item_in_resolved_set": target in resolved,
                        "beam_width": beam_width,
                        "decoding_mode": "constrained_beam",
                    }
                )
    outcomes = pd.DataFrame(outcome_rows)
    beams = pd.DataFrame(beam_rows)
    expected_rows = len(examples) * beam_width
    if len(outcomes) != len(examples) or outcomes["trace_id"].nunique() != len(examples):
        raise RuntimeError(f"{state_name} outcome accounting failed")
    if len(beams) != expected_rows or beams["trace_id"].nunique() != len(examples):
        raise RuntimeError(f"{state_name} beam accounting failed")
    for _, group in beams.groupby("trace_id", sort=False):
        if group.sort_values("rank")["rank"].tolist() != list(range(1, beam_width + 1)):
            raise RuntimeError(f"{state_name} beam ranks are incomplete")
    return outcomes, beams


def rank_metrics(frame: pd.DataFrame, rank_column: str) -> dict[str, float]:
    ranks = pd.to_numeric(frame[rank_column], errors="coerce")
    result: dict[str, float] = {}
    for cutoff in (5, 10, 20):
        hit = ranks.notna() & (ranks <= cutoff)
        result[f"Recall@{cutoff}"] = float(hit.mean())
        gain = np.where(hit, 1.0 / np.log2(ranks.fillna(cutoff + 1).to_numpy() + 1.0), 0.0)
        result[f"NDCG@{cutoff}"] = float(np.mean(gain))
    return result


def summarize_outcomes(outcomes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [("overall", outcomes)]
    groups.extend((str(name), group) for name, group in outcomes.groupby("target_stratum", sort=True))
    for stratum, frame in groups:
        rows.append(
            {
                "state": str(frame["state"].iloc[0]),
                "target_stratum": stratum,
                "targets": len(frame),
                "mapped_target_rate": float(frame["target_mapped"].mean()),
                "mean_missing_history_items": float(frame["history_missing_item_count"].mean()),
                **{f"path_{key}": value for key, value in rank_metrics(frame, "target_path_rank").items()},
                **{f"item_{key}": value for key, value in rank_metrics(frame, "target_unique_item_rank").items()},
            }
        )
    return pd.DataFrame(rows)


def write_d7_accounting(
    *,
    state_name: str,
    item_to_code: dict[int, tuple[int, ...]],
    outcomes: pd.DataFrame,
    beams: pd.DataFrame,
    output_dir: Path,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    """Run the same normalized D7 label and accounting contract used by G21."""

    labeled, target_analysis, overlap, outcome_strata, result = analyze_traces(
        sid=sid_frame(item_to_code),
        traces=beams,
        outcomes=outcomes,
        bootstrap_samples=bootstrap_samples,
        seed=seed,
    )
    stem = f"{state_name}_d7"
    labeled.to_parquet(output_dir / f"{stem}_labels.parquet", index=False)
    target_analysis.to_parquet(output_dir / f"{stem}_target_analysis.parquet", index=False)
    overlap.to_csv(output_dir / f"{stem}_failure_overlap.csv", index=False)
    outcome_strata.to_csv(output_dir / f"{stem}_outcome_strata.csv", index=False)
    (output_dir / f"{stem}_summary.json").write_text(
        json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8"
    )
    if not result["deterministic_label_check"] or not result["exporter_labeler_resolution_match"]:
        raise RuntimeError(f"{state_name} failed normalized D7 accounting")
    return result


def build_validity_gate(summary: pd.DataFrame) -> dict[str, Any]:
    overall = summary[summary["target_stratum"] == "overall"].set_index("state")
    common = summary[summary["target_stratum"] == "common"].set_index("state")
    new = summary[summary["target_stratum"] == "new"].set_index("state")
    stale_state = "stale_old_model_old_mapping"
    mapping_state = "mapping_only_old_model_new_mapping"
    mapping_only_ndcg = float(overall.loc[mapping_state, "path_NDCG@20"])
    stale_common_ndcg = float(common.loc[stale_state, "path_NDCG@20"])
    mapping_only_common_ndcg = float(common.loc[mapping_state, "path_NDCG@20"])
    adapted_states = sorted(name for name in overall.index if name.startswith("adapted_model_new_mapping_seed"))
    adapted_ndcgs = [float(overall.loc[name, "path_NDCG@20"]) for name in adapted_states]
    adapted_common_ndcgs = [float(common.loc[name, "path_NDCG@20"]) for name in adapted_states]
    adapted_new_recalls = [
        float(new.loc[name, "item_Recall@20"]) if name in new.index else math.nan for name in adapted_states
    ]
    disruption = max(0.0, stale_common_ndcg - mapping_only_common_ndcg)
    common_recovery_threshold = stale_common_ndcg - (1.0 - COMMON_RECOVERY_FRACTION) * disruption
    gate = {
        "mapping_only_path_ndcg20": mapping_only_ndcg,
        "adapted_path_ndcg20_by_seed": adapted_ndcgs,
        "adapted_mean_path_ndcg20": float(np.mean(adapted_ndcgs)),
        "adapted_all_seeds_above_mapping_only": all(value > mapping_only_ndcg for value in adapted_ndcgs),
        "stale_common_path_ndcg20": stale_common_ndcg,
        "mapping_only_common_path_ndcg20": mapping_only_common_ndcg,
        "adapted_common_path_ndcg20_by_seed": adapted_common_ndcgs,
        "adapted_new_item_recall20_by_seed": adapted_new_recalls,
        "mapping_swap_disruption_observed": mapping_only_common_ndcg < stale_common_ndcg,
        "common_recovery_fraction_required": COMMON_RECOVERY_FRACTION,
        "common_recovery_threshold_path_ndcg20": common_recovery_threshold,
        "adapted_all_seeds_recover_common_vs_mapping_only": all(
            value > mapping_only_common_ndcg for value in adapted_common_ndcgs
        ),
        "adapted_all_seeds_meet_a_relative_common_recovery": all(
            value >= common_recovery_threshold for value in adapted_common_ndcgs
        ),
        "adapted_all_seeds_reach_new_items": bool(
            adapted_new_recalls and all(math.isfinite(value) and value > 0.0 for value in adapted_new_recalls)
        ),
    }
    positive_handoff = bool(
        gate["adapted_all_seeds_above_mapping_only"]
        and gate["adapted_all_seeds_recover_common_vs_mapping_only"]
        and gate["adapted_all_seeds_meet_a_relative_common_recovery"]
        and gate["adapted_all_seeds_reach_new_items"]
    )
    gate["claim_status"] = "POSITIVE_REPAIR_HANDOFF" if positive_handoff else "BOUNDARY_ONLY"
    return gate


def build_stage_contract(
    *,
    stage: str,
    target_rows: int,
    full_test_rows: int,
    beam_width: int,
    seeds: list[int],
    max_train_rows: int,
    max_validation_rows: int,
    max_epochs: int,
    patience: int,
    reviewed_manifest_sha256: str,
) -> dict[str, bool]:
    manifest_bound = len(reviewed_manifest_sha256) == 64 and all(
        character in "0123456789abcdef" for character in reviewed_manifest_sha256
    )
    return {
        "preflight": stage == "preflight",
        "canary": (
            stage == "canary"
            and manifest_bound
            and target_rows == 100
            and beam_width == 20
            and seeds == [2025]
            and max_train_rows == 1024
            and max_validation_rows == 512
            and max_epochs == 2
            and patience == 1
        ),
        "primary": (
            stage == "primary"
            and manifest_bound
            and target_rows == full_test_rows
            and beam_width >= 20
            and seeds == list(PRIMARY_SEEDS)
            and max_train_rows == 0
            and max_validation_rows == 0
            and max_epochs >= 200
            and patience >= 15
        ),
    }


def load_official_datasets(
    *,
    dact_root: Path,
    code_path: Path,
    train_path: Path,
    validation_path: Path,
    max_history_items: int,
) -> tuple[Any, Any, Any]:
    from tools.run_v1_gate21_tiger_d7_trace import load_official_module

    module = load_official_module(dact_root)
    train = module.GenRecDataset(str(train_path), str(code_path), "train", max_history_items)
    validation = module.GenRecDataset(str(validation_path), str(code_path), "evaluation", max_history_items)
    return module, train, validation


def finetune_state(
    *,
    dact_root: Path,
    checkpoint: Path,
    code_path: Path,
    train_path: Path,
    validation_path: Path,
    seed: int,
    device: str,
    batch_size: int,
    max_history_items: int,
    learning_rate: float,
    max_epochs: int,
    patience: int,
    checkpoint_path: Path,
    max_train_rows: int,
    max_validation_rows: int,
) -> tuple[Any, pd.DataFrame, dict[str, Any]]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    set_seed(seed)
    module, train_dataset, validation_dataset = load_official_datasets(
        dact_root=dact_root,
        code_path=code_path,
        train_path=train_path,
        validation_path=validation_path,
        max_history_items=max_history_items,
    )
    if max_train_rows > 0:
        train_dataset = torch.utils.data.Subset(train_dataset, range(min(max_train_rows, len(train_dataset))))
    if max_validation_rows > 0:
        validation_dataset = torch.utils.data.Subset(
            validation_dataset, range(min(max_validation_rows, len(validation_dataset)))
        )
    collate = lambda batch: module.GenRecDataLoader.collate_fn(None, batch)  # noqa: E731
    generator = torch.Generator()
    generator.manual_seed(seed)
    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        collate_fn=collate,
        generator=generator,
    )
    validation_loader = torch.utils.data.DataLoader(
        validation_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        collate_fn=collate,
    )
    model = load_model(dact_root, checkpoint, device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    history = []
    best_loss = math.inf
    best_epoch = 0
    stale_epochs = 0
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, max_epochs + 1):
        model.train()
        train_total = 0.0
        for batch in train_loader:
            optimizer.zero_grad(set_to_none=True)
            loss, _ = model(
                input_ids=batch["history"].to(device),
                attention_mask=batch["attention_mask"].to(device),
                labels=batch["target"].to(device),
            )
            loss.backward()
            optimizer.step()
            train_total += float(loss.detach().cpu())
        model.eval()
        validation_total = 0.0
        with torch.no_grad():
            for batch in validation_loader:
                loss, _ = model(
                    input_ids=batch["history"].to(device),
                    attention_mask=batch["attention_mask"].to(device),
                    labels=batch["target"].to(device),
                )
                validation_total += float(loss.detach().cpu())
        train_loss = train_total / max(1, len(train_loader))
        validation_loss = validation_total / max(1, len(validation_loader))
        improved = validation_loss < best_loss - 1e-8
        history.append(
            {
                "seed": seed,
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
                "best": improved,
            }
        )
        if improved:
            best_loss = validation_loss
            best_epoch = epoch
            stale_epochs = 0
            torch.save(model.state_dict(), checkpoint_path)
        else:
            stale_epochs += 1
            if stale_epochs >= patience:
                break
    if best_epoch == 0 or not checkpoint_path.exists():
        raise RuntimeError(f"G22 seed {seed} did not produce a valid checkpoint")
    model.load_state_dict(torch.load(checkpoint_path, map_location=device), strict=True)
    model.eval()
    return model, pd.DataFrame(history), {
        "seed": seed,
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "epochs_run": len(history),
        "train_rows": len(train_dataset),
        "validation_rows": len(validation_dataset),
        "checkpoint_sha256": sha256(checkpoint_path),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    paths = {
        "released_checkpoint": args.checkpoint.resolve(),
        "old_codes": args.old_codes.resolve(),
        "new_codes": args.new_codes.resolve(),
        "train": args.train.resolve(),
        "validation": args.validation.resolve(),
        "test": args.test.resolve(),
        "mapping_audit_result": args.mapping_audit_result.resolve(),
    }
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(path)
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    expected_inputs = validate_expected_inputs(
        expected_path=args.expected_inputs.resolve(), dact_root=args.dact_root.resolve(), paths=paths
    )
    old_map, old_reverse = load_mapping(paths["old_codes"])
    new_map, new_reverse = load_mapping(paths["new_codes"])
    common_items = set(old_map) & set(new_map)
    new_items = set(new_map) - set(old_map)
    examples = load_period_examples(paths["test"], max_targets=args.max_targets)
    if not examples:
        raise RuntimeError("G22 target universe is empty")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    old_trie, old_constraint = build_trie(args.dact_root.resolve(), old_map)
    new_trie, new_constraint = build_trie(args.dact_root.resolve(), new_map)
    del old_trie, new_trie
    released_model = load_model(args.dact_root.resolve(), paths["released_checkpoint"], args.device)
    state_specs = [
        ("stale_old_model_old_mapping", released_model, old_map, old_reverse, old_constraint),
        ("mapping_only_old_model_new_mapping", released_model, new_map, new_reverse, new_constraint),
    ]
    summaries = []
    d7_accounting: dict[str, dict[str, Any]] = {}
    target_universe = None
    for state_name, model, mapping, reverse, constraint in state_specs:
        outcomes, beams = evaluate_state(
            model=model,
            state_name=state_name,
            examples=examples,
            item_to_code=mapping,
            reverse=reverse,
            constraint_fn=constraint,
            new_item_ids=new_items,
            beam_width=args.beam_width,
            batch_size=args.eval_batch_size,
            max_history_items=args.max_history_items,
            device=args.device,
        )
        universe = outcomes[["released_row_index", "user_id", "target_item_id"]].to_dict("records")
        if target_universe is None:
            target_universe = universe
        elif universe != target_universe:
            raise RuntimeError("G22 states used different target universes")
        outcomes.to_parquet(output_dir / f"{state_name}_outcomes.parquet", index=False)
        beams.to_parquet(output_dir / f"{state_name}_beams.parquet", index=False)
        d7_accounting[state_name] = write_d7_accounting(
            state_name=state_name,
            item_to_code=mapping,
            outcomes=outcomes,
            beams=beams,
            output_dir=output_dir,
            bootstrap_samples=args.bootstrap_samples,
            seed=args.seeds[0] + len(d7_accounting) * 97,
        )
        summaries.append(summarize_outcomes(outcomes))

    seed_records = []
    for seed in args.seeds:
        checkpoint_path = output_dir / "checkpoints" / f"adapted_seed{seed}.pth"
        adapted_model, history, record = finetune_state(
            dact_root=args.dact_root.resolve(),
            checkpoint=paths["released_checkpoint"],
            code_path=paths["new_codes"],
            train_path=paths["train"],
            validation_path=paths["validation"],
            seed=seed,
            device=args.device,
            batch_size=args.train_batch_size,
            max_history_items=args.max_history_items,
            learning_rate=args.learning_rate,
            max_epochs=args.max_epochs,
            patience=args.patience,
            checkpoint_path=checkpoint_path,
            max_train_rows=args.max_train_rows,
            max_validation_rows=args.max_validation_rows,
        )
        state_name = f"adapted_model_new_mapping_seed{seed}"
        outcomes, beams = evaluate_state(
            model=adapted_model,
            state_name=state_name,
            examples=examples,
            item_to_code=new_map,
            reverse=new_reverse,
            constraint_fn=new_constraint,
            new_item_ids=new_items,
            beam_width=args.beam_width,
            batch_size=args.eval_batch_size,
            max_history_items=args.max_history_items,
            device=args.device,
        )
        universe = outcomes[["released_row_index", "user_id", "target_item_id"]].to_dict("records")
        if universe != target_universe:
            raise RuntimeError(f"G22 adapted seed {seed} used a different target universe")
        history.to_csv(output_dir / f"adapted_seed{seed}_training_history.csv", index=False)
        outcomes.to_parquet(output_dir / f"{state_name}_outcomes.parquet", index=False)
        beams.to_parquet(output_dir / f"{state_name}_beams.parquet", index=False)
        d7_accounting[state_name] = write_d7_accounting(
            state_name=state_name,
            item_to_code=new_map,
            outcomes=outcomes,
            beams=beams,
            output_dir=output_dir,
            bootstrap_samples=args.bootstrap_samples,
            seed=seed,
        )
        summaries.append(summarize_outcomes(outcomes))
        seed_records.append(record)

    summary = pd.concat(summaries, ignore_index=True)
    summary.to_csv(output_dir / "g22_three_state_metrics.csv", index=False)
    validity_gate = build_validity_gate(summary)
    full_test_rows = len(pd.read_parquet(paths["test"], columns=["target"]))
    stage_contract = build_stage_contract(
        stage=args.stage,
        target_rows=len(examples),
        full_test_rows=full_test_rows,
        beam_width=args.beam_width,
        seeds=args.seeds,
        max_train_rows=args.max_train_rows,
        max_validation_rows=args.max_validation_rows,
        max_epochs=args.max_epochs,
        patience=args.patience,
        reviewed_manifest_sha256=args.reviewed_manifest_sha256,
    )
    status_pass = bool(stage_contract[args.stage])
    result = {
        "schema": "sidinspector.g22.three_state_handoff.v1",
        "contract": CONTRACT_ID,
        "status": f"{'PASS' if status_pass else 'FAIL'}_G22_{args.stage.upper()}_DOWNSTREAM_AUDIT",
        "stage": args.stage,
        "source": {
            **{name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()},
            "expected_inputs": expected_inputs,
        },
        "protocol": {
            "target_period": "0.7",
            "target_rows": len(examples),
            "target_universe_sha256": hashlib.sha256(
                json.dumps(target_universe, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "common_catalog_items": len(common_items),
            "new_catalog_items": len(new_items),
            "beam_width": args.beam_width,
            "seeds": args.seeds,
            "learning_rate": args.learning_rate,
            "max_epochs": args.max_epochs,
            "patience": args.patience,
            "max_train_rows": args.max_train_rows,
            "max_validation_rows": args.max_validation_rows,
            "unknown_history_policy": "all-zero PAD code",
            "unmapped_target_policy": "forced miss",
            "test_used_for_training_or_selection": False,
            "full_test_rows": full_test_rows,
            "stage_contract_pass": stage_contract[args.stage],
            "reviewed_manifest_sha256": args.reviewed_manifest_sha256 or None,
        },
        "adaptation": seed_records,
        "d7_accounting": d7_accounting,
        "validity_gate": validity_gate,
        "elapsed_sec": time.perf_counter() - started,
        "evidence_boundary": (
            "One released temporal repair case under the DACT TIGER architecture; "
            "no universal repair-effectiveness or causal diagnostic claim."
        ),
    }
    (output_dir / "g22_downstream_result.json").write_text(
        json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8"
    )
    if not status_pass:
        raise RuntimeError(f"{CONTRACT_ID} failed the {args.stage} execution contract")
    print(json.dumps(json_safe(result), indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("preflight", "canary", "primary"), default="preflight")
    parser.add_argument("--dact-root", type=Path, default=DEFAULT_DACT_ROOT)
    parser.add_argument(
        "--checkpoint", type=Path, default=DEFAULT_DACT_ROOT / "TIGER-backbone/ckpt/tiger_Tools_0.6_cf.pth"
    )
    parser.add_argument("--old-codes", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/Tools_0.6_cf.npy")
    parser.add_argument("--new-codes", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/Tools_0.7_dact.npy")
    parser.add_argument("--train", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/train_0.7.parquet")
    parser.add_argument("--validation", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/valid_0.7.parquet")
    parser.add_argument("--test", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/test_0.7.parquet")
    parser.add_argument(
        "--mapping-audit-result",
        type=Path,
        default=(
            PROJECT_ROOT
            / "experiments/v1_evidence_chain/gate22_diagnose_repair_reaudit/mapping_audit/g22_mapping_reaudit_result.json"
        ),
    )
    parser.add_argument("--expected-inputs", type=Path, default=DEFAULT_EXPECTED_INPUTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--beam-width", type=int, default=4)
    parser.add_argument("--train-batch-size", type=int, default=256)
    parser.add_argument("--eval-batch-size", type=int, default=64)
    parser.add_argument("--max-history-items", type=int, default=20)
    parser.add_argument("--max-targets", type=int, default=4)
    parser.add_argument("--seeds", type=int, nargs="+", default=[2025])
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--max-epochs", type=int, default=1)
    parser.add_argument("--patience", type=int, default=1)
    parser.add_argument("--max-train-rows", type=int, default=512)
    parser.add_argument("--max-validation-rows", type=int, default=256)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--reviewed-manifest-sha256", default="")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
