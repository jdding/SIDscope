#!/usr/bin/env python3
"""Export D7-compatible beams from the released DACT TIGER/T5 checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any, Iterable

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
except ImportError as exc:  # pragma: no cover
    transformers = None  # type: ignore[assignment]
    TRANSFORMERS_IMPORT_ERROR: Exception | None = exc
else:
    TRANSFORMERS_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from sidinspector.d7_trace import deterministic_label_check, label_traces, summarize_trace_labels  # noqa: E402
from sidinspector.trace_analysis import analyze_traces  # noqa: E402


CONTRACT_ID = "G21_D7_RELEASED_TIGER_TRACE"
DEFAULT_DACT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/upstreams/DACT"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate21_tiger_d7_robustness"
DEFAULT_EXPECTED_INPUTS = DEFAULT_OUTPUT_ROOT / "G21_EXPECTED_INPUT_SHA256.json"
MODEL_CONFIG = {
    "num_layers": 4,
    "num_decoder_layers": 4,
    "d_model": 128,
    "d_ff": 1024,
    "num_heads": 6,
    "d_kv": 64,
    "dropout_rate": 0.1,
    "vocab_size": 1505,
    "pad_token_id": 0,
    "eos_token_id": 0,
    "feed_forward_proj": "relu",
}


def stage_contract_pass(args: argparse.Namespace, target_rows: int) -> bool:
    manifest_bound = len(args.reviewed_manifest_sha256) == 64 and all(
        character in "0123456789abcdef" for character in args.reviewed_manifest_sha256
    )
    if args.stage == "preflight":
        return target_rows >= 4
    if args.stage == "canary":
        return bool(
            manifest_bound
            and args.device == "cuda"
            and target_rows == 100
            and args.max_targets == 100
            and args.beam_width == 20
            and args.batch_size == 16
            and args.modes == ["constrained"]
        )
    return bool(
        manifest_bound
        and args.device == "cuda"
        and target_rows == 500
        and args.max_targets == 500
        and args.beam_width == 50
        and args.batch_size == 16
        and args.modes == ["constrained", "unconstrained"]
        and args.bootstrap_samples >= 2000
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def stable_key(*parts: Any) -> int:
    text = "::".join(str(part) for part in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def json_sha256(value: Any) -> str:
    payload = json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def offset_code(code: Iterable[int], codebook_size: int = 256) -> tuple[int, ...]:
    values = tuple(int(value) for value in code)
    if not values:
        raise ValueError("SID code is empty")
    if any(value < 0 or value >= codebook_size for value in values):
        raise ValueError(f"SID token outside [0, {codebook_size}): {values}")
    return tuple(value + level * codebook_size + 1 for level, value in enumerate(values))


def load_mapping(code_path: Path) -> tuple[dict[int, tuple[int, ...]], dict[tuple[int, ...], tuple[int, ...]]]:
    raw = np.load(code_path, allow_pickle=True)
    item_to_code = {index + 1: offset_code(code) for index, code in enumerate(raw)}
    reverse: dict[tuple[int, ...], list[int]] = {}
    for item, code in item_to_code.items():
        reverse.setdefault(code, []).append(item)
    return item_to_code, {code: tuple(sorted(items)) for code, items in reverse.items()}


def sid_frame(item_to_code: dict[int, tuple[int, ...]]) -> pd.DataFrame:
    depth = len(next(iter(item_to_code.values())))
    rows = []
    for item, code in sorted(item_to_code.items()):
        rows.append({"item_id": item, **{f"sid_level_{level}": code[level] for level in range(depth)}})
    return pd.DataFrame(rows)


def source_revision(root: Path) -> str:
    marker = root / "SIDSCOPE_PINNED_REVISION.txt"
    if marker.exists():
        value = marker.read_text(encoding="utf-8").strip()
        if not value:
            raise RuntimeError(f"empty pinned-revision marker: {marker}")
        return value
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def load_official_module(dact_root: Path) -> Any:
    backbone = dact_root / "TIGER-backbone"
    main_path = backbone / "main_trie.py"
    if not main_path.exists():
        raise FileNotFoundError(main_path)
    inserted_openpyxl_stub = False
    if "openpyxl" not in sys.modules and importlib.util.find_spec("openpyxl") is None:
        stub = types.ModuleType("openpyxl")

        def unavailable_openpyxl(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("openpyxl is unavailable and is outside the SIDScope TIGER execution route")

        stub.Workbook = unavailable_openpyxl  # type: ignore[attr-defined]
        stub.load_workbook = unavailable_openpyxl  # type: ignore[attr-defined]
        sys.modules["openpyxl"] = stub
        inserted_openpyxl_stub = True
    sys.path.insert(0, str(backbone))
    try:
        spec = importlib.util.spec_from_file_location("sidscope_dact_tiger_main", main_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import released TIGER source: {main_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if inserted_openpyxl_stub:
            sys.modules.pop("openpyxl", None)
    module._sidscope_openpyxl_stubbed = inserted_openpyxl_stub
    return module


def load_model(dact_root: Path, checkpoint: Path, device: str) -> Any:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    module = load_official_module(dact_root)
    model = module.TIGER(dict(MODEL_CONFIG))
    state = torch.load(checkpoint, map_location="cpu")
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    return model


def build_trie(dact_root: Path, item_to_code: dict[int, tuple[int, ...]]) -> tuple[Any, Any]:
    module = load_official_module(dact_root)
    sequences = [[0, *code, 0] for code in item_to_code.values()]
    trie = module.Trie(sequences)
    return trie, module.prefix_allowed_tokens_fn(trie)


def prepare_examples(
    test_path: Path,
    item_to_code: dict[int, tuple[int, ...]],
    *,
    max_targets: int,
    max_history_items: int,
) -> list[dict[str, Any]]:
    frame = pd.read_parquet(test_path)
    required = {"user", "history", "target"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"released test split missing columns: {missing}")
    rows = []
    for row_index, row in enumerate(frame.itertuples(index=False)):
        target = int(row.target)
        raw_history = [int(item) for item in list(row.history)]
        missing_history = sorted({item for item in raw_history if item not in item_to_code})
        if target not in item_to_code:
            raise ValueError(f"released target {target} has no mapping row")
        if missing_history:
            raise ValueError(f"released history contains unmapped items: {missing_history[:5]}")
        history = raw_history
        if not history:
            raise ValueError(f"released test row {row_index} has empty history")
        history = history[-max_history_items:]
        rows.append(
            {
                "released_row_index": row_index,
                "user_id": str(row.user),
                "target_item_id": target,
                "history_items": history,
            }
        )
    rows.sort(key=lambda row: (stable_key(row["user_id"], row["target_item_id"]), row["user_id"]))
    return rows[:max_targets] if max_targets > 0 else rows


def encode_history(
    examples: list[dict[str, Any]], item_to_code: dict[int, tuple[int, ...]], max_history_items: int
) -> tuple[Any, Any]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    depth = len(next(iter(item_to_code.values())))
    encoded = []
    masks = []
    for example in examples:
        codes = [item_to_code[item] for item in example["history_items"][-max_history_items:]]
        padding = [(0,) * depth] * (max_history_items - len(codes))
        flat = [token for code in [*padding, *codes] for token in code]
        encoded.append(flat)
        masks.append([int(token != 0) for token in flat])
    return torch.tensor(encoded, dtype=torch.long), torch.tensor(masks, dtype=torch.long)


def assert_official_preprocessing_parity(
    *,
    dact_root: Path,
    test_path: Path,
    code_path: Path,
    examples: list[dict[str, Any]],
    item_to_code: dict[int, tuple[int, ...]],
    max_history_items: int,
    checks: int = 8,
) -> dict[str, Any]:
    """Compare G21 tensors with the released GenRecDataset contract."""

    module = load_official_module(dact_root)
    official = module.GenRecDataset(str(test_path), str(code_path), "evaluation", max_history_items)
    selected = examples[: min(checks, len(examples))]
    input_ids, masks = encode_history(selected, item_to_code, max_history_items)
    for position, example in enumerate(selected):
        released = official[int(example["released_row_index"])]
        released_history = torch.tensor(
            [token for code in released["history"] for token in code], dtype=torch.long
        )
        released_target = torch.tensor(released["target"], dtype=torch.long)
        released_mask = (released_history != 0).long()
        expected_target = torch.tensor(item_to_code[int(example["target_item_id"])], dtype=torch.long)
        if not torch.equal(input_ids[position], released_history):
            raise RuntimeError(f"official preprocessing history parity failed at selected row {position}")
        if not torch.equal(masks[position], released_mask):
            raise RuntimeError(f"official preprocessing mask parity failed at selected row {position}")
        if not torch.equal(expected_target, released_target):
            raise RuntimeError(f"official preprocessing target parity failed at selected row {position}")
    return {"status": "PASS", "checked_rows": len(selected), "official_dataset_rows": len(official)}


def validate_expected_inputs(
    *,
    expected_path: Path,
    dact_root: Path,
    checkpoint: Path,
    code_path: Path,
    test_path: Path,
) -> dict[str, Any]:
    if not expected_path.exists():
        raise FileNotFoundError(f"G21 expected-input manifest is missing: {expected_path}")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    observed_assets = {
        "source_revision": source_revision(dact_root),
        "checkpoint_sha256": sha256(checkpoint),
        "mapping_sha256": sha256(code_path),
        "test_split_sha256": sha256(test_path),
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
        raise RuntimeError(f"G21 expected-input mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return {
        "status": "PASS",
        "manifest": str(expected_path),
        **observed_assets,
        **runtime,
        "runtime_profile": matched_profile.get("name"),
    }


def ranking_metrics(outcomes: pd.DataFrame, cutoffs: tuple[int, ...] = (5, 10, 20)) -> dict[str, float]:
    result: dict[str, float] = {}
    ranks = pd.to_numeric(outcomes["target_path_rank"], errors="coerce")
    for cutoff in cutoffs:
        hit = ranks.notna() & (ranks <= cutoff)
        result[f"Recall@{cutoff}"] = float(hit.mean())
        gains = np.where(hit, 1.0 / np.log2(ranks.fillna(cutoff + 1).to_numpy() + 1.0), 0.0)
        result[f"NDCG@{cutoff}"] = float(np.mean(gains))
    return result


def validate_mode_accounting(
    *,
    traces: pd.DataFrame,
    outcomes: pd.DataFrame,
    examples: list[dict[str, Any]],
    beam_width: int,
    mode: str,
    depth: int,
) -> dict[str, Any]:
    expected_targets = {(str(row["user_id"]), int(row["target_item_id"])) for row in examples}
    observed_targets = set(zip(outcomes["user_id"].astype(str), outcomes["target_item_id"].astype(int)))
    if observed_targets != expected_targets:
        raise RuntimeError(f"{mode} target universe differs from the preregistered examples")
    if outcomes["trace_id"].duplicated().any():
        raise RuntimeError(f"{mode} outcomes contain duplicate trace IDs")
    if set(traces["trace_id"].astype(str)) != set(outcomes["trace_id"].astype(str)):
        raise RuntimeError(f"{mode} trace and outcome IDs differ")
    if traces["score"].isna().any() or not np.isfinite(traces["score"].astype(float)).all():
        raise RuntimeError(f"{mode} contains non-finite sequence scores")
    for trace_id, group in traces.groupby("trace_id", sort=False):
        ordered = group.sort_values("rank", kind="stable")
        if ordered["rank"].astype(int).tolist() != list(range(1, beam_width + 1)):
            raise RuntimeError(f"{mode} incomplete ranks for {trace_id}")
        scores = ordered["score"].astype(float).to_numpy()
        if np.any(scores[:-1] < scores[1:] - 1e-12):
            raise RuntimeError(f"{mode} sequence scores are not non-increasing for {trace_id}")
        if ordered["generated_length"].astype(int).lt(0).any() or ordered["generated_length"].astype(int).gt(depth).any():
            raise RuntimeError(f"{mode} generated length outside [0, {depth}] for {trace_id}")
        for row in ordered.itertuples(index=False):
            steps = json.loads(str(row.step_logprob))
            if len(steps) != int(row.generated_length):
                raise RuntimeError(f"{mode} transition-score length mismatch for {trace_id} rank {row.rank}")
    if mode == "constrained" and traces["terminated_early"].astype(bool).any():
        raise RuntimeError("constrained generation terminated before the full SID depth")
    return {
        "status": "PASS",
        "target_universe_size": len(expected_targets),
        "trace_rows": len(traces),
        "early_termination_rows": int(traces["terminated_early"].astype(bool).sum()),
        "score_order": "explicit_descending_sequence_score",
    }


def decode_mode(
    *,
    model: Any,
    examples: list[dict[str, Any]],
    item_to_code: dict[int, tuple[int, ...]],
    reverse: dict[tuple[int, ...], tuple[int, ...]],
    constraint_fn: Any,
    mode: str,
    beam_width: int,
    batch_size: int,
    max_history_items: int,
    device: str,
    provenance: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    trace_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    depth = len(next(iter(item_to_code.values())))
    for start in range(0, len(examples), batch_size):
        batch = examples[start : start + batch_size]
        input_ids, attention_mask = encode_history(batch, item_to_code, max_history_items)
        input_ids = input_ids.to(device)
        attention_mask = attention_mask.to(device)
        kwargs: dict[str, Any] = {
            "num_beams": beam_width,
            "return_dict_in_generate": True,
            "output_scores": True,
        }
        if mode == "constrained":
            kwargs["prefix_allowed_tokens_fn"] = constraint_fn
        with torch.no_grad():
            generated = model.generate(input_ids=input_ids, attention_mask=attention_mask, **kwargs)
            transition = model.model.compute_transition_scores(
                generated.sequences,
                generated.scores,
                generated.beam_indices,
                normalize_logits=True,
            )
        sequences = generated.sequences.detach().cpu().reshape(len(batch), beam_width, -1)
        transition = transition.detach().cpu().reshape(len(batch), beam_width, -1)
        sequence_scores = generated.sequences_scores.detach().cpu().reshape(len(batch), beam_width)
        for batch_index, example in enumerate(batch):
            target = int(example["target_item_id"])
            target_code = item_to_code[target]
            decoded: list[tuple[float, tuple[int, ...], list[float], bool]] = []
            for rank_index in range(beam_width):
                sequence = sequences[batch_index, rank_index].tolist()
                candidate = [int(token) for token in sequence[1 : 1 + depth]]
                eos_position = next((idx for idx, token in enumerate(candidate) if token == 0), None)
                generated_length = eos_position if eos_position is not None else len(candidate)
                code = tuple(candidate[:generated_length])
                steps = [
                    float(value)
                    for value in transition[batch_index, rank_index, :generated_length].tolist()
                ]
                decoded.append(
                    (
                        float(sequence_scores[batch_index, rank_index]),
                        code,
                        steps,
                        generated_length < depth,
                    )
                )
            decoded.sort(key=lambda value: (-value[0], value[1]))
            decoded_codes = [value[1] for value in decoded]
            target_rank = next((rank + 1 for rank, code in enumerate(decoded_codes) if code == target_code), None)
            target_items = reverse[target_code]
            unique_hit = bool(target_rank is not None and len(target_items) == 1)
            trace_id = f"DACT::Tools::0.6_cf::{mode}::user{example['user_id']}::target{target}"
            outcome_rows.append(
                {
                    "trace_id": trace_id,
                    "user_id": example["user_id"],
                    "target_item_id": target,
                    "target_path_rank": target_rank,
                    "target_path_survived": target_rank is not None,
                    "target_uniquely_addressable": len(target_items) == 1,
                    "target_item_uniquely_hit": unique_hit,
                    "target_missed": target_rank is None,
                    "target_ambiguous": bool(target_rank is not None and len(target_items) > 1),
                    "decoding_mode": mode,
                }
            )
            for rank_index, (sequence_score, code, steps, terminated_early) in enumerate(decoded):
                resolved = reverse.get(code, ())
                trace_rows.append(
                    {
                        "artifact_id": "dact_tools_0.6_cf",
                        "mapping_revision": provenance["mapping_sha256"],
                        "dataset": "Tools",
                        "label": "DACT TIGER Tools 0.6 CF",
                        "method": "DACT released TIGER backbone",
                        "trace_id": trace_id,
                        "user_id": example["user_id"],
                        "target_item_id": target,
                        "rank": rank_index + 1,
                        "sid_path": "-".join(str(token) for token in code),
                        "generated_code": json.dumps(code),
                        "score": sequence_score,
                        "step_logprob": json.dumps(steps),
                        "prefix_entropy": None,
                        "generated_length": len(code),
                        "terminated_early": terminated_early,
                        "resolved_item_ids_exporter": ";".join(str(item) for item in resolved),
                        "resolved_item_count_exporter": len(resolved),
                        "target_item_in_resolved_set": target in resolved,
                        "target_path_survived": target_rank is not None,
                        "target_item_uniquely_hit": unique_hit,
                        "target_missed": target_rank is None,
                        "beam_width": beam_width,
                        "decoding_mode": f"{mode}_beam",
                        "trace_source": "g21_dact_released_tiger_checkpoint",
                        "model": "released_t5_tiger_4layer_4.65m",
                        "checkpoint_sha256": provenance["checkpoint_sha256"],
                        "configuration_sha256": provenance["configuration_sha256"],
                        "score_semantics": "huggingface_beam_sequence_score",
                        "history_count": len(example["history_items"]),
                        "split_protocol": "released_test_0.6_history_target_rows",
                    }
                )
    return pd.DataFrame(trace_rows), pd.DataFrame(outcome_rows)


def run(args: argparse.Namespace) -> dict[str, Any]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    dact_root = args.dact_root.resolve()
    checkpoint = args.checkpoint.resolve()
    code_path = args.code_path.resolve()
    test_path = args.test_path.resolve()
    for path in (checkpoint, code_path, test_path):
        if not path.exists():
            raise FileNotFoundError(path)
    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    item_to_code, reverse = load_mapping(code_path)
    sid = sid_frame(item_to_code)
    examples = prepare_examples(
        test_path, item_to_code, max_targets=args.max_targets, max_history_items=args.max_history_items
    )
    if len(examples) < args.max_targets:
        raise RuntimeError(f"requested {args.max_targets} targets but only {len(examples)} are eligible")
    expected_inputs = validate_expected_inputs(
        expected_path=args.expected_inputs.resolve(),
        dact_root=dact_root,
        checkpoint=checkpoint,
        code_path=code_path,
        test_path=test_path,
    )
    parity = assert_official_preprocessing_parity(
        dact_root=dact_root,
        test_path=test_path,
        code_path=code_path,
        examples=examples,
        item_to_code=item_to_code,
        max_history_items=args.max_history_items,
    )
    provenance = {
        "source_revision": expected_inputs["source_revision"],
        "checkpoint_sha256": expected_inputs["checkpoint_sha256"],
        "mapping_sha256": expected_inputs["mapping_sha256"],
        "test_split_sha256": expected_inputs["test_split_sha256"],
        "configuration_sha256": json_sha256(
            {
                "model": MODEL_CONFIG,
                "beam_width": args.beam_width,
                "batch_size": args.batch_size,
                "max_targets": args.max_targets,
                "max_history_items": args.max_history_items,
                "modes": args.modes,
            }
        ),
    }
    started = time.perf_counter()
    model = load_model(dact_root, checkpoint, device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    trie, constraint_fn = build_trie(dact_root, item_to_code)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    mode_results: dict[str, Any] = {}
    for mode in args.modes:
        traces, outcomes = decode_mode(
            model=model,
            examples=examples,
            item_to_code=item_to_code,
            reverse=reverse,
            constraint_fn=constraint_fn,
            mode=mode,
            beam_width=args.beam_width,
            batch_size=args.batch_size,
            max_history_items=args.max_history_items,
            device=device,
            provenance=provenance,
        )
        labels, target_analysis, overlap, strata, analysis = analyze_traces(
            sid=sid,
            traces=traces,
            outcomes=outcomes,
            bootstrap_samples=args.bootstrap_samples,
            seed=args.seed + len(mode_results) * 101,
        )
        deterministic = deterministic_label_check(sid=sid, traces=traces, active_item_ids={str(i) for i in item_to_code})
        summary = summarize_trace_labels(labels)
        accounting_contract = validate_mode_accounting(
            traces=traces,
            outcomes=outcomes,
            examples=examples,
            beam_width=args.beam_width,
            mode=mode,
            depth=len(next(iter(item_to_code.values()))),
        )
        expected_rows = len(examples) * args.beam_width
        constrained_valid = mode != "constrained" or int((labels["primary_failure"] == "invalid_path").sum()) == 0
        accounting_pass = bool(
            len(traces) == expected_rows
            and len(labels) == expected_rows
            and outcomes["trace_id"].nunique() == len(examples)
            and deterministic
            and analysis["exporter_labeler_resolution_match"]
            and constrained_valid
            and accounting_contract["status"] == "PASS"
        )
        prefix = output_dir / f"g21_{mode}"
        traces.to_csv(prefix.with_name(prefix.name + "_beam_traces.csv"), index=False)
        labels.to_csv(prefix.with_name(prefix.name + "_labels.csv"), index=False)
        outcomes.to_csv(prefix.with_name(prefix.name + "_target_outcomes.csv"), index=False)
        summary.to_csv(prefix.with_name(prefix.name + "_label_summary.csv"), index=False)
        target_analysis.to_csv(prefix.with_name(prefix.name + "_target_analysis.csv"), index=False)
        overlap.to_csv(prefix.with_name(prefix.name + "_failure_overlap.csv"), index=False)
        strata.to_csv(prefix.with_name(prefix.name + "_outcome_strata.csv"), index=False)
        mode_results[mode] = {
            "target_traces": int(len(examples)),
            "beam_rows": int(len(traces)),
            "accounting_pass": accounting_pass,
            "ranking": ranking_metrics(outcomes),
            "primary_failure_counts": {
                str(key): int(value) for key, value in labels["primary_failure"].value_counts().sort_index().items()
            },
            "target_path_survival_rate": float(outcomes["target_path_survived"].mean()),
            "unique_item_hit_rate": float(outcomes["target_item_uniquely_hit"].mean()),
            "analysis": analysis,
            "accounting_contract": accounting_contract,
        }
    target_universes = {
        mode: sorted(
            zip(
                pd.read_csv(output_dir / f"g21_{mode}_target_outcomes.csv")["user_id"].astype(str),
                pd.read_csv(output_dir / f"g21_{mode}_target_outcomes.csv")["target_item_id"].astype(int),
            )
        )
        for mode in args.modes
    }
    if len({json_sha256(value) for value in target_universes.values()}) != 1:
        raise RuntimeError("constrained and unconstrained modes used different target universes")
    execution_contract_pass = stage_contract_pass(args, len(examples))
    status_pass = bool(
        execution_contract_pass
        and all(result["accounting_pass"] for result in mode_results.values())
        and parameter_count == 4_652_288
        and len(item_to_code) == 9_610
    )
    status = f"{'PASS' if status_pass else 'FAIL'}_G21_{args.stage.upper()}"
    result = {
        "schema": "sidinspector.g21.released_tiger_trace.v1",
        "contract": CONTRACT_ID,
        "status": status,
        "stage": args.stage,
        "source": {
            "project": "DACT",
            "model": "released TIGER/T5 backbone",
            "dataset": "Tools",
            "snapshot": "0.6_cf",
            "parameter_count": parameter_count,
            "catalog_items": len(item_to_code),
            "unique_full_codes": len(reverse),
            **provenance,
            "expected_inputs": expected_inputs,
            "official_preprocessing_parity": parity,
        },
        "configuration": {
            "device": device,
            "beam_width": args.beam_width,
            "batch_size": args.batch_size,
            "max_targets": args.max_targets,
            "max_history_items": args.max_history_items,
            "modes": args.modes,
            "seed": args.seed,
            "reviewed_manifest_sha256": args.reviewed_manifest_sha256 or None,
            "stage_contract_pass": execution_contract_pass,
        },
        "mode_results": mode_results,
        "elapsed_sec": time.perf_counter() - started,
        "evidence_boundary": (
            "Released-checkpoint D7 trace portability and decoding-constraint accounting only; "
            "no failure-mechanism, universal-prevalence, or D1-D5 predictivity claim."
        ),
    }
    (output_dir / "g21_result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    if not status_pass:
        raise RuntimeError(f"{CONTRACT_ID} failed: {status}")
    print(json.dumps(json_safe(result), indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("preflight", "canary", "primary"), default="preflight")
    parser.add_argument("--dact-root", type=Path, default=DEFAULT_DACT_ROOT)
    parser.add_argument(
        "--checkpoint", type=Path, default=DEFAULT_DACT_ROOT / "TIGER-backbone/ckpt/tiger_Tools_0.6_cf.pth"
    )
    parser.add_argument("--code-path", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/Tools_0.6_cf.npy")
    parser.add_argument("--test-path", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/test_0.6.parquet")
    parser.add_argument("--expected-inputs", type=Path, default=DEFAULT_EXPECTED_INPUTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / "local_preflight")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--beam-width", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-targets", type=int, default=4)
    parser.add_argument("--max-history-items", type=int, default=20)
    parser.add_argument("--modes", nargs="+", choices=("constrained", "unconstrained"), default=["constrained"])
    parser.add_argument("--bootstrap-samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--reviewed-manifest-sha256", default="")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
