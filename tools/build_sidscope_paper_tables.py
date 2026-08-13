#!/usr/bin/env python3
"""Deterministically rebuild all eight SIDScope manuscript table snapshots.

The inputs are compact, released evidence summaries under
``docs/reproducibility/paper_table_sources``. This command does not retrain
tokenizers or regenerate omitted upstream datasets and checkpoints.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "docs" / "reproducibility" / "paper_table_sources"

COPIED_TABLES = {
    "table1_resource_delta.csv": "table1_resource_delta_source.csv",
    "table2_artifact_coverage.csv": "table2_artifact_coverage_source.csv",
    "table6_evidence_ladder.csv": "table4_evidence_ladder_source.csv",
    "table9_resource_contract.csv": "table6_resource_contract_source.csv",
    "table10_g20_trained_trace.csv": "table10_g20_trained_trace_source.csv",
}

TABLE5_FIELDS = [
    "artifact",
    "d1_unique_codes",
    "d2_collision_item_rate",
    "d3_depth1_weighted",
    "d4_tail_unique_ratio",
    "d5_active_prefix_counts",
    "source_evidence",
]

TABLE4_FIELDS = ["level", "question", "required_evidence", "source_evidence"]

TABLE8_FIELDS = [
    "mapping_model_state",
    "catalog_gaps",
    "d6_churn",
    "common_ndcg_at_20",
    "new_item_recall_at_20",
    "gate",
    "source_evidence",
]

CONFORMANCE_ROWS = [
    ("C0", "Is the source and reuse boundary explicit?", "URL, revision, derivation, license, redistribution"),
    ("C1", "Are normalized tables coherent?", "Schema, SID reconstruction, dataset, depth, item count"),
    ("C2", "Do mapping, metadata, and interactions join?", "Nonempty joined items and coverage report"),
    ("C3", "Does the diagnostic interface execute?", "Bounded D1--D5 outputs and limits"),
    ("C4", "Are inputs pinned and replayable?", "Command, runtime, evidence paths, three hashes"),
    ("C5", "May the route enter the paper matrix?", "Exact inventory identity and eligible evidence role"),
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if not fields or not rows:
        raise RuntimeError(f"Paper-table source is empty: {path}")
    return fields, rows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_table4_adapter_conformance() -> list[dict[str, str]]:
    return [
        {
            "level": level,
            "question": question,
            "required_evidence": evidence,
            "source_evidence": "docs/ADAPTER_CONFORMANCE.md",
        }
        for level, question, evidence in CONFORMANCE_ROWS
    ]


def build_table5_diagnostic_profile() -> list[dict[str, str]]:
    reports = [
        ("ReSID-GAOQ / Video", "resid_gaoq_video_report.json"),
        ("GRID / P5 Beauty", "grid_p5_beauty_report.json"),
        ("CARD / P5 Beauty", "card_p5_beauty_report.json"),
        ("DIGER / Beauty", "diger_beauty_report.json"),
        ("DIGER / Yelp", "diger_yelp_report.json"),
        ("ReSOT / Instruments", "resot_instruments_report.json"),
        ("LETTER / Instruments", "letter_instruments_report.json"),
        ("LC-Rec / Instruments", "lcrec_instruments_report.json"),
    ]
    output: list[dict[str, str]] = []
    for paper_label, report_name in reports:
        report_path = ROOT / "docs" / "reproducibility" / "conformance" / report_name
        report = read_json(report_path)
        checks = report.get("checks")
        if not isinstance(checks, list):
            raise RuntimeError(f"Conformance report lacks checks: {report_path}")
        metric_rows = [
            check.get("details", {}).get("metric_smoke_summary", [])
            for check in checks
            if isinstance(check, dict) and check.get("title") == "Bounded D1-D5 smoke"
        ]
        if len(metric_rows) != 1 or not isinstance(metric_rows[0], list) or len(metric_rows[0]) != 1:
            raise RuntimeError(f"Conformance report lacks one D1-D5 summary: {report_path}")
        row = metric_rows[0][0]
        if not isinstance(row, dict):
            raise RuntimeError(f"Malformed D1-D5 summary: {report_path}")
        output.append(
            {
                "artifact": paper_label,
                "d1_unique_codes": str(row["d1_unique_codes"]),
                "d2_collision_item_rate": f"{float(row['full_collision_rate']):.3f}",
                "d3_depth1_weighted": f"{float(row['d3_depth1_weighted_collab_recall']):.3f}",
                "d4_tail_unique_ratio": f"{float(row['d4_tail_sid_unique_ratio']):.3f}",
                "d5_active_prefix_counts": str(row["prefix_counts"]),
                "source_evidence": str(report_path.relative_to(ROOT)),
            }
        )
    return output


def build_table8_dact_handoff() -> list[dict[str, str]]:
    g22 = read_json(ROOT / "docs" / "reproducibility" / "g22_diagnose_repair_handoff_summary.json")
    diagnosis = g22["mapping_diagnosis"]
    protocol = g22["handoff_protocol"]
    handoff = g22["handoff_results"]
    if not isinstance(diagnosis, dict) or not isinstance(protocol, dict) or not isinstance(handoff, dict):
        raise RuntimeError("G22 summary lacks diagnosis, protocol, or handoff fields")
    adapted_seeds = [int(value) for value in protocol["adaptation_seeds"]]
    adapted_common = [float(value) for value in handoff["adapted_common_ndcg_at_20"]]
    adapted_new = [float(value) for value in handoff["adapted_new_item_recall_at_20"]]
    if not (len(adapted_seeds) == len(adapted_common) == len(adapted_new)):
        raise RuntimeError("G22 seed and adapted-result lengths differ")
    source = "docs/reproducibility/g22_diagnose_repair_handoff_summary.json"
    rows = [
        {
            "mapping_model_state": "0.6 / released model",
            "catalog_gaps": str(int(diagnosis["old_catalog_without_sid"])),
            "d6_churn": "0.0%",
            "common_ndcg_at_20": f"{float(handoff['old_model_old_mapping_common_ndcg_at_20']):.5f}",
            "new_item_recall_at_20": "--",
            "gate": "Baseline",
            "source_evidence": source,
        },
        {
            "mapping_model_state": "0.7 / released model",
            "catalog_gaps": str(int(diagnosis["repaired_catalog_without_sid"])),
            "d6_churn": f"{float(diagnosis['common_full_code_churn_rate']):.1%}",
            "common_ndcg_at_20": f"{float(handoff['old_model_new_mapping_common_ndcg_at_20']):.5f}",
            "new_item_recall_at_20": f"{float(handoff['old_model_new_mapping_new_item_recall_at_20']):.5f}",
            "gate": "Fail",
            "source_evidence": source,
        },
    ]
    for seed, common, new_item in zip(adapted_seeds, adapted_common, adapted_new):
        rows.append(
            {
                "mapping_model_state": f"0.7 / adapted, seed {seed}",
                "catalog_gaps": str(int(diagnosis["repaired_catalog_without_sid"])),
                "d6_churn": f"{float(diagnosis['common_full_code_churn_rate']):.1%}",
                "common_ndcg_at_20": f"{common:.5f}",
                "new_item_recall_at_20": f"{new_item:.5f}",
                "gate": "Pass",
                "source_evidence": source,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    for output_name, source_name in COPIED_TABLES.items():
        fields, rows = read_csv(SOURCE_DIR / source_name)
        write_csv(args.output_dir / output_name, fields, rows)
    write_csv(args.output_dir / "table4_adapter_conformance.csv", TABLE4_FIELDS, build_table4_adapter_conformance())
    write_csv(args.output_dir / "table5_diagnostic_profile.csv", TABLE5_FIELDS, build_table5_diagnostic_profile())
    write_csv(args.output_dir / "table8_resot_walkthrough.csv", TABLE8_FIELDS, build_table8_dact_handoff())
    print(f"Rebuilt {len(COPIED_TABLES) + 3} SIDScope manuscript tables in {args.output_dir}")


if __name__ == "__main__":
    main()
