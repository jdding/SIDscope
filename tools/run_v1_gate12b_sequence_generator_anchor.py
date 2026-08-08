#!/usr/bin/env python3
"""Run SIDScope G12b sequence-generator utility-anchor checks.

G12b is the stronger rescue run after the original G12 boundary result.  It
keeps the same SIDScope artifact/split surface, but replaces the mean-pooled
independent-token scorer with a small sequence generator: a GRU history encoder
and teacher-forced autoregressive SID decoder.  Evaluation still ranks a
non-prefix hard-negative candidate pool by learned target-code likelihood, but
the run is only claim-eligible if the learned generator itself beats simple
popularity/random baselines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
except ImportError as exc:  # pragma: no cover - exercised by environment precheck.
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    DataLoader = object  # type: ignore[assignment,misc]
    Dataset = object  # type: ignore[assignment,misc]
    TORCH_IMPORT_ERROR: Exception | None = exc
else:
    TORCH_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from sidinspector.downstream_probe import _d3_weighted, _dcg  # noqa: E402
from tools.run_v1_gate2_cross_dataset_utility import (  # noqa: E402
    _filter_row_data,
    _split_train_eval,
)
from tools.run_v1_gate10_independent_utility import (  # noqa: E402
    _artifact_cols,
    rank_corr,
    stable_mod,
    stable_seed,
)


DEFAULT_G2_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate2_cross_dataset_utility"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate12b_sequence_generator_anchor"
DEFAULT_RUNS_DIR = PROJECT_ROOT / "experiments/v1_evidence_chain/runs"
CONTRACT_ID = "G12B_SEQUENCE_GENERATOR_ANCHOR"
DEFAULT_ARTIFACT_LABELS = (
    "resid_gaoq_musical_pilot,"
    "resid_gaoq_video_pilot,"
    "grid_faithful_p5_beauty,"
    "resid_hf_category_musical,"
    "resid_hf_category_video"
)
MANIFEST_PATH_COLUMNS = ("sid_assignments", "item_metadata", "interactions")


def _level_cols(frame: pd.DataFrame) -> list[str]:
    return sorted(
        [col for col in frame.columns if col.startswith("sid_level_") and not frame[col].isna().all()],
        key=lambda col: int(col.rsplit("_", 1)[1]),
    )


def _parse_csv(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _parse_path_rewrites(rewrites: list[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for rewrite in rewrites:
        if "=" not in rewrite:
            raise ValueError(f"Invalid --path-rewrite value {rewrite!r}; expected OLD=NEW")
        old, new = rewrite.split("=", 1)
        if not old:
            raise ValueError(f"Invalid --path-rewrite value {rewrite!r}; OLD prefix is empty")
        parsed.append((old, new))
    return parsed


def _load_manifest(g2_root: Path, manifest_path: Path | None, path_rewrites: list[str]) -> pd.DataFrame:
    path = manifest_path if manifest_path is not None else g2_root / "g2_manifest.csv"
    manifest = pd.read_csv(path)
    rewrites = _parse_path_rewrites(path_rewrites)
    if not rewrites:
        return manifest
    manifest = manifest.copy()
    for col in MANIFEST_PATH_COLUMNS:
        if col not in manifest.columns:
            continue
        values = []
        for raw in manifest[col].astype(str):
            updated = raw
            for old, new in rewrites:
                if updated.startswith(old):
                    updated = new + updated[len(old) :]
                    break
            values.append(updated)
        manifest[col] = values
    return manifest


def validate_manifest_inputs(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _load_manifest(args.g2_root, args.manifest_path, args.path_rewrite)
    selected = _select_manifest(manifest, _parse_csv(args.artifact_labels), args.max_artifacts)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for _, row in selected.iterrows():
        for col in MANIFEST_PATH_COLUMNS:
            path = Path(str(row[col]))
            exists = path.exists()
            rows.append({"label": row["label"], "column": col, "path": str(path), "exists": exists})
            if not exists:
                missing.append(str(path))
    result = {
        "schema": "sidinspector.v1.gate12b.input_preflight.v1",
        "status": "pass" if not missing else "fail",
        "selected_rows": int(len(selected)),
        "checked_paths": int(len(rows)),
        "missing_paths": missing,
        "rows": rows,
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "g12b_input_preflight.json").write_text(
        json.dumps(_json_safe(result), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def _format_float(value: Any) -> str:
    if value is None or pd.isna(value):
        return "nan"
    return f"{float(value):.4f}"


def _hash_rows(*parts: Any) -> int:
    digest = hashlib.sha256("::".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


@dataclass(frozen=True)
class SIDEncoding:
    level_cols: list[str]
    item_to_index: dict[int, int]
    index_to_item: list[int]
    item_code: dict[int, tuple[int, ...]]
    item_sid_path: dict[int, tuple[str, ...]]
    item_code_matrix: np.ndarray
    level_vocab_sizes: list[int]
    unique_full_codes: int
    duplicate_sid_rate: float


def build_sid_encoding(sid: pd.DataFrame) -> SIDEncoding:
    level_cols = _level_cols(sid)
    if not level_cols:
        raise ValueError("SID frame has no usable sid_level_* columns")
    sid = sid[["item_id", *level_cols]].dropna(subset=["item_id", *level_cols]).copy()
    sid["item_id"] = sid["item_id"].astype(int)
    sid = sid.drop_duplicates("item_id", keep="first").copy()
    sid = sid.sort_values("item_id", kind="stable").reset_index(drop=True)

    token_maps: list[dict[str, int]] = []
    for col in level_cols:
        values = sorted({str(value) for value in sid[col].tolist()})
        token_maps.append({value: idx for idx, value in enumerate(values)})

    item_to_index: dict[int, int] = {}
    index_to_item = [0]
    item_code: dict[int, tuple[int, ...]] = {}
    item_sid_path: dict[int, tuple[str, ...]] = {}
    matrix_rows: list[tuple[int, ...]] = []
    for row in sid.itertuples(index=False):
        item = int(getattr(row, "item_id"))
        original_path = tuple(str(getattr(row, col)) for col in level_cols)
        code = tuple(token_maps[level][str(getattr(row, col))] for level, col in enumerate(level_cols))
        item_to_index[item] = len(index_to_item)
        index_to_item.append(item)
        item_code[item] = code
        item_sid_path[item] = original_path
        matrix_rows.append(code)

    code_counter = Counter(matrix_rows)
    duplicate_items = sum(count for count in code_counter.values() if count > 1)
    duplicate_sid_rate = float(duplicate_items / len(matrix_rows)) if matrix_rows else 0.0
    return SIDEncoding(
        level_cols=level_cols,
        item_to_index=item_to_index,
        index_to_item=index_to_item,
        item_code=item_code,
        item_sid_path=item_sid_path,
        item_code_matrix=np.asarray(matrix_rows, dtype=np.int64),
        level_vocab_sizes=[len(mapping) for mapping in token_maps],
        unique_full_codes=len(code_counter),
        duplicate_sid_rate=duplicate_sid_rate,
    )


class HistoryCodeDataset(Dataset):  # type: ignore[misc]
    def __init__(self, examples: list[tuple[list[int], tuple[int, ...]]]) -> None:
        self.examples = examples

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> tuple[list[int], tuple[int, ...]]:
        return self.examples[index]


def collate_history_code(batch: list[tuple[list[int], tuple[int, ...]]]) -> tuple[Any, Any]:
    if torch is None:
        raise RuntimeError("PyTorch is required for G12b")
    max_len = max(len(history) for history, _ in batch)
    histories = torch.zeros((len(batch), max_len), dtype=torch.long)
    targets = torch.zeros((len(batch), len(batch[0][1])), dtype=torch.long)
    for row_idx, (history, code) in enumerate(batch):
        histories[row_idx, : len(history)] = torch.as_tensor(history, dtype=torch.long)
        targets[row_idx] = torch.as_tensor(code, dtype=torch.long)
    return histories, targets


class SequenceSIDGenerator(nn.Module):  # type: ignore[misc]
    def __init__(
        self,
        *,
        num_items: int,
        level_vocab_sizes: list[int],
        embedding_dim: int,
        hidden_dim: int,
        decoder_dim: int,
        dropout: float,
    ) -> None:
        if nn is None:
            raise RuntimeError("PyTorch is required for G12b")
        super().__init__()
        self.item_embedding = nn.Embedding(num_items + 1, embedding_dim, padding_idx=0)
        self.history_gru = nn.GRU(embedding_dim, hidden_dim, batch_first=True)
        self.initial_decoder = nn.Linear(hidden_dim, decoder_dim)
        self.bos = nn.Parameter(torch.zeros(decoder_dim))
        self.token_embeddings = nn.ModuleList(
            nn.Embedding(vocab_size + 1, decoder_dim, padding_idx=0) for vocab_size in level_vocab_sizes
        )
        self.decoder_cell = nn.GRUCell(decoder_dim + hidden_dim, decoder_dim)
        self.dropout = nn.Dropout(dropout)
        self.heads = nn.ModuleList(nn.Linear(decoder_dim, vocab_size) for vocab_size in level_vocab_sizes)

    def encode(self, histories: Any) -> Any:
        lengths = histories.ne(0).sum(dim=1).clamp_min(1)
        embedded = self.item_embedding(histories)
        outputs, _ = self.history_gru(embedded)
        row_index = torch.arange(histories.shape[0], device=histories.device)
        return outputs[row_index, lengths - 1]

    def forward(self, histories: Any, target_codes: Any) -> list[Any]:
        history_state = self.encode(histories)
        decoder_state = torch.tanh(self.initial_decoder(history_state))
        logits: list[Any] = []
        for level, head in enumerate(self.heads):
            if level == 0:
                previous = self.bos.unsqueeze(0).expand(histories.shape[0], -1)
            else:
                previous = self.token_embeddings[level - 1](target_codes[:, level - 1] + 1)
            decoder_input = torch.cat([self.dropout(previous), history_state], dim=1)
            decoder_state = self.decoder_cell(decoder_input, decoder_state)
            logits.append(head(self.dropout(decoder_state)))
        return logits

    def score_codes(self, histories: Any, candidate_codes: Any) -> Any:
        if histories.shape[0] == 1 and candidate_codes.shape[0] > 1:
            histories = histories.expand(candidate_codes.shape[0], -1)
        logits = self.forward(histories, candidate_codes)
        scores = torch.zeros(candidate_codes.shape[0], device=candidate_codes.device)
        for level, level_logits in enumerate(logits):
            log_probs = torch.log_softmax(level_logits, dim=1)
            scores = scores + log_probs.gather(1, candidate_codes[:, level : level + 1]).squeeze(1)
        return scores


def make_training_examples(
    *,
    train: pd.DataFrame,
    users: list[Any],
    encoding: SIDEncoding,
    max_history_items: int,
    targets_per_user: int,
    max_train_samples: int,
) -> tuple[list[tuple[list[int], tuple[int, ...]]], int]:
    train_subset = _sort_interactions_for_sequence(train[train["user_id"].isin(users)])
    train_by_user = {
        user: [int(item) for item in group["item_id"].tolist() if int(item) in encoding.item_to_index]
        for user, group in train_subset.groupby("user_id", sort=False)
    }
    examples: list[tuple[int, list[int], tuple[int, ...]]] = []
    for user in sorted(train_by_user, key=lambda value: stable_mod(value, 2**31 - 1)):
        items = train_by_user[user]
        if len(items) < 2:
            continue
        target_positions = list(range(1, len(items)))
        target_positions = target_positions[-targets_per_user:]
        for pos in target_positions:
            target = items[pos]
            history_items = items[:pos]
            if len(history_items) > max_history_items:
                history_items = history_items[-max_history_items:]
            history = [encoding.item_to_index[item] for item in history_items if item in encoding.item_to_index]
            if not history or target not in encoding.item_code:
                continue
            examples.append((_hash_rows(user, pos, target), history, encoding.item_code[target]))
    examples = sorted(examples, key=lambda row: row[0])
    if max_train_samples > 0:
        examples = examples[:max_train_samples]
    return [(history, code) for _, history, code in examples], len(train_by_user)


def train_model(
    *,
    encoding: SIDEncoding,
    examples: list[tuple[list[int], tuple[int, ...]]],
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
) -> tuple[SequenceSIDGenerator, dict[str, Any]]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    torch.manual_seed(seed)
    np.random.seed(seed % (2**32))
    resolved_device = device
    if device == "auto":
        resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
    if resolved_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested CUDA device, but torch.cuda.is_available() is false")

    model = SequenceSIDGenerator(
        num_items=len(encoding.index_to_item) - 1,
        level_vocab_sizes=encoding.level_vocab_sizes,
        embedding_dim=embedding_dim,
        hidden_dim=hidden_dim,
        decoder_dim=decoder_dim,
        dropout=dropout,
    ).to(resolved_device)
    dataset = HistoryCodeDataset(examples)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collate_history_code,
        num_workers=num_workers,
        generator=torch.Generator().manual_seed(seed),
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    criterion = nn.CrossEntropyLoss()
    losses: list[float] = []
    samples = 0
    start = time.perf_counter()
    for _ in range(epochs):
        model.train()
        for histories, target_codes in loader:
            histories = histories.to(resolved_device)
            target_codes = target_codes.to(resolved_device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(histories, target_codes)
            loss = sum(criterion(level_logits, target_codes[:, level]) for level, level_logits in enumerate(logits))
            if not bool(torch.isfinite(loss).detach().cpu().item()):
                raise RuntimeError("G12B_SEQUENCE_GENERATOR_ANCHOR FAIL: non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            samples += int(histories.shape[0])
    elapsed = time.perf_counter() - start
    return model, {
        "device": resolved_device,
        "epochs": int(epochs),
        "train_samples_seen": int(samples),
        "train_batches": int(len(losses)),
        "loss_first": float(losses[0]) if losses else math.nan,
        "loss_last": float(losses[-1]) if losses else math.nan,
        "train_sec": float(elapsed),
        "samples_per_sec": float(samples / elapsed) if elapsed > 0 else math.nan,
    }


def _candidate_pool(
    *,
    sorted_catalog: list[int],
    history: set[int],
    targets: set[int],
    candidate_pool_size: int,
) -> list[int]:
    base_pool = [item for item in sorted_catalog if item not in history][:candidate_pool_size]
    return sorted(
        set(base_pool).union(targets).difference(history),
        key=lambda item: (0 if item in targets else 1, item),
    )


def _sequence_order_source(frame: pd.DataFrame) -> str:
    if "position" in frame.columns and not frame["position"].isna().all():
        return "position"
    if "timestamp" in frame.columns and not frame["timestamp"].isna().all():
        return "timestamp"
    return ""


def _with_sequence_order(frame: pd.DataFrame) -> pd.DataFrame:
    subset = frame.copy()
    subset["_g12b_row_order"] = np.arange(len(subset), dtype=np.int64)
    order_source = _sequence_order_source(subset)
    if order_source:
        order_values = pd.to_numeric(subset[order_source], errors="coerce")
        subset["_g12b_seq_order"] = order_values.fillna(subset["_g12b_row_order"]).astype(float)
    else:
        subset["_g12b_seq_order"] = subset["_g12b_row_order"].astype(float)
    subset["_g12b_order_source"] = order_source or "stable_input_order"
    return subset


def _sort_interactions_for_sequence(frame: pd.DataFrame) -> pd.DataFrame:
    subset = _with_sequence_order(frame)
    if _sequence_order_source(frame):
        sort_cols = ["user_id", "_g12b_seq_order", "_g12b_row_order"]
    else:
        sort_cols = ["user_id", "_g12b_row_order"]
    return subset.sort_values(sort_cols, kind="stable").drop(
        columns=["_g12b_row_order", "_g12b_seq_order", "_g12b_order_source"],
        errors="ignore",
    )


def _ordered_items_by_user(frame: pd.DataFrame, encoding: SIDEncoding) -> dict[Any, list[int]]:
    subset = _sort_interactions_for_sequence(frame)
    return {
        user: [int(item) for item in group["item_id"].tolist() if int(item) in encoding.item_to_index]
        for user, group in subset.groupby("user_id", sort=False)
    }


def _ranking_metrics(ranked: list[int], targets: list[int], rec_k: int) -> dict[str, float]:
    top_pos = {item: pos + 1 for pos, item in enumerate(ranked[:rec_k])}
    hit_ranks = [top_pos[target] for target in targets if target in top_pos]
    ideal_hits = min(len(targets), rec_k)
    ideal_dcg = _dcg(list(range(1, ideal_hits + 1))) if ideal_hits else 0.0
    return {
        "recall_at_k": float(len(hit_ranks) / len(targets)) if targets else 0.0,
        "ndcg_at_k": float(_dcg(hit_ranks) / ideal_dcg) if ideal_dcg else 0.0,
        "mrr_at_k": float(1.0 / min(hit_ranks)) if hit_ranks else 0.0,
    }


def evaluate_model(
    *,
    model: SequenceSIDGenerator,
    encoding: SIDEncoding,
    eval_train: pd.DataFrame,
    eval_events: pd.DataFrame,
    diag_popularity: dict[int, int],
    rec_k: int,
    candidate_pool_size: int,
    max_history_items: int,
    max_eval_users: int,
    device: str,
    trace_rows: list[dict[str, Any]] | None = None,
    trace_top_k: int = 0,
    trace_context: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if torch is None:
        raise RuntimeError("PyTorch is required for G12b")
    model.eval()
    sorted_catalog = sorted(encoding.item_to_index, key=lambda item: (-diag_popularity.get(item, 0), item))
    train_ordered = _with_sequence_order(eval_train)
    eval_ordered = _with_sequence_order(eval_events)
    train_source = str(train_ordered["_g12b_order_source"].iloc[0]) if not train_ordered.empty else "stable_input_order"
    eval_source = str(eval_ordered["_g12b_order_source"].iloc[0]) if not eval_ordered.empty else "stable_input_order"
    comparable_temporal_order = train_source == eval_source and train_source != "stable_input_order"
    train_groups = {user: group.copy() for user, group in train_ordered.groupby("user_id", sort=False)}
    eval_groups = {user: group.copy() for user, group in eval_ordered.groupby("user_id", sort=False)}
    users = sorted(set(train_groups).intersection(eval_groups), key=lambda value: stable_mod(value, 2**31 - 1))
    if max_eval_users > 0:
        users = users[:max_eval_users]

    rows: list[dict[str, Any]] = []
    resolved_device = device
    with torch.no_grad():
        for user in users:
            user_train = train_groups[user].sort_values(["_g12b_seq_order", "_g12b_row_order"], kind="stable")
            user_eval = eval_groups[user].sort_values(["_g12b_seq_order", "_g12b_row_order"], kind="stable")
            for target_idx, (_, target_row) in enumerate(user_eval.iterrows()):
                target = int(target_row["item_id"])
                if target not in encoding.item_to_index:
                    continue
                if comparable_temporal_order:
                    target_order = float(target_row["_g12b_seq_order"])
                    history_frame = user_train[user_train["_g12b_seq_order"].astype(float) < target_order]
                else:
                    target_order = math.nan
                    history_frame = user_train
                history_items = [int(item) for item in history_frame["item_id"].tolist() if int(item) in encoding.item_to_index]
                future_history_excluded = int(len(user_train) - len(history_frame))
                if not history_items or target in set(history_items):
                    continue
                history_set = set(history_items)
                targets = [target]
                target_set = {target}
                candidates = _candidate_pool(
                    sorted_catalog=sorted_catalog,
                    history=history_set,
                    targets=target_set,
                    candidate_pool_size=candidate_pool_size,
                )
                if not candidates:
                    continue
                history_tail = history_items[-max_history_items:] if max_history_items > 0 else history_items
                history_indices = [encoding.item_to_index[item] for item in history_tail]
                history_tensor = torch.as_tensor([history_indices], dtype=torch.long, device=resolved_device)
                candidate_items = [item for item in candidates if item in encoding.item_code]
                candidate_codes = torch.as_tensor(
                    [encoding.item_code[item] for item in candidate_items],
                    dtype=torch.long,
                    device=resolved_device,
                )
                scores = model.score_codes(history_tensor, candidate_codes).detach().cpu().numpy()
                scored = list(zip(candidate_items, [float(score) for score in scores]))
                ranked_scored = sorted(
                    scored,
                    key=lambda pair: (-pair[1], -diag_popularity.get(pair[0], 0), pair[0]),
                )
                generator_ranked = [
                    item for item, _ in ranked_scored[:rec_k]
                ]
                popularity_ranked = sorted(
                    candidate_items,
                    key=lambda item: (-diag_popularity.get(item, 0), item),
                )[:rec_k]
                random_ranked = sorted(
                    candidate_items,
                    key=lambda item: stable_mod(f"g12b-random::{user}::{target_idx}::{item}", 2**31 - 1),
                )[:rec_k]
                if trace_rows is not None and trace_top_k > 0:
                    base_trace = dict(trace_context or {})
                    trace_id = "::".join(
                        [
                            str(base_trace.get("dataset", "dataset")),
                            str(base_trace.get("label", "artifact")),
                            f"fold{base_trace.get('fold', 'na')}",
                            f"user{user}",
                            f"target{target}",
                            f"targetidx{target_idx}",
                        ]
                    )
                    for rank, (candidate_item, score) in enumerate(ranked_scored[:trace_top_k], start=1):
                        sid_path = encoding.item_sid_path.get(candidate_item)
                        trace_rows.append(
                            {
                                **base_trace,
                                "trace_id": trace_id,
                                "user_id": str(user),
                                "target_item_id": int(target),
                                "target_order": target_order,
                                "target_index": int(target_idx),
                                "rank": int(rank),
                                "item_id": int(candidate_item),
                                "expected_item_id": int(candidate_item),
                                "sid_path": "-".join(str(value) for value in sid_path) if sid_path is not None else "",
                                "score": float(score),
                                "step_logprob": float(score),
                                "hit": bool(candidate_item in target_set),
                                "target_hit_at_k": bool(candidate_item in target_set and rank <= rec_k),
                                "rec_k": int(rec_k),
                                "candidate_count": int(len(candidate_items)),
                                "candidate_pool_size": int(candidate_pool_size),
                                "beam_width": int(trace_top_k),
                                "decoding_mode": "candidate_pool_scoring",
                                "trace_source": "g12b_sequence_generator_scored_candidates",
                                "history_count": int(len(history_items)),
                                "future_history_events_excluded": int(future_history_excluded),
                                "temporal_history_mode": (
                                    "per_target_history"
                                    if comparable_temporal_order
                                    else "full_train_history_no_explicit_order"
                                ),
                            }
                        )
                generator_metrics = _ranking_metrics(generator_ranked, targets, rec_k)
                popularity_metrics = _ranking_metrics(popularity_ranked, targets, rec_k)
                random_metrics = _ranking_metrics(random_ranked, targets, rec_k)
                rows.append(
                    {
                        "user_id": user,
                        "target_item": target,
                        "target_order": target_order,
                        "temporal_history_mode": "per_target_history" if comparable_temporal_order else "full_train_history_no_explicit_order",
                        "future_history_events_excluded": future_history_excluded,
                        "history_count": len(history_items),
                        "targets": len(targets),
                        "candidate_count": len(candidate_items),
                        "candidate_hits": len(target_set.intersection(candidates)),
                        "candidate_recall": float(len(target_set.intersection(candidates)) / len(targets)),
                        "recall_at_k": generator_metrics["recall_at_k"],
                        "ndcg_at_k": generator_metrics["ndcg_at_k"],
                        "mrr_at_k": generator_metrics["mrr_at_k"],
                        "popularity_recall_at_k": popularity_metrics["recall_at_k"],
                        "popularity_ndcg_at_k": popularity_metrics["ndcg_at_k"],
                        "popularity_mrr_at_k": popularity_metrics["mrr_at_k"],
                        "random_recall_at_k": random_metrics["recall_at_k"],
                        "random_ndcg_at_k": random_metrics["ndcg_at_k"],
                        "random_mrr_at_k": random_metrics["mrr_at_k"],
                        "recall_lift_vs_popularity": generator_metrics["recall_at_k"]
                        - popularity_metrics["recall_at_k"],
                        "ndcg_lift_vs_popularity": generator_metrics["ndcg_at_k"]
                        - popularity_metrics["ndcg_at_k"],
                        "mrr_lift_vs_popularity": generator_metrics["mrr_at_k"]
                        - popularity_metrics["mrr_at_k"],
                        "recall_lift_vs_random": generator_metrics["recall_at_k"]
                        - random_metrics["recall_at_k"],
                        "ndcg_lift_vs_random": generator_metrics["ndcg_at_k"]
                        - random_metrics["ndcg_at_k"],
                        "mrr_lift_vs_random": generator_metrics["mrr_at_k"]
                        - random_metrics["mrr_at_k"],
                        "ndcg_beats_popularity": float(
                            generator_metrics["ndcg_at_k"] > popularity_metrics["ndcg_at_k"]
                        ),
                        "recall_beats_popularity": float(
                            generator_metrics["recall_at_k"] > popularity_metrics["recall_at_k"]
                        ),
                        "ndcg_beats_random": float(generator_metrics["ndcg_at_k"] > random_metrics["ndcg_at_k"]),
                        "recall_beats_random": float(
                            generator_metrics["recall_at_k"] > random_metrics["recall_at_k"]
                        ),
                    }
                )
    user_metrics = pd.DataFrame(rows)
    if user_metrics.empty:
        return user_metrics, {
            "users_with_eval_targets": 0,
            "targets_evaluated": 0,
            "candidate_recall": math.nan,
            "recall_at_k": math.nan,
            "ndcg_at_k": math.nan,
            "mrr_at_k": math.nan,
        }
    weights = user_metrics["targets"].astype(float).to_numpy()
    metric_cols = [
        "candidate_recall",
        "recall_at_k",
        "ndcg_at_k",
        "mrr_at_k",
        "popularity_recall_at_k",
        "popularity_ndcg_at_k",
        "popularity_mrr_at_k",
        "random_recall_at_k",
        "random_ndcg_at_k",
        "random_mrr_at_k",
        "recall_lift_vs_popularity",
        "ndcg_lift_vs_popularity",
        "mrr_lift_vs_popularity",
        "recall_lift_vs_random",
        "ndcg_lift_vs_random",
        "mrr_lift_vs_random",
        "ndcg_beats_popularity",
        "recall_beats_popularity",
        "ndcg_beats_random",
        "recall_beats_random",
    ]
    summary = {
        "users_with_eval_targets": int(user_metrics["user_id"].nunique()),
        "targets_evaluated": int(user_metrics["targets"].sum()),
        "mean_candidate_count": float(user_metrics["candidate_count"].mean()),
        "temporal_history_mode": ";".join(sorted(user_metrics["temporal_history_mode"].dropna().astype(str).unique())),
        "future_history_events_excluded": int(user_metrics["future_history_events_excluded"].sum()),
        "mean_history_count": float(user_metrics["history_count"].mean()),
    }
    for col in metric_cols:
        summary[col] = float(np.average(user_metrics[col], weights=weights))
    return user_metrics, summary


def run_artifact_fold(
    *,
    row: pd.Series,
    manifest_row: int,
    sid: pd.DataFrame,
    interactions: pd.DataFrame,
    fold: int,
    folds: int,
    analysis_depth: int,
    d3_top_k: int,
    max_pair_events: int,
    max_user_items: int,
    max_users: int,
    max_train_samples: int,
    train_targets_per_user: int,
    max_history_items: int,
    max_eval_users: int,
    candidate_pool_size: int,
    rec_k: int,
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
    trace_rows: list[dict[str, Any]] | None = None,
    trace_top_k: int = 0,
) -> tuple[dict[str, Any], pd.DataFrame]:
    setup_start = time.perf_counter()
    sid = sid.copy()
    sid["item_id"] = sid["item_id"].astype(int)
    encoding = build_sid_encoding(sid)
    item_ids = set(encoding.item_to_index)
    train, eval_events = _split_train_eval(interactions)
    train = train[train["item_id"].astype(int).isin(item_ids)].copy()
    eval_events = eval_events[eval_events["item_id"].astype(int).isin(item_ids)].copy()
    train_sizes = train[["user_id", "item_id"]].drop_duplicates().groupby("user_id").size()
    eligible = train_sizes[(train_sizes >= 2) & (train_sizes <= max_user_items)].index
    eligible_users = sorted(
        set(eligible).intersection(set(eval_events["user_id"])),
        key=lambda user: stable_mod(user, 2**31 - 1),
    )
    if max_users > 0:
        eligible_users = eligible_users[:max_users]
    diag_users = [user for user in eligible_users if stable_mod(user, folds) != fold]
    eval_users = [user for user in eligible_users if stable_mod(user, folds) == fold]
    if folds == 1:
        diag_users = eligible_users
        eval_users = eligible_users
    if not diag_users or not eval_users:
        raise ValueError(f"Fold {fold} has insufficient users for {row['label']}")
    diag_train = train[train["user_id"].isin(diag_users)].copy()
    eval_train = train[train["user_id"].isin(eval_users)].copy()
    eval_holdout = eval_events[eval_events["user_id"].isin(eval_users)].copy()
    depth = min(analysis_depth, len(encoding.level_cols))
    d3_weighted, d3_users, d3_pair_events = _d3_weighted(
        sid,
        diag_train,
        depth=depth,
        top_k=d3_top_k,
        max_pair_events=max_pair_events,
        max_user_items=max_user_items,
    )
    examples, train_user_count = make_training_examples(
        train=diag_train,
        users=diag_users,
        encoding=encoding,
        max_history_items=max_history_items,
        targets_per_user=train_targets_per_user,
        max_train_samples=max_train_samples,
    )
    if not examples:
        raise ValueError(f"No training examples for {row['label']} fold {fold}")
    setup_sec = time.perf_counter() - setup_start

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
        seed=seed + manifest_row * 101 + fold,
        device=device,
        num_workers=num_workers,
    )
    eval_start = time.perf_counter()
    user_metrics, eval_summary = evaluate_model(
        model=model,
        encoding=encoding,
        eval_train=eval_train,
        eval_events=eval_holdout,
        diag_popularity=diag_train.groupby("item_id").size().astype(int).to_dict(),
        rec_k=rec_k,
        candidate_pool_size=candidate_pool_size,
        max_history_items=max_history_items,
        max_eval_users=max_eval_users,
        device=train_info["device"],
        trace_rows=trace_rows,
        trace_top_k=trace_top_k,
        trace_context={
            "dataset": row["dataset"],
            "label": row["label"],
            "method": row["method"],
            "manifest_row": int(manifest_row),
            "row_family": row.get("row_family", ""),
            "gate2_role": row.get("gate2_role", ""),
            "fold": int(fold),
            "folds": int(folds),
            "prefix_depth": int(depth),
            "model": "gru_history_autoregressive_sid_sequence_generator",
            "candidate_protocol": "popularity_sampled_non_prefix",
            "ranker": "teacher_forced_sid_code_log_likelihood",
            "level_count": int(len(encoding.level_cols)),
            "catalog_items": int(len(encoding.item_to_index)),
            "unique_full_codes": int(encoding.unique_full_codes),
            "duplicate_sid_rate": float(encoding.duplicate_sid_rate),
            "d3_weighted_disjoint": float(d3_weighted),
        },
    )
    eval_sec = time.perf_counter() - eval_start
    summary = {
        "dataset": row["dataset"],
        "label": row["label"],
        "method": row["method"],
        "manifest_row": int(manifest_row),
        "row_family": row.get("row_family", ""),
        "gate2_role": row.get("gate2_role", ""),
        "fold": int(fold),
        "folds": int(folds),
        "prefix_depth": int(depth),
        "model": "gru_history_autoregressive_sid_sequence_generator",
        "candidate_protocol": "popularity_sampled_non_prefix",
        "ranker": "teacher_forced_sid_code_log_likelihood",
        "rec_k": int(rec_k),
        "candidate_pool_size": int(candidate_pool_size),
        "level_count": int(len(encoding.level_cols)),
        "level_vocab_sizes": ";".join(str(value) for value in encoding.level_vocab_sizes),
        "catalog_items": int(len(encoding.item_to_index)),
        "unique_full_codes": int(encoding.unique_full_codes),
        "duplicate_sid_rate": float(encoding.duplicate_sid_rate),
        "eligible_users": int(len(eligible_users)),
        "diagnostic_users": int(len(diag_users)),
        "generator_train_users": int(train_user_count),
        "generator_train_examples": int(len(examples)),
        "d3_weighted_disjoint": float(d3_weighted),
        "d3_users": int(d3_users),
        "d3_pair_events": int(d3_pair_events),
        "setup_sec": float(setup_sec),
        "eval_sec": float(eval_sec),
        **train_info,
        **eval_summary,
    }
    for col, value in summary.items():
        user_metrics[col] = value
    return summary, user_metrics


def _bootstrap_corr(frame: pd.DataFrame, signal: str, outcome: str, unit_cols: list[str], samples: int, seed: int) -> dict[str, Any]:
    cols = [*unit_cols, signal, outcome]
    data = frame[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    collapsed = data.groupby(unit_cols, dropna=False)[[signal, outcome]].mean().reset_index()
    point = rank_corr(collapsed[signal], collapsed[outcome])
    if len(collapsed) < 4 or pd.isna(point) or samples <= 0:
        return {
            "signal": signal,
            "outcome": outcome,
            "unit": "+".join(unit_cols),
            "effective_n": int(len(collapsed)),
            "spearman": point,
            "ci_low": math.nan,
            "ci_high": math.nan,
            "bootstrap_samples": 0,
        }
    rng = np.random.default_rng(seed)
    values: list[float] = []
    indices = np.arange(len(collapsed))
    for _ in range(samples):
        sample = collapsed.iloc[rng.choice(indices, size=len(indices), replace=True)]
        value = rank_corr(sample[signal], sample[outcome])
        if not pd.isna(value):
            values.append(float(value))
    return {
        "signal": signal,
        "outcome": outcome,
        "unit": "+".join(unit_cols),
        "effective_n": int(len(collapsed)),
        "spearman": point,
        "ci_low": float(np.quantile(values, 0.025)) if values else math.nan,
        "ci_high": float(np.quantile(values, 0.975)) if values else math.nan,
        "bootstrap_samples": int(len(values)),
    }


def analyze(summary: pd.DataFrame, *, bootstrap_samples: int, seed: int) -> pd.DataFrame:
    rows = []
    for outcome in [
        "recall_at_k",
        "ndcg_at_k",
        "mrr_at_k",
        "recall_lift_vs_popularity",
        "ndcg_lift_vs_popularity",
        "mrr_lift_vs_popularity",
        "recall_lift_vs_random",
        "ndcg_lift_vs_random",
        "mrr_lift_vs_random",
    ]:
        for unit_cols in [
            [*_artifact_cols(), "fold"],
            _artifact_cols(),
        ]:
            rows.append(
                _bootstrap_corr(
                    summary,
                    signal="d3_weighted_disjoint",
                    outcome=outcome,
                    unit_cols=unit_cols,
                    samples=bootstrap_samples,
                    seed=seed + len(rows) * 43,
                )
            )
    return pd.DataFrame(rows)


def enforce_g12b_contract(summary: pd.DataFrame, user_metrics: pd.DataFrame) -> None:
    """Hard-fail the executable G12b contract before writing a misleading run."""

    if summary.empty:
        raise RuntimeError("G12B_SEQUENCE_GENERATOR_ANCHOR FAIL: no artifact-fold summary rows were produced")
    if user_metrics.empty:
        raise RuntimeError("G12B_SEQUENCE_GENERATOR_ANCHOR FAIL: no user-level evaluation rows were produced")
    for col in ("users_with_eval_targets", "targets_evaluated"):
        if col not in summary.columns:
            raise RuntimeError(f"G12B_SEQUENCE_GENERATOR_ANCHOR FAIL: missing {col}")
        if (summary[col].astype(float) <= 0).any():
            raise RuntimeError(f"G12B_SEQUENCE_GENERATOR_ANCHOR FAIL: every artifact-fold needs positive {col}")
    for col in (
        "recall_at_k",
        "ndcg_at_k",
        "mrr_at_k",
        "popularity_recall_at_k",
        "popularity_ndcg_at_k",
        "random_ndcg_at_k",
        "recall_lift_vs_popularity",
        "ndcg_lift_vs_popularity",
        "recall_lift_vs_random",
        "ndcg_lift_vs_random",
        "loss_first",
        "loss_last",
    ):
        if col not in summary.columns:
            raise RuntimeError(f"G12B_SEQUENCE_GENERATOR_ANCHOR FAIL: missing {col}")
        if not summary[col].replace([np.inf, -np.inf], np.nan).notna().all():
            raise RuntimeError(f"G12B_SEQUENCE_GENERATOR_ANCHOR FAIL: non-finite {col}")


def _pick_assoc(association: pd.DataFrame, outcome: str, unit: str) -> dict[str, Any]:
    rows = association[(association["outcome"] == outcome) & (association["unit"] == unit)]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _write_report(result: dict[str, Any], output_root: Path) -> None:
    fold_unit = "dataset+label+method+manifest_row+fold"
    lines = [
        "# Gate 12b Sequence-Generator Anchor Result",
        "",
        f"- gate: `{result['gate']}`",
        f"- run_id: `{result['run_id']}`",
        f"- verdict: `{result['verdict']}`",
        f"- built_pass_for_75_target: `{result['built_pass_for_75_target']}`",
        f"- artifact_rows: `{result['artifact_rows']}`",
        f"- artifact_fold_rows: `{result['artifact_fold_rows']}`",
        f"- device: `{result['device']}`",
        f"- model_validity_pass: `{result['model_validity_pass']}`",
        f"- mean_ndcg_lift_vs_popularity: `{_format_float(result['mean_ndcg_lift_vs_popularity'])}`",
        "",
        "## Primary Artifact-Fold Readout",
        "",
        "| Outcome | Spearman | 95% CI | Effective n |",
        "| --- | ---: | ---: | ---: |",
    ]
    for outcome in ["recall_at_k", "ndcg_at_k", "mrr_at_k", "ndcg_lift_vs_popularity"]:
        row = result["primary_associations"].get(outcome, {})
        lines.append(
            f"| `{outcome}` | {_format_float(row.get('spearman'))} | "
            f"[{_format_float(row.get('ci_low'))}, {_format_float(row.get('ci_high'))}] | "
            f"{row.get('effective_n', 'nan')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            result["claim_update"],
            "",
            "## Scope",
        ]
    )
    lines.extend([f"- {item}" for item in result["limitations"]])
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- fold summary: `{result['artifacts']['fold_summary']}`",
            f"- associations: `{result['artifacts']['associations']}`",
            f"- user metrics: `{result['artifacts']['user_metrics']}`",
            "",
            f"Primary association unit: `{fold_unit}`.",
        ]
    )
    (output_root / "GATE12B_RESULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _select_manifest(manifest: pd.DataFrame, labels: list[str], max_artifacts: int) -> pd.DataFrame:
    if labels:
        selected = manifest[manifest["label"].astype(str).isin(labels)].copy()
    else:
        selected = manifest.copy()
    if selected.empty:
        raise ValueError("No manifest rows selected for G12b")
    if max_artifacts > 0:
        selected = selected.head(max_artifacts).copy()
    return selected


def _run_record_path(runs_dir: Path, run_id: str) -> Path:
    if "gate12b" in run_id.lower() or "sequence_generator" in run_id.lower():
        return runs_dir / f"{run_id}.json"
    return runs_dir / f"{run_id}_gate12b_sequence_generator_anchor.json"


def _dummy_frames() -> tuple[pd.Series, int, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(20260620)
    item_count = 200
    user_count = 100
    sid = pd.DataFrame(
        {
            "item_id": np.arange(1, item_count + 1, dtype=np.int64),
            "sid_level_0": np.arange(item_count) % 20,
            "sid_level_1": (np.arange(item_count) // 5) % 20,
            "sid_level_2": np.arange(item_count) % 7,
        }
    )
    rows = []
    for user in range(1, user_count + 1):
        preferred = int(rng.integers(0, 20))
        candidates = [item for item in range(1, item_count + 1) if item % 20 == preferred]
        sampled = rng.choice(candidates, size=10, replace=True)
        for pos, item in enumerate(sampled):
            rows.append({"user_id": user, "item_id": int(item), "position": pos})
    interactions = pd.DataFrame(rows)
    row = pd.Series(
        {
            "dataset": "dummy",
            "label": "dummy_tiny_sid",
            "method": "dummy_tiny_sid",
            "row_family": "dummy",
            "gate2_role": "dummy",
        }
    )
    return row, 0, sid, interactions


def close_gate12(args: argparse.Namespace) -> dict[str, Any]:
    if torch is None:
        raise RuntimeError(f"PyTorch import failed: {TORCH_IMPORT_ERROR}")
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    args.runs_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    summary_rows: list[dict[str, Any]] = []
    user_frames: list[pd.DataFrame] = []
    trace_rows: list[dict[str, Any]] = []
    if args.dummy:
        selected_rows = [(*_dummy_frames(), 0.0)]
    else:
        manifest = _load_manifest(args.g2_root, args.manifest_path, args.path_rewrite)
        selected = _select_manifest(manifest, _parse_csv(args.artifact_labels), args.max_artifacts)
        selected_rows = []
        for manifest_row, row in selected.iterrows():
            load_start = time.perf_counter()
            sid, _, interactions = _filter_row_data(row)
            selected_rows.append((row, int(manifest_row), sid, interactions, time.perf_counter() - load_start))

    for row, manifest_row, sid, interactions, load_sec in selected_rows:
        for fold in range(args.folds):
            fold_summary, fold_user_metrics = run_artifact_fold(
                row=row,
                manifest_row=manifest_row,
                sid=sid,
                interactions=interactions,
                fold=fold,
                folds=args.folds,
                analysis_depth=args.analysis_depth,
                d3_top_k=args.d3_top_k,
                max_pair_events=args.max_pair_events,
                max_user_items=args.max_user_items,
                max_users=args.max_users,
                max_train_samples=args.max_train_samples,
                train_targets_per_user=args.train_targets_per_user,
                max_history_items=args.max_history_items,
                max_eval_users=args.max_eval_users,
                candidate_pool_size=args.candidate_pool_size,
                rec_k=args.rec_k,
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
                trace_rows=trace_rows if args.export_traces else None,
                trace_top_k=args.trace_top_k if args.export_traces else 0,
            )
            fold_summary["load_sec"] = float(load_sec)
            summary_rows.append(fold_summary)
            user_frames.append(fold_user_metrics)

    summary = pd.DataFrame(summary_rows)
    user_metrics = pd.concat(user_frames, ignore_index=True) if user_frames else pd.DataFrame()
    enforce_g12b_contract(summary, user_metrics)
    association = analyze(summary, bootstrap_samples=args.bootstrap_samples, seed=args.seed)
    summary.to_csv(output_root / "g12b_sequence_generator_fold_summary.csv", index=False)
    user_metrics.to_csv(output_root / "g12b_sequence_generator_user_metrics.csv", index=False)
    association.to_csv(output_root / "g12b_sequence_generator_associations.csv", index=False)
    trace_path = output_root / "g12b_sequence_generator_traces.csv"
    trace_rows_written = 0
    if args.export_traces:
        trace_frame = pd.DataFrame(trace_rows)
        trace_frame.to_csv(trace_path, index=False)
        trace_rows_written = int(len(trace_frame))

    fold_unit = "dataset+label+method+manifest_row+fold"
    primary_assoc = {
        outcome: _pick_assoc(association, outcome, fold_unit)
        for outcome in [
            "recall_at_k",
            "ndcg_at_k",
            "mrr_at_k",
            "ndcg_lift_vs_popularity",
            "ndcg_lift_vs_random",
        ]
    }
    recall = primary_assoc.get("recall_at_k", {})
    ndcg = primary_assoc.get("ndcg_at_k", {})
    ndcg_lift = primary_assoc.get("ndcg_lift_vs_popularity", {})
    loss_improved = float((summary["loss_last"].astype(float) < summary["loss_first"].astype(float)).mean())
    model_validity_rate = float((summary["ndcg_lift_vs_popularity"].astype(float) > 0).mean())
    random_validity_rate = float((summary["ndcg_lift_vs_random"].astype(float) > 0).mean())
    mean_ndcg_lift = float(summary["ndcg_lift_vs_popularity"].mean())
    mean_recall_lift = float(summary["recall_lift_vs_popularity"].mean())
    mean_ndcg_lift_vs_random = float(summary["ndcg_lift_vs_random"].mean())
    mean_recall_lift_vs_random = float(summary["recall_lift_vs_random"].mean())
    model_validity_pass = bool(
        len(summary) >= 3
        and loss_improved >= 0.8
        and model_validity_rate >= 0.5
        and random_validity_rate >= 0.5
        and mean_ndcg_lift > 0
        and mean_ndcg_lift_vs_random > 0
    )
    directional = (
        int(recall.get("effective_n", 0) or 0) >= 3
        and int(ndcg.get("effective_n", 0) or 0) >= 3
        and float(recall.get("spearman", math.nan)) > 0
        and float(ndcg.get("spearman", math.nan)) > 0
        and float(ndcg_lift.get("spearman", math.nan)) > 0
    )
    strong = directional and float(ndcg.get("spearman", math.nan)) >= 0.30
    built_pass = bool(
        model_validity_pass
        and strong
        and int(ndcg.get("effective_n", 0) or 0) >= 8
        and float(ndcg.get("ci_low", -math.inf)) > 0
    )
    if not model_validity_pass:
        verdict = "built_fail_sequence_generator_model_validity"
    elif built_pass:
        verdict = "built_pass_sequence_generator_anchor"
    elif strong:
        verdict = "built_partial_sequence_generator_anchor_directional"
    elif directional:
        verdict = "built_weak_sequence_generator_anchor_directional"
    else:
        verdict = "built_fail_sequence_generator_anchor_not_supported"

    device_values = sorted(summary["device"].dropna().astype(str).unique()) if not summary.empty else []
    train_sec = float(summary["train_sec"].sum()) if "train_sec" in summary else 0.0
    train_samples = int(summary["train_samples_seen"].sum()) if "train_samples_seen" in summary else 0
    result = {
        "schema": "sidinspector.v1.gate12b.sequence_generator_anchor.v1",
        "run_id": args.run_id,
        "gate": "G12B_SEQUENCE_GENERATOR_ANCHOR",
        "verdict": verdict,
        "built_pass_for_75_target": built_pass,
        "model_validity_pass": model_validity_pass,
        "model_validity_rate_ndcg_beats_popularity": model_validity_rate,
        "model_validity_rate_ndcg_beats_random": random_validity_rate,
        "loss_improved_artifact_fold_rate": loss_improved,
        "mean_ndcg_lift_vs_popularity": mean_ndcg_lift,
        "mean_recall_lift_vs_popularity": mean_recall_lift,
        "mean_ndcg_lift_vs_random": mean_ndcg_lift_vs_random,
        "mean_recall_lift_vs_random": mean_recall_lift_vs_random,
        "sequence_generator_directional": bool(directional),
        "sequence_generator_strong": bool(strong),
        "artifact_rows": int(summary[_artifact_cols()].drop_duplicates().shape[0]) if not summary.empty else 0,
        "artifact_fold_rows": int(len(summary)),
        "user_metric_rows": int(len(user_metrics)),
        "folds": int(args.folds),
        "epochs": int(args.epochs),
        "rec_k": int(args.rec_k),
        "candidate_pool_size": int(args.candidate_pool_size),
        "max_users": int(args.max_users),
        "max_train_samples": int(args.max_train_samples),
        "max_eval_users": int(args.max_eval_users),
        "device": ",".join(device_values) if device_values else args.device,
        "total_wall_sec": float(time.perf_counter() - started),
        "total_train_sec": train_sec,
        "samples_per_sec": float(train_samples / train_sec) if train_sec > 0 else math.nan,
        "gpu_worthiness": "yes" if train_sec > 60 and train_samples > 0 else "no_or_unclear",
        "primary_associations": primary_assoc,
        "artifacts": {
            "fold_summary": str(output_root / "g12b_sequence_generator_fold_summary.csv"),
            "user_metrics": str(output_root / "g12b_sequence_generator_user_metrics.csv"),
            "associations": str(output_root / "g12b_sequence_generator_associations.csv"),
            "result": str(output_root / "g12b_sequence_generator_result.json"),
            "report": str(output_root / "GATE12B_RESULT.md"),
            "traces": str(trace_path) if args.export_traces else None,
        },
        "trace_export": {
            "enabled": bool(args.export_traces),
            "trace_rows": trace_rows_written,
            "trace_top_k": int(args.trace_top_k),
            "trace_path": str(trace_path) if args.export_traces else None,
            "decoding_mode": "candidate_pool_scoring" if args.export_traces else None,
        },
        "claim_update": (
            "G12b replaces the fixed SID-prefix-affinity scorer and the original "
            "mean-pooled tiny generator with a GRU history encoder plus "
            "autoregressive SID decoder. A positive result is claim-eligible only "
            "when the learned generator beats popularity/random baselines and D3 "
            "remains positively associated with generator utility or utility lift."
        ),
        "limitations": [
            "This is a fixed-budget sequence generator, not a full TIGER/T5 production recommender.",
            "Candidate pools are popularity-sampled hard negatives with targets added, not exhaustive full-catalog decoding.",
            "Artifact count is intentionally small; use this as a bounded utility anchor only if the model-validity gate passes.",
            "D7 failure-family traces are exported only when --export-traces is enabled; these traces are candidate-pool scoring rows, not free/unconstrained decoding beams.",
        ],
    }
    (output_root / "g12b_sequence_generator_result.json").write_text(
        json.dumps(_json_safe(result), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _run_record_path(args.runs_dir, args.run_id).write_text(
        json.dumps(_json_safe({"run_id": args.run_id, **result}), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_report(result, output_root)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g2-root", type=Path, default=DEFAULT_G2_ROOT)
    parser.add_argument("--manifest-path", type=Path)
    parser.add_argument(
        "--path-rewrite",
        action="append",
        default=[],
        help="Rewrite manifest path prefixes as OLD=NEW; may be repeated for AutoDL portability.",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--run-id", default="R732")
    parser.add_argument("--artifact-labels", default=DEFAULT_ARTIFACT_LABELS)
    parser.add_argument("--max-artifacts", type=int, default=-1)
    parser.add_argument("--folds", type=int, default=2)
    parser.add_argument("--analysis-depth", type=int, default=3)
    parser.add_argument("--d3-top-k", type=int, default=20)
    parser.add_argument("--max-pair-events", type=int, default=1_000_000)
    parser.add_argument("--max-user-items", type=int, default=200)
    parser.add_argument("--max-users", type=int, default=1200)
    parser.add_argument("--max-train-samples", type=int, default=4000)
    parser.add_argument("--train-targets-per-user", type=int, default=2)
    parser.add_argument("--max-history-items", type=int, default=50)
    parser.add_argument("--max-eval-users", type=int, default=120)
    parser.add_argument("--candidate-pool-size", type=int, default=500)
    parser.add_argument("--rec-k", type=int, default=20)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--embedding-dim", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--decoder-dim", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--bootstrap-samples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260620)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--export-traces", action="store_true", help="Export per-candidate trace rows for G19 D7 labeling.")
    parser.add_argument("--trace-top-k", type=int, default=20, help="Top ranked candidates per target to export with --export-traces.")
    parser.add_argument("--dummy", action="store_true", help="Run a synthetic micro-test under 60 seconds on CPU.")
    parser.add_argument("--smoke", action="store_true", help="Apply a small real-data smoke profile.")
    parser.add_argument("--validate-inputs-only", action="store_true", help="Validate selected manifest input paths and exit.")
    args = parser.parse_args()

    if args.smoke:
        args.artifact_labels = _parse_csv(args.artifact_labels)[0]
        args.max_artifacts = 1
        args.folds = 1
        args.max_users = min(args.max_users, 120)
        args.max_train_samples = min(args.max_train_samples, 200)
        args.max_eval_users = min(args.max_eval_users, 20)
        args.candidate_pool_size = min(args.candidate_pool_size, 100)
        args.epochs = min(args.epochs, 1)
        args.batch_size = min(args.batch_size, 32)
        args.embedding_dim = min(args.embedding_dim, 32)
        args.hidden_dim = min(args.hidden_dim, 64)
        args.decoder_dim = min(args.decoder_dim, 64)
        args.bootstrap_samples = 0
        args.device = "cpu"
    if args.dummy:
        args.folds = 1
        args.max_users = 100
        args.max_train_samples = 200
        args.max_eval_users = 10
        args.candidate_pool_size = 100
        args.epochs = 1
        args.batch_size = 4
        args.device = "cpu"
        args.bootstrap_samples = 0
        args.decoder_dim = min(args.decoder_dim, 32)

    if args.validate_inputs_only:
        result = validate_manifest_inputs(args)
        print(json.dumps(_json_safe(result), indent=2, sort_keys=True, allow_nan=False))
        return 0 if result["status"] == "pass" else 1

    result = close_gate12(args)
    print(json.dumps(_json_safe(result), indent=2, sort_keys=True, allow_nan=False))
    print(
        "load_sec={load:.4f} setup_sec={setup:.4f} train_sec={train:.4f} "
        "eval_sec={eval:.4f} samples_per_sec={sps:.4f} gpu_worthiness={worthy}".format(
            load=float(pd.read_csv(args.output_root / "g12b_sequence_generator_fold_summary.csv")["load_sec"].sum()),
            setup=float(pd.read_csv(args.output_root / "g12b_sequence_generator_fold_summary.csv")["setup_sec"].sum()),
            train=float(result["total_train_sec"]),
            eval=float(pd.read_csv(args.output_root / "g12b_sequence_generator_fold_summary.csv")["eval_sec"].sum()),
            sps=float(result["samples_per_sec"]) if not pd.isna(result["samples_per_sec"]) else math.nan,
            worthy=result["gpu_worthiness"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
