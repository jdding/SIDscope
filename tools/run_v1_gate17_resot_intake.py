"""Run bounded ReSOT archive-route intake for SIDScope.

R759 is an intake gate only. It normalizes one verified ReSOT released index
branch, runs SIDScope preflight plus a bounded D1-D5 smoke, and records that the
row is not paper-facing until the main matrix is explicitly refreshed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sidinspector.adapters.resot import (  # noqa: E402
    normalize_resot_index,
    normalize_resot_interactions,
    normalize_resot_metadata,
)
from sidinspector.preflight import preflight_inputs  # noqa: E402


DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate17_resot_intake"
DEFAULT_RUN_JSON = PROJECT_ROOT / "experiments/v1_evidence_chain/runs/R759_resot_text_index_intake.json"
DEFAULT_RESULT_MD = DEFAULT_OUTPUT_ROOT / "G17_RESOT_INTAKE_RESULT.md"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric_smoke_row(preflight: dict[str, Any]) -> dict[str, Any]:
    rows = preflight.get("metric_smoke_summary") or []
    if not rows:
        return {}
    return dict(rows[0])


def _coverage_summary(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    return list(preflight.get("coverage") or [])


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    row = result["metric_smoke_summary"]
    coverage = result["coverage_summary"]
    lines = [
        "# R759 ReSOT Text-Index Intake",
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
    for item in coverage:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "Allowed after R759:",
            "",
            "- ReSOT has a SIDScope-normalized text-index Instruments intake row.",
            "- The row passes local input-contract preflight and bounded D1-D5 smoke.",
            "- No GPU is needed for this archive-route intake.",
            "",
            "Not allowed yet:",
            "",
            "- Counting ReSOT in the current paper-facing matrix.",
            "- Updating G2/G3/G4 row counts without an explicit matrix refresh.",
            "- Describing this as a trained-generator result.",
            "- Dropping the no-license-detected reuse caveat.",
            "",
            "## Next Step If Promoted",
            "",
            "Run the matrix-refresh path that recomputes D1-D5/G2/G3/G4 with the ReSOT row, then update the claim ledger, table/figure ledger, release manifest, and paper counts.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_intake(args: argparse.Namespace) -> dict[str, Any]:
    normalized_dir = args.output_root / "normalized_text"
    normalized_dir.mkdir(parents=True, exist_ok=True)

    sid_assignments = normalize_resot_index(
        args.index_json,
        item2id_path=args.item2id,
        method=args.method,
        dataset=args.dataset_name,
    )
    item_metadata = normalize_resot_metadata(args.item_json, item2id_path=args.item2id, dataset=args.dataset_name)
    interactions = normalize_resot_interactions(
        args.inter_json,
        item2id_path=args.item2id,
        dataset=args.dataset_name,
        split=args.interaction_split,
    )

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

    result = {
        "schema": "sidscope.g17.resot_intake.v1",
        "run_id": "R759",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "PASS_INTAKE_NOT_MATRIX_PROMOTED",
        "clear_conclusion": (
            "ReSOT text-index Instruments normalizes and passes bounded SIDScope preflight; "
            "it is still excluded from paper-facing matrix counts until a refresh gate reruns G2/G3/G4."
        ),
        "gate": "G17_P6_SOURCE_PROVENANCE_AND_MATRIX_EXTENSION",
        "row_label": "ReSOT text-index official-code-derived / Instruments",
        "method": args.method,
        "dataset": args.dataset_name,
        "item_id_boundary": (
            "SIDScope metric tables use ReSOT's numeric dense id as item_id; "
            "the released ASIN from item2id is retained in source_item_id."
        ),
        "gpu_required": False,
        "matrix_change_now": "none",
        "inputs": {
            "index_json": str(args.index_json),
            "item2id": str(args.item2id),
            "item_json": str(args.item_json),
            "inter_json": str(args.inter_json),
            "source_route": "verified ReSOT Google Drive data.zip archive; R758 central-directory and range-extracted content checks",
        },
        "outputs": {
            "sid_assignments": str(sid_path),
            "item_metadata": str(metadata_path),
            "interactions": str(interactions_path),
            "preflight_metric_smoke": str(preflight_path),
            "result_markdown": str(args.result_md),
        },
        "normalized_tables": {
            "sid_assignments": {"rows": int(len(sid_assignments)), "columns": list(sid_assignments.columns)},
            "item_metadata": {"rows": int(len(item_metadata)), "columns": list(item_metadata.columns)},
            "interactions": {"rows": int(len(interactions)), "columns": list(interactions.columns)},
        },
        "coverage_summary": _coverage_summary(preflight),
        "metric_smoke_summary": _metric_smoke_row(preflight),
        "bounds": preflight["bounds"],
        "allowed_claims": [
            "ReSOT has a SIDScope-normalized text-index Instruments intake row.",
            "The row passes local input-contract preflight and bounded D1-D5 smoke.",
        ],
        "forbidden_claims_before_refresh": [
            "Count ReSOT in the current paper-facing matrix.",
            "Update G2/G3/G4 row counts without recomputation.",
            "Treat this as trained-generator evidence.",
        ],
        "license_boundary": "No GitHub license detected during G17 source audit; preserve conservative reuse wording.",
    }
    _write_json(args.run_json, result)
    _write_markdown(args.result_md, result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded ReSOT text-index intake.")
    parser.add_argument("--index-json", type=Path, required=True)
    parser.add_argument("--item2id", type=Path, required=True)
    parser.add_argument("--item-json", type=Path, required=True)
    parser.add_argument("--inter-json", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-json", type=Path, default=DEFAULT_RUN_JSON)
    parser.add_argument("--result-md", type=Path, default=DEFAULT_RESULT_MD)
    parser.add_argument("--dataset-name", default="Instruments")
    parser.add_argument("--method", default="resot_text_index_official_code_derived")
    parser.add_argument("--interaction-split", default=None)
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
