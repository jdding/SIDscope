#!/usr/bin/env python3
"""Deterministically rebuild all ten SIDScope manuscript table snapshots.

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
    "table7_trace_accounting.csv": "table5_trace_accounting_source.csv",
    "table9_resource_contract.csv": "table6_resource_contract_source.csv",
    "table10_g20_trained_trace.csv": "table10_g20_trained_trace_source.csv",
}

TABLE5_FIELDS = [
    "group",
    "artifact",
    "unique_sids",
    "d2_aliasing_rate",
    "d3_l1_weighted",
    "source_evidence",
]

TABLE3_FIELDS = [
    "artifact_route",
    "derivation",
    "configuration_identity",
    "reuse_boundary",
    "conformance_evidence",
    "source_evidence",
]

TABLE4_FIELDS = ["level", "question", "required_evidence", "source_evidence"]

TABLE8_FIELDS = ["stage", "question", "evidence", "decision", "source_evidence"]

INVENTORY_PROJECTION = {
    "resid_musical_snapshot": (
        "Tracked snapshot",
        "depth 3; active prefixes 32/1280/23742",
        "Code/data licensed; returned mapping boundary unresolved",
        "Auditable snapshot",
    ),
    "resid_gaoq_video": (
        "Official-code-derived",
        "FAMAE+GAOQ; 32/64/64; 50 epochs",
        "MIT; summaries and derived tables",
        "C0--C5 pass",
    ),
    "grid_p5_beauty": (
        "Tokenizer-stage rebuild",
        "seed 42; 3 levels; width 256",
        "Restricted research source; no upstream data redistribution",
        "C0--C5 pass",
    ),
    "card_p5_beauty": (
        "Code-derived with shim",
        "4 levels; width 256; 20 epochs",
        "No license detected; summary only",
        "C0--C5 pass",
    ),
    "diger_beauty": (
        "Official-code-derived",
        "3 levels; width 256; checkpoint pinned",
        "No license detected; summary only",
        "C0--C5 pass",
    ),
    "resot_instruments": (
        "Released archive",
        "text index; 4 levels; 6,250 unique leaves",
        "No license detected; archive not redistributed",
        "C0--C5 pass",
    ),
    "letter_instruments": (
        "Released index",
        "4 levels; 9,922 items; official index pinned",
        "No license detected; upstream artifact not redistributed",
        "C0--C5 pass",
    ),
    "lcrec_instruments": (
        "Released index",
        "4 levels; 9,922 items; official archive pinned",
        "No license detected; upstream artifact not redistributed",
        "C0--C5 pass",
    ),
}

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


def build_table3_source_inventory() -> list[dict[str, str]]:
    _, rows = read_csv(ROOT / "docs" / "reproducibility" / "sidscope_source_license_config_inventory.csv")
    by_route = {row["route_id"]: row for row in rows}
    output: list[dict[str, str]] = []
    for route_id, values in INVENTORY_PROJECTION.items():
        row = by_route.get(route_id)
        if row is None:
            raise RuntimeError(f"Source inventory is missing {route_id}")
        derivation, configuration, reuse_boundary, conformance = values
        output.append(
            {
                "artifact_route": row["paper_label"],
                "derivation": derivation,
                "configuration_identity": configuration,
                "reuse_boundary": reuse_boundary,
                "conformance_evidence": conformance,
                "source_evidence": "docs/reproducibility/sidscope_source_license_config_inventory.csv",
            }
        )
    return output


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
    _, rows = read_csv(ROOT / "docs" / "reproducibility" / "table2_musical_diagnostic.csv")
    labels = {
        "GRID-style ft": ("Stress/reference rows", "GRID-like stress"),
        "GRID-style cap": ("Stress/reference rows", "GRID-like capacity"),
        "RQ-min ref": ("Stress/reference rows", "RQ-min reference"),
        "ReSID": ("Source-traced named rows", "ReSID"),
        "Cat-prefix": ("Interpretation controls", "Category-prefix control"),
        "Pop-balanced": ("Interpretation controls", "Popularity-balanced control"),
        "Hash-collide": ("Interpretation controls", "Hash-collision control"),
    }
    by_artifact = {row["artifact"]: row for row in rows}
    output: list[dict[str, str]] = []
    for source_label in labels:
        row = by_artifact.get(source_label)
        if row is None:
            raise RuntimeError(f"Diagnostic snapshot is missing {source_label}")
        group, paper_label = labels[source_label]
        output.append(
            {
                "group": group,
                "artifact": paper_label,
                "unique_sids": row["unique_sids"],
                "d2_aliasing_rate": f"{float(row['d2_aliasing_rate']):.3f}",
                "d3_l1_weighted": f"{float(row['d3_l1_weighted']):.3f}",
                "source_evidence": "docs/reproducibility/table2_musical_diagnostic.csv",
            }
        )
    return output


def build_table8_resot_walkthrough() -> list[dict[str, str]]:
    record = read_json(ROOT / "docs" / "reproducibility" / "resot_resource_walkthrough.json")
    diagnostic = record["diagnostic_snapshot"]
    if not isinstance(diagnostic, dict):
        raise RuntimeError("ReSOT walkthrough lacks a diagnostic snapshot")
    items = int(diagnostic["items"])
    interactions = int(diagnostic["interactions"])
    d3 = float(diagnostic["d3_depth1_weighted_collab_recall"])
    rows = [
        {
            "stage": "Discover",
            "question": "Does the release contain item-level SIDs?",
            "evidence": f"{items:,} four-level text-index rows in the upstream archive",
            "decision": "Continue; do not redistribute archive",
            "source_evidence": "docs/reproducibility/resot_resource_walkthrough.json",
        },
        {
            "stage": "Normalize",
            "question": "Do artifact IDs join metadata and interactions?",
            "evidence": f"{items:,}/{items:,}/{interactions:,} normalized rows; complete joins",
            "decision": "Run conformance and diagnostics",
            "source_evidence": "docs/reproducibility/resot_resource_walkthrough.json",
        },
        {
            "stage": "Inspect",
            "question": "Is the route coherent and diagnostically executable?",
            "evidence": f"C0--C5 pass; D2=0; D3@1={d3:.4f}",
            "decision": "Addressable row; prefix alignment remains modest",
            "source_evidence": "docs/reproducibility/conformance/resot_instruments_report.json",
        },
        {
            "stage": "Promote",
            "question": "May it count as named artifact evidence?",
            "evidence": "Matrix refresh recomputes D1--D5, exposure, and uncertainty",
            "decision": "Admit released-archive row",
            "source_evidence": "docs/reproducibility/resot_resource_walkthrough.json",
        },
        {
            "stage": "Reject invalid",
            "question": "Does a contradictory export slip through?",
            "evidence": "Public fixture has full SID inconsistent with its level columns",
            "decision": "Stop at C1; do not promote",
            "source_evidence": "examples/conformance_failure_fixture/conformance_report.json",
        },
    ]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    for output_name, source_name in COPIED_TABLES.items():
        fields, rows = read_csv(SOURCE_DIR / source_name)
        write_csv(args.output_dir / output_name, fields, rows)
    write_csv(args.output_dir / "table3_source_inventory.csv", TABLE3_FIELDS, build_table3_source_inventory())
    write_csv(args.output_dir / "table4_adapter_conformance.csv", TABLE4_FIELDS, build_table4_adapter_conformance())
    write_csv(args.output_dir / "table5_diagnostic_profile.csv", TABLE5_FIELDS, build_table5_diagnostic_profile())
    write_csv(args.output_dir / "table8_resot_walkthrough.csv", TABLE8_FIELDS, build_table8_resot_walkthrough())
    print(f"Rebuilt {len(COPIED_TABLES) + 4} SIDScope manuscript tables in {args.output_dir}")


if __name__ == "__main__":
    main()
