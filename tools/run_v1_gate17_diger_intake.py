"""Run a bounded DIGER RQ-VAE official-code-derived intake for SIDScope.

The default remains the historical R763 Beauty intake. G23 adds the official
Yelp route through the same exporter and normalized contract; neither route is
paper-facing until its explicit matrix-refresh gate passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


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

DATASET_PROFILES: dict[str, dict[str, Any]] = {
    "beauty": {
        "dataset_name": "beauty",
        "paper_dataset": "Beauty",
        "data_dir": "beauty",
        "checkpoint_dir": "rqvae_beauty",
        "embedding_file": "Beauty.emb-llama.npy",
        "map_file": "beauty.emb_map.json",
        "split_files": ["beauty.train.jsonl", "beauty.valid.jsonl", "beauty.test.jsonl"],
        "stats_file": "beauty_stats.json",
        "hf_dataset_revision": "42f26ba9d98338ae24aa8b552a952326e516b5fd",
        "hf_model_revision": "aeabd516a4078f7e849d79e5af0198365f88f9ba",
        "embedding_sha256": "08b80b2be6d12438d4da6001fab566b015ba209ac2ad9c4690628f4be24fe16a",
        "checkpoint_sha256": "845d78dbff476754de239d6950b60b8b2c51f486f5f790785e5ccc16f839d297",
        "map_sha256": "393505f65b7ebd13b3e54d80827bac7bc3cc592cfa113321f2a715287815a97e",
        "interaction_sha256": {
            "beauty.train.jsonl": "e5b1d7ceb62d5294f4786b711dba829c844488a7bd229aca65e4905e4b85962d",
            "beauty.valid.jsonl": "04c38f3a5c81a8b9f3010fa0676599ab3d718c3d40b6edbfafd910c20578089d",
            "beauty.test.jsonl": "88d594ff285b58854d5445b6d8ed08934b6c4b2a5e6d1bbbd4ca04ad07775ba5",
        },
        "upstream_revision": "fccf1229581440645a18563ece9c65bf72f1aa01",
        "upstream_rqvae_tree": "9a86cf6baf474371a22dc96e0c4735c6045ca0e0",
        "expected_depth": 3,
        "run_id": "R763",
        "output_root": DEFAULT_OUTPUT_ROOT,
        "run_json": DEFAULT_RUN_JSON,
        "result_md": DEFAULT_RESULT_MD,
    },
    "yelp": {
        "dataset_name": "yelp",
        "paper_dataset": "Yelp",
        "data_dir": "yelp",
        "checkpoint_dir": "rqvae_yelp",
        "embedding_file": "Yelp.emb-llama.npy",
        "map_file": "yelp.emb_map.json",
        "split_files": ["yelp.train.jsonl", "yelp.valid.jsonl", "yelp.test.jsonl"],
        "stats_file": None,
        "hf_dataset_revision": "42f26ba9d98338ae24aa8b552a952326e516b5fd",
        "hf_model_revision": "ef1f7792daf39d963e88559c4d19ab5cf06195db",
        "embedding_sha256": "7e313fc32174f91db96da9cef3859012af5e3db46d963f36da7823ba622cf484",
        "checkpoint_sha256": "696b3df0197b3174e7e52acd6193bb9e08841275ed24b8dd2feb1b0124c1ba79",
        "map_sha256": "5fc71078cc21398113c3ea391a0948e7323ba97a7a5611eca54bd80d56ac1858",
        "interaction_sha256": {
            "yelp.train.jsonl": "5a90029c196fd5ad216056bbf4987225973f0fde75ee2a0d33a22735c732da10",
            "yelp.valid.jsonl": "a06ecba37f8f4d1ab226018dad40d2cceb77e9527f5206d2a57f369cc8149083",
            "yelp.test.jsonl": "675e979463f3290209731e0d7fc08b4e5f6ba97d7b77d39c9b3b6c71e5952dd4",
        },
        "upstream_revision": "cd72dcdc25d28e0acfa5aea14788ad863b41ab4f",
        "upstream_rqvae_tree": "9a86cf6baf474371a22dc96e0c4735c6045ca0e0",
        "expected_depth": 3,
        "run_id": "R828",
        "output_root": PROJECT_ROOT / "experiments/v1_evidence_chain/gate23_non_amazon_route_expansion/intake",
        "run_json": PROJECT_ROOT / "experiments/v1_evidence_chain/runs/R828_diger_yelp_intake.json",
        "result_md": PROJECT_ROOT / "experiments/v1_evidence_chain/gate23_non_amazon_route_expansion/G23_DIGER_YELP_INTAKE_RESULT.md",
    },
}


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


def _git_source_identity(upstream_root: Path) -> dict[str, str]:
    def git(*parts: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(upstream_root), *parts],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    status = git("status", "--porcelain", "--untracked-files=no")
    if status:
        raise ValueError("DIGER upstream checkout has modified tracked files")
    untracked = git("ls-files", "--others", "--exclude-standard", "scripts/rqvae")
    unsafe_untracked = [
        path for path in untracked.splitlines() if path and not Path(path).name.startswith("._")
    ]
    if unsafe_untracked:
        raise ValueError(
            f"DIGER RQ-VAE source tree has untracked executable inputs: {unsafe_untracked}"
        )
    return {
        "revision": git("rev-parse", "HEAD"),
        "rqvae_tree": git("rev-parse", "HEAD:scripts/rqvae"),
    }


def _verify_hash(path: Path, expected: str, label: str) -> str:
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"{label} SHA-256 mismatch: {observed} != {expected}")
    return observed


def _load_rqvae_class(upstream_root: Path):
    rqvae_root = upstream_root / "scripts/rqvae"
    if str(rqvae_root) not in sys.path:
        sys.path.insert(0, str(rqvae_root))
    from models.rqvae import RQVAE  # type: ignore

    return RQVAE


def _load_checkpoint(path: Path) -> dict[str, Any]:
    import torch

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
    import torch

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


def _resolve_item_count(
    *, item_map_rows: int, embedding_rows: int, stats_path: Path | None
) -> tuple[int, dict[str, Any]]:
    if item_map_rows != embedding_rows:
        raise ValueError(
            f"DIGER map has {item_map_rows} items but embedding has {embedding_rows} rows"
        )
    evidence: dict[str, Any] = {
        "source": "released_emb_map_and_embedding_shape",
        "item_map_rows_excluding_pad": item_map_rows,
        "embedding_rows": embedding_rows,
    }
    if stats_path is not None:
        stats = json.loads(_require(stats_path).read_text(encoding="utf-8"))
        stats_items = int(stats["n_items"])
        evidence["stats_n_items"] = stats_items
        evidence["stats_path"] = str(stats_path)
        if stats_items != item_map_rows:
            raise ValueError(
                f"DIGER stats has {stats_items} items but map has {item_map_rows}"
            )
        evidence["source"] = "released_stats_map_and_embedding_shape"
    return item_map_rows, evidence


def _metric_smoke_row(preflight: dict[str, Any]) -> dict[str, Any]:
    rows = preflight.get("metric_smoke_summary") or []
    return dict(rows[0]) if rows else {}


def _coverage_summary(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    return list(preflight.get("coverage") or [])


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    row = result["metric_smoke_summary"]
    lines = [
        f"# {result['run_id']} DIGER RQ-VAE Intake",
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
            f"Allowed after {result['run_id']}:",
            "",
            f"- DIGER has a SIDScope-normalized RQ-VAE official-code-derived {result['paper_dataset']} intake row.",
            "- The row passes local input-contract preflight and bounded D1-D5 smoke.",
            "- No GPU is needed for this tokenizer-stage export.",
            "",
            f"Not allowed from {result['run_id']} alone:",
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
    profile = DATASET_PROFILES[args.dataset_key]
    dataset_name = args.dataset_name or str(profile["dataset_name"])
    paper_dataset = str(profile["paper_dataset"])
    output_root = args.output_root or Path(profile["output_root"])
    run_json = args.run_json or Path(profile["run_json"])
    result_md = args.result_md or Path(profile["result_md"])
    run_id = args.run_id or str(profile["run_id"])
    normalized_dir = output_root / f"normalized_rqvae_{args.dataset_key}"
    pass_marker = normalized_dir / "intake_pass.json"
    if pass_marker.exists():
        pass_marker.unlink()
    if args.dataset_key == "yelp":
        admission = output_root.parent / "G23_MATRIX_ADMISSION.json"
        if admission.exists():
            admission.unlink()

    upstream_root = _require(args.upstream_root)
    data_root = _require(args.hf_root / str(profile["data_dir"]))
    checkpoint_path = _require(
        args.hf_root / str(profile["checkpoint_dir"]) / "best_collision_model.pth"
    )
    emb_map_path = _require(data_root / str(profile["map_file"]))
    embedding_path = _require(data_root / str(profile["embedding_file"]))
    interaction_paths = [
        _require(data_root / str(filename)) for filename in profile["split_files"]
    ]

    source_identity = _git_source_identity(upstream_root)
    if source_identity["revision"] != profile["upstream_revision"]:
        raise ValueError(
            f"DIGER upstream revision mismatch: {source_identity['revision']} != "
            f"{profile['upstream_revision']}"
        )
    if source_identity["rqvae_tree"] != profile["upstream_rqvae_tree"]:
        raise ValueError(
            f"DIGER RQ-VAE tree mismatch: {source_identity['rqvae_tree']} != "
            f"{profile['upstream_rqvae_tree']}"
        )
    observed_embedding_sha = _verify_hash(
        embedding_path, str(profile["embedding_sha256"]), "Embedding"
    )
    observed_checkpoint_sha = _verify_hash(
        checkpoint_path, str(profile["checkpoint_sha256"]), "Checkpoint"
    )
    observed_map_sha = _verify_hash(emb_map_path, str(profile["map_sha256"]), "emb_map")
    observed_interaction_sha = {
        path.name: _verify_hash(
            path,
            str(profile["interaction_sha256"][path.name]),
            path.name,
        )
        for path in interaction_paths
    }

    item_map = read_diger_emb_map(emb_map_path)
    embedding_shape = np.load(embedding_path, mmap_mode="r").shape
    if len(embedding_shape) != 2:
        raise ValueError(f"Expected 2D embedding array, got shape={embedding_shape}")
    stats_name = profile.get("stats_file")
    stats_path = data_root / str(stats_name) if stats_name else None
    expected_items, item_count_evidence = _resolve_item_count(
        item_map_rows=len(item_map),
        embedding_rows=int(embedding_shape[0]),
        stats_path=stats_path,
    )
    codes = export_diger_codes(
        upstream_root=upstream_root,
        embedding_path=embedding_path,
        checkpoint_path=checkpoint_path,
        batch_size=args.batch_size,
    )
    if codes.shape != (expected_items, int(profile["expected_depth"])):
        raise ValueError(
            f"Exported code shape {codes.shape}; expected {(expected_items, profile['expected_depth'])}"
        )

    sid_assignments = normalize_diger_codes(codes, emb_map_path, method=args.method, dataset=dataset_name)
    item_metadata = normalize_diger_metadata(emb_map_path, dataset=dataset_name)
    interactions = normalize_diger_interactions(interaction_paths, emb_map_path, dataset=dataset_name)
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{args.dataset_key}-intake-", dir=output_root) as tmp:
        staging = Path(tmp)
        staged_codes = staging / "diger_rqvae_codes.npy"
        staged_sid = staging / "sid_assignments.parquet"
        staged_metadata = staging / "item_metadata.parquet"
        staged_interactions = staging / "interactions.parquet"
        np.save(staged_codes, codes)
        sid_assignments.to_parquet(staged_sid, index=False)
        item_metadata.to_parquet(staged_metadata, index=False)
        interactions.to_parquet(staged_interactions, index=False)
        preflight = preflight_inputs(
            staged_sid,
            staged_metadata,
            staged_interactions,
            allow_partial_coverage=False,
            run_metric_smoke=True,
            max_metric_items=args.max_metric_items,
            top_k=args.d3_top_k,
            max_pair_events=args.d3_max_pair_events,
            max_user_items=args.d3_max_user_items,
        )
        normalized_dir.mkdir(parents=True, exist_ok=True)
        for staged in (staged_codes, staged_sid, staged_metadata, staged_interactions):
            os.replace(staged, normalized_dir / staged.name)

    sid_path = normalized_dir / "sid_assignments.parquet"
    metadata_path = normalized_dir / "item_metadata.parquet"
    interactions_path = normalized_dir / "interactions.parquet"
    preflight_path = output_root / f"preflight_metric_smoke_{args.dataset_key}.json"
    _write_json(preflight_path, preflight)

    ckpt = _load_checkpoint(checkpoint_path)
    result = {
        "schema": "sidscope.diger_intake.v2",
        "run_id": run_id,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "PASS_INTAKE_NOT_MATRIX_PROMOTED",
        "clear_conclusion": (
            f"DIGER RQ-VAE {paper_dataset} exports complete item codes from public upstream "
            "sources and passes bounded SIDScope preflight; it is excluded from "
            "paper-facing matrix counts until an explicit refresh reruns G2/G3/G4."
        ),
        "gate": "G17_P6_SOURCE_PROVENANCE_AND_MATRIX_EXTENSION" if args.dataset_key == "beauty" else "G23_DIGER_YELP_NON_AMAZON_INTAKE",
        "row_label": f"DIGER RQ-VAE official-code-derived / {paper_dataset}",
        "paper_dataset": paper_dataset,
        "method": args.method,
        "dataset": dataset_name,
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
            "hf_dataset_sha": profile["hf_dataset_revision"],
            "hf_model_sha": profile["hf_model_revision"],
            "upstream_revision": source_identity["revision"],
            "upstream_rqvae_tree": source_identity["rqvae_tree"],
        },
        "input_sha256": {
            "embedding": observed_embedding_sha,
            "emb_map": observed_map_sha,
            "checkpoint": observed_checkpoint_sha,
            "interactions": observed_interaction_sha,
            **({"stats": _sha256(stats_path)} if stats_path is not None else {}),
        },
        "item_count_evidence": item_count_evidence,
        "checkpoint_summary": _validate_checkpoint(ckpt),
        "normalized_tables": {
            "sid_assignments": {"rows": int(len(sid_assignments)), "columns": list(sid_assignments.columns)},
            "item_metadata": {"rows": int(len(item_metadata)), "columns": list(item_metadata.columns)},
            "interactions": {"rows": int(len(interactions)), "columns": list(interactions.columns)},
        },
        "export_summary": {
            "embedding_shape": list(embedding_shape),
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
            "result_markdown": str(result_md),
        },
        "coverage_summary": _coverage_summary(preflight),
        "metric_smoke_summary": _metric_smoke_row(preflight),
        "bounds": preflight["bounds"],
        "allowed_claims": [
            f"DIGER has a SIDScope-normalized RQ-VAE official-code-derived {paper_dataset} intake row.",
            "The row passes local input-contract preflight and bounded D1-D5 smoke.",
        ],
        "forbidden_claims_before_refresh": [
            "Count DIGER in the current paper-facing matrix.",
            "Describe the row as an author-released DIGER mapping.",
            "Treat this as trained-generator evidence.",
        ],
        "license_boundary": "No GitHub license detected during G17 source audit; preserve conservative reuse wording.",
    }
    _write_json(run_json, result)
    _write_markdown(result_md, result)
    _write_json(
        pass_marker,
        {
            "schema": "sidscope.diger_intake_pass.v1",
            "run_id": run_id,
            "status": "pass",
            "normalized_input_sha256": {
                "sid_assignments": _sha256(sid_path),
                "item_metadata": _sha256(metadata_path),
                "interactions": _sha256(interactions_path),
            },
            "source_identity": source_identity,
        },
    )
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded DIGER RQ-VAE intake.")
    parser.add_argument("--upstream-root", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--hf-root", type=Path, default=DEFAULT_HF_ROOT)
    parser.add_argument("--dataset-key", choices=sorted(DATASET_PROFILES), default="beauty")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--run-json", type=Path)
    parser.add_argument("--result-md", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--dataset-name")
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
