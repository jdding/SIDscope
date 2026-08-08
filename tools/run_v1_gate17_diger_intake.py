"""Run bounded DIGER RQ-VAE official-code-derived intake for SIDScope.

R763 exports item codes from DIGER's public Beauty RQ-VAE checkpoint and public
processed embeddings, normalizes the result through SIDScope, and runs local
preflight plus bounded D1-D5 smoke. The row is not paper-facing until the main
matrix is explicitly refreshed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sidinspector.adapters.diger import (  # noqa: E402
    normalize_diger_codes,
    normalize_diger_interactions,
    normalize_diger_metadata,
    read_diger_emb_map,
)
from sidinspector.preflight import preflight_inputs  # noqa: E402


DEFAULT_UPSTREAM = PROJECT_ROOT / "experiments/v1_evidence_chain/upstreams/diger/DIGER"
DEFAULT_HF_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/upstreams/diger/hf"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate17_diger_intake"
DEFAULT_RUN_JSON = PROJECT_ROOT / "experiments/v1_evidence_chain/runs/R763_diger_rqvae_intake.json"
DEFAULT_RESULT_MD = DEFAULT_OUTPUT_ROOT / "G17_DIGER_INTAKE_RESULT.md"


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _load_rqvae_class(upstream_root: Path):
    rqvae_root = upstream_root / "scripts/rqvae"
    if str(rqvae_root) not in sys.path:
        sys.path.insert(0, str(rqvae_root))
    from models.rqvae import RQVAE  # type: ignore

    return RQVAE


def _load_checkpoint(path: Path) -> dict[str, Any]:
    return torch.load(path, map_location="cpu", weights_only=False)


def _validate_checkpoint(ckpt: dict[str, Any]) -> dict[str, Any]:
    args = ckpt.get("args")
    if not hasattr(args, "__dict__"):
        raise ValueError("DIGER checkpoint args must be an argparse.Namespace-like object")
    state_dict = ckpt.get("state_dict")
    if not isinstance(state_dict, dict) or not state_dict:
        raise ValueError("DIGER checkpoint missing non-empty state_dict")
    required_prefixes = ("encoder.", "rq.", "decoder.")
    missing = [prefix for prefix in required_prefixes if not any(key.startswith(prefix) for key in state_dict)]
    if missing:
        raise ValueError(f"DIGER checkpoint state_dict missing prefixes: {missing}")
    return {
        "epoch": ckpt.get("epoch"),
        "best_collision_rate": ckpt.get("best_collision_rate"),
        "args": dict(args.__dict__),
        "state_dict_keys": len(state_dict),
    }


def export_diger_codes(
    *,
    upstream_root: Path,
    embedding_path: Path,
    checkpoint_path: Path,
    batch_size: int,
) -> np.ndarray:
    embeddings = np.load(embedding_path, mmap_mode="r")
    if embeddings.ndim != 2:
        raise ValueError(f"Expected 2D embedding array, got shape={embeddings.shape}")

    ckpt = _load_checkpoint(checkpoint_path)
    args = ckpt["args"]
    args.device = "cpu"
    RQVAE = _load_rqvae_class(upstream_root)
    model = RQVAE(args=args, in_dim=int(embeddings.shape[1]))
    model.load_state_dict(ckpt["state_dict"], strict=True)
    model.eval()

    outputs: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(embeddings), batch_size):
            batch = np.asarray(embeddings[start : start + batch_size], dtype=np.float32)
            tensor = torch.from_numpy(batch)
            indices = model.get_indices(tensor)
            outputs.append(indices.detach().cpu().numpy().astype(np.int64))
    return np.concatenate(outputs, axis=0)


def _metric_smoke_row(preflight: dict[str, Any]) -> dict[str, Any]:
    rows = preflight.get("metric_smoke_summary") or []
    return dict(rows[0]) if rows else {}


def _coverage_summary(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    return list(preflight.get("coverage") or [])


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    row = result["metric_smoke_summary"]
    lines = [
        "# R763 DIGER RQ-VAE Intake",
        "",
        f"Date: {result['date']}",
        "",
        "```text",
        f"STATUS: {result['status']}",
        f"CLEAR_CONCLUSION: {result['clear_conclusion']}",
        f"MATRIX_CHANGE_NOW: {result['matrix_change_now']}",
        f"GPU_REQUIRED: {str(result['gpu_required']).lower()}",
        "```",
        "",
        "## Normalized Row",
        "",
        f"- Label: `{result['row_label']}`",
        f"- Method: `{result['method']}`",
        f"- Dataset: `{result['dataset']}`",
        f"- SID rows: `{result['normalized_tables']['sid_assignments']['rows']}`",
        f"- Metadata rows: `{result['normalized_tables']['item_metadata']['rows']}`",
        f"- Interaction rows: `{result['normalized_tables']['interactions']['rows']}`",
        f"- Item ID boundary: {result['item_id_boundary']}",
        "",
        "## Bounded Metric Smoke",
        "",
        f"- Unique full SIDs: `{row.get('unique_sid')}`",
        f"- Duplicate SID rate: `{row.get('duplicate_sid_rate')}`",
        f"- Full-code collision rate: `{row.get('full_collision_rate')}`",
        f"- D3 depth-1 weighted co-occurrence recall: `{row.get('d3_depth1_weighted_collab_recall')}`",
        f"- D5 prefix counts: `{row.get('prefix_counts')}`",
        "",
        "## Coverage",
        "",
    ]
    for item in result["coverage_summary"]:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "Allowed after R763:",
            "",
            "- DIGER has a SIDScope-normalized RQ-VAE official-code-derived Beauty intake row.",
            "- The row passes local input-contract preflight and bounded D1-D5 smoke.",
            "- No GPU is needed for this tokenizer-stage export.",
            "",
            "Not allowed from R763 alone:",
            "",
            "- Counting DIGER in the current paper-facing matrix without an explicit refresh.",
            "- Calling the row an author-released item-to-SID mapping.",
            "- Claiming full DIGER differentiable assignment or trained-generator coverage.",
            "- Dropping the no-license-detected reuse caveat.",
            "",
            "## Next Step If Promoted",
            "",
            "Run the matrix-refresh path that recomputes D1-D5/G2/G3/G4 with the DIGER row, then update the claim ledger, table/figure ledger, release manifest, and paper counts.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_intake(args: argparse.Namespace) -> dict[str, Any]:
    upstream_root = _require(args.upstream_root)
    beauty_root = _require(args.hf_root / "beauty")
    checkpoint_path = _require(args.hf_root / "rqvae_beauty/best_collision_model.pth")
    emb_map_path = _require(beauty_root / "beauty.emb_map.json")
    embedding_path = _require(beauty_root / "Beauty.emb-llama.npy")
    interaction_paths = [
        _require(beauty_root / "beauty.train.jsonl"),
        _require(beauty_root / "beauty.valid.jsonl"),
        _require(beauty_root / "beauty.test.jsonl"),
    ]

    stats_path = _require(beauty_root / "beauty_stats.json")
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    item_map = read_diger_emb_map(emb_map_path)
    codes = export_diger_codes(
        upstream_root=upstream_root,
        embedding_path=embedding_path,
        checkpoint_path=checkpoint_path,
        batch_size=args.batch_size,
    )
    if codes.shape[0] != int(stats["n_items"]):
        raise ValueError(f"Exported {codes.shape[0]} code rows but stats reports n_items={stats['n_items']}")

    normalized_dir = args.output_root / "normalized_rqvae_beauty"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    np.save(normalized_dir / "diger_rqvae_codes.npy", codes)

    sid_assignments = normalize_diger_codes(codes, emb_map_path, method=args.method, dataset=args.dataset_name)
    item_metadata = normalize_diger_metadata(emb_map_path, dataset=args.dataset_name)
    interactions = normalize_diger_interactions(interaction_paths, emb_map_path, dataset=args.dataset_name)

    sid_path = normalized_dir / "sid_assignments.parquet"
    metadata_path = normalized_dir / "item_metadata.parquet"
    interactions_path = normalized_dir / "interactions.parquet"
    sid_assignments.to_parquet(sid_path, index=False)
    item_metadata.to_parquet(metadata_path, index=False)
    interactions.to_parquet(interactions_path, index=False)

    preflight = preflight_inputs(
        sid_path,
        metadata_path,
        interactions_path,
        allow_partial_coverage=False,
        run_metric_smoke=True,
        max_metric_items=args.max_metric_items,
        top_k=args.d3_top_k,
        max_pair_events=args.d3_max_pair_events,
        max_user_items=args.d3_max_user_items,
    )
    preflight_path = args.output_root / "preflight_metric_smoke.json"
    _write_json(preflight_path, preflight)

    ckpt = _load_checkpoint(checkpoint_path)
    result = {
        "schema": "sidscope.g17.diger_intake.v1",
        "run_id": "R763",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "PASS_INTAKE_NOT_MATRIX_PROMOTED",
        "clear_conclusion": (
            "DIGER RQ-VAE Beauty exports complete item codes from public upstream "
            "sources and passes bounded SIDScope preflight; it is excluded from "
            "paper-facing matrix counts until an explicit refresh reruns G2/G3/G4."
        ),
        "gate": "G17_P6_SOURCE_PROVENANCE_AND_MATRIX_EXTENSION",
        "row_label": "DIGER RQ-VAE official-code-derived / Beauty",
        "method": args.method,
        "dataset": args.dataset_name,
        "item_id_boundary": (
            "SIDScope uses DIGER embedding row ids as numeric item_id values; "
            "the upstream item_* id and DIGER token id are retained for provenance."
        ),
        "gpu_required": False,
        "matrix_change_now": "none",
        "inputs": {
            "upstream_root": str(upstream_root),
            "embedding_path": str(embedding_path),
            "emb_map": str(emb_map_path),
            "interaction_paths": [str(path) for path in interaction_paths],
            "checkpoint": str(checkpoint_path),
            "hf_dataset_sha": "42f26ba9d98338ae24aa8b552a952326e516b5fd",
            "hf_model_sha": "aeabd516a4078f7e849d79e5af0198365f88f9ba",
        },
        "input_sha256": {
            "embedding": _sha256(embedding_path),
            "emb_map": _sha256(emb_map_path),
            "stats": _sha256(stats_path),
            "checkpoint": _sha256(checkpoint_path),
        },
        "checkpoint_summary": _validate_checkpoint(ckpt),
        "normalized_tables": {
            "sid_assignments": {"rows": int(len(sid_assignments)), "columns": list(sid_assignments.columns)},
            "item_metadata": {"rows": int(len(item_metadata)), "columns": list(item_metadata.columns)},
            "interactions": {"rows": int(len(interactions)), "columns": list(interactions.columns)},
        },
        "export_summary": {
            "embedding_shape": list(np.load(embedding_path, mmap_mode="r").shape),
            "embedding_dtype": str(np.load(embedding_path, mmap_mode="r").dtype),
            "emb_map_rows_excluding_pad": int(len(item_map)),
            "code_shape": list(codes.shape),
            "code_depth": int(codes.shape[1]),
            "unique_full_sids": int(sid_assignments["sid"].nunique()),
        },
        "outputs": {
            "sid_assignments": str(sid_path),
            "item_metadata": str(metadata_path),
            "interactions": str(interactions_path),
            "codes": str(normalized_dir / "diger_rqvae_codes.npy"),
            "preflight_metric_smoke": str(preflight_path),
            "result_markdown": str(args.result_md),
        },
        "coverage_summary": _coverage_summary(preflight),
        "metric_smoke_summary": _metric_smoke_row(preflight),
        "bounds": preflight["bounds"],
        "allowed_claims": [
            "DIGER has a SIDScope-normalized RQ-VAE official-code-derived Beauty intake row.",
            "The row passes local input-contract preflight and bounded D1-D5 smoke.",
        ],
        "forbidden_claims_before_refresh": [
            "Count DIGER in the current paper-facing matrix.",
            "Describe the row as an author-released DIGER mapping.",
            "Treat this as trained-generator evidence.",
        ],
        "license_boundary": "No GitHub license detected during G17 source audit; preserve conservative reuse wording.",
    }
    _write_json(args.run_json, result)
    _write_markdown(args.result_md, result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded DIGER RQ-VAE Beauty intake.")
    parser.add_argument("--upstream-root", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--hf-root", type=Path, default=DEFAULT_HF_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-json", type=Path, default=DEFAULT_RUN_JSON)
    parser.add_argument("--result-md", type=Path, default=DEFAULT_RESULT_MD)
    parser.add_argument("--dataset-name", default="beauty")
    parser.add_argument("--method", default="diger_rqvae_official_code_derived")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-metric-items", type=int, default=50_000)
    parser.add_argument("--d3-top-k", type=int, default=5)
    parser.add_argument("--d3-max-pair-events", type=int, default=10_000)
    parser.add_argument("--d3-max-user-items", type=int, default=50)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    result = run_intake(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
