#!/usr/bin/env python3
"""Build the ReSOT intake-to-promotion resource-use walkthrough."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = ROOT / "docs/reproducibility/resot_resource_walkthrough.json"
DEFAULT_OUTPUT_MD = ROOT / "docs/RESOT_RESOURCE_WALKTHROUGH.md"
DEFAULT_SOURCE_BUNDLE = ROOT / "docs/reproducibility/resot_walkthrough_sources.json"
DEFAULT_CONTROL = ROOT / "docs/reproducibility/resot_instruments_category_control.json"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _inventory_row(path: Path, route_id: str) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        matches = [row for row in csv.DictReader(handle) if row["route_id"] == route_id]
    if len(matches) != 1:
        raise ValueError(f"expected one inventory row for {route_id}, found {len(matches)}")
    return matches[0]


def _public_evidence(root: Path, stage: dict[str, Any]) -> str:
    raw_path = str(stage.get("public_record", ""))
    if not raw_path:
        raise ValueError("walkthrough stage lacks a public evidence record")
    path = root / raw_path
    if not path.is_file():
        raise FileNotFoundError(f"missing public walkthrough evidence: {raw_path}")
    return raw_path


def build_walkthrough(root: Path, source_bundle: Path | None = None) -> dict[str, Any]:
    inventory = _inventory_row(
        root / "docs/reproducibility/sidscope_source_license_config_inventory.csv",
        "resot_instruments",
    )
    sources = _load_json(source_bundle or root / "docs/reproducibility/resot_walkthrough_sources.json")
    archive = sources["archive"]
    intake = sources["intake"]
    promotion = sources["promotion"]
    conformance = _load_json(root / "docs/reproducibility/conformance/resot_instruments_report.json")
    failure = _load_json(root / "examples/conformance_failure_fixture/conformance_report.json")
    control = _load_json(root / "docs/reproducibility/resot_instruments_category_control.json")

    if conformance.get("status") != "pass" or conformance.get("failed_levels"):
        raise ValueError("ReSOT conformance report must pass C0-C5")
    if failure.get("status") != "fail" or failure.get("failed_levels") != ["C1"]:
        raise ValueError("failure fixture must fail exactly C1")
    if sources.get("route_id") != "resot_instruments":
        raise ValueError("walkthrough source bundle route does not match ReSOT inventory")
    if inventory["route_id"] != sources["route_id"]:
        raise ValueError("walkthrough source bundle does not match inventory route")
    if archive.get("route_id") != sources["route_id"] or archive.get("dataset") != inventory["dataset"]:
        raise ValueError("archive stage does not match inventory route and dataset")
    if archive.get("artifact_name") != inventory["artifact_name"]:
        raise ValueError("archive artifact does not match inventory")
    if int(archive.get("json_rows", -1)) != int(inventory["item_count"]):
        raise ValueError("archive item count does not match inventory")
    if intake.get("route_id") != sources["route_id"] or intake.get("dataset") != inventory["dataset"]:
        raise ValueError("intake stage does not match inventory route and dataset")
    if int(intake.get("sid_rows", -1)) != int(inventory["item_count"]):
        raise ValueError("intake item count does not match inventory")
    if promotion.get("route_id") != sources["route_id"]:
        raise ValueError("promotion stage does not match walkthrough route")
    if promotion.get("status") != "PASS_MATRIX_PROMOTED":
        raise ValueError("ReSOT matrix-promotion record is not closed")
    manifest_path = root / str(conformance.get("manifest", ""))
    manifest = _load_json(manifest_path)
    if conformance.get("artifact_id") != manifest.get("artifact_id"):
        raise ValueError("conformance report artifact does not match manifest")
    if manifest.get("promotion", {}).get("route_id") != sources["route_id"]:
        raise ValueError("conformance promotion does not match walkthrough route")
    c5 = next((check for check in conformance.get("checks", []) if check.get("level") == "C5"), None)
    if not c5 or c5.get("details", {}).get("route_id") != sources["route_id"]:
        raise ValueError("conformance C5 does not bind the walkthrough route")
    c1 = next((check for check in conformance.get("checks", []) if check.get("level") == "C1"), None)
    c3 = next((check for check in conformance.get("checks", []) if check.get("level") == "C3"), None)
    smoke = (c3 or {}).get("details", {}).get("metric_smoke_summary", [])
    if not c1 or len(smoke) != 1:
        raise ValueError("conformance report lacks one C1/C3 ReSOT diagnostic record")
    c1_tables = c1.get("details", {}).get("tables", {})
    c3_row = smoke[0]
    exact_pairs = {
        "sid_rows": (
            intake.get("sid_rows"),
            c1_tables.get("sid_assignments", {}).get("rows"),
        ),
        "metadata_rows": (
            intake.get("metadata_rows"),
            c1_tables.get("item_metadata", {}).get("rows"),
        ),
        "sid_length": (intake.get("sid_length"), c3_row.get("sid_length")),
        "unique_sid": (intake.get("unique_sid"), c3_row.get("unique_sid")),
        "prefix_counts": (intake.get("prefix_counts"), c3_row.get("prefix_counts")),
        "interaction_rows": (
            intake.get("interaction_rows"),
            c1_tables.get("interactions", {}).get("rows"),
        ),
    }
    for name, (observed, expected) in exact_pairs.items():
        if observed != expected:
            raise ValueError(f"walkthrough {name} does not match conformance report")
    float_pairs = {
        "full_collision_rate": (intake.get("full_collision_rate"), c3_row.get("full_collision_rate")),
        "d3_depth1_weighted_collab_recall": (
            intake.get("d3_depth1_weighted_collab_recall"),
            c3_row.get("d3_depth1_weighted_collab_recall"),
        ),
    }
    for name, (observed, expected) in float_pairs.items():
        if observed is None or expected is None or abs(float(observed) - float(expected)) > 1e-12:
            raise ValueError(f"walkthrough {name} does not match conformance report")
    if control.get("status") != "pass" or control.get("dataset") != inventory["dataset"]:
        raise ValueError("ReSOT same-dataset control is missing or bound to another dataset")
    control_source = control.get("source_artifact", {})
    control_row = control.get("category_prefix_control", {})
    if abs(float(control_source.get("d3_depth1_weighted_collab_recall")) - float(intake["d3_depth1_weighted_collab_recall"])) > 1e-12:
        raise ValueError("ReSOT same-dataset control is not bound to the walkthrough source artifact")
    source_profile = [
        float(row["weighted_collab_prefix_recall"])
        for row in control_source.get("d3_by_depth", [])
    ]
    control_profile = [
        float(row["weighted_collab_prefix_recall"])
        for row in control_row.get("d3_by_depth", [])
    ]
    if len(source_profile) != int(intake["sid_length"]) or len(control_profile) != int(intake["sid_length"]):
        raise ValueError("ReSOT same-dataset control lacks the declared depth profile")

    return {
        "schema": "sidscope.resot_resource_walkthrough.v1",
        "status": "pass",
        "route_id": "resot_instruments",
        "paper_label": inventory["paper_label"],
        "source_boundary": {
            "source_url": inventory["source_url"],
            "source_revision": inventory["source_revision"],
            "artifact_name": inventory["artifact_name"],
            "retrieval_record": inventory["configuration"],
            "license_status": inventory["license_status"],
            "redistribution_policy": inventory["redistribution_policy"],
        },
        "stages": [
            {
                "stage": "discover",
                "question": "Does the upstream release expose an item-to-SID artifact?",
                "evidence": _public_evidence(root, archive),
                "historical_record_id": archive["historical_record_id"],
                "outcome": f"{archive['json_rows']} four-level text-index rows found in the released archive.",
            },
            {
                "stage": "normalize",
                "question": "Can the release be represented by the SIDScope table contract?",
                "evidence": _public_evidence(root, intake),
                "historical_record_id": intake["historical_record_id"],
                "outcome": (
                    f"{intake['sid_rows']} SID rows, "
                    f"{intake['metadata_rows']} metadata rows, and "
                    f"{intake['interaction_rows']} interaction rows normalized."
                ),
            },
            {
                "stage": "inspect",
                "question": "Do joins and bounded D1-D5 diagnostics execute?",
                "evidence": "docs/reproducibility/conformance/resot_instruments_report.json",
                "outcome": (
                    f"C0-C5 pass; collision rate {intake['full_collision_rate']:.3f}, "
                    "weighted D3 at depths 1-3 "
                    f"{source_profile[0]:.4f}/{source_profile[1]:.4f}/{source_profile[2]:.4f} versus "
                    f"{control_profile[0]:.4f}/{control_profile[1]:.4f}/{control_profile[2]:.4f} for the "
                    "same-dataset category-prefix control."
                ),
            },
            {
                "stage": "promote",
                "question": "May the route enter the paper-facing comparison matrix?",
                "evidence": _public_evidence(root, promotion),
                "historical_record_id": promotion["historical_record_id"],
                "outcome": (
                    f"Promoted after matrix refresh; effective artifact n={promotion['effective_artifact_n']} "
                    f"and artifact-depth n={promotion['effective_artifact_depth_n']}."
                ),
            },
            {
                "stage": "reject-invalid",
                "question": "Does the contract reject an internally inconsistent SID export?",
                "evidence": "examples/conformance_failure_fixture/conformance_report.json",
                "outcome": "The public fixture fails C1 only because sid disagrees with sid_level_* columns.",
            },
        ],
        "diagnostic_snapshot": {
            "items": intake["sid_rows"],
            "interactions": intake["interaction_rows"],
            "sid_depth": intake["sid_length"],
            "unique_full_sids": intake["unique_sid"],
            "full_collision_rate": intake["full_collision_rate"],
            "d3_depth1_weighted_collab_recall": intake["d3_depth1_weighted_collab_recall"],
            "d3_weighted_by_depth": source_profile,
            "same_dataset_category_control_d3": control_row["d3_depth1_weighted_collab_recall"],
            "same_dataset_category_control_d3_by_depth": control_profile,
            "same_dataset_control_record": "docs/reproducibility/resot_instruments_category_control.json",
            "prefix_counts": intake["prefix_counts"],
        },
        "decision": {
            "paper_counted": True,
            "reason": "The released archive route passes source, schema, join, diagnostic, provenance, and promotion checks.",
            "claim_boundary": [
                "This is a released text-index artifact intake and matrix row.",
                "It is not trained-generator evidence or coverage of every ReSOT branch.",
                "The upstream archive is not redistributed because no upstream license was detected.",
            ],
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    source = payload["source_boundary"]
    diagnostic = payload["diagnostic_snapshot"]
    lines = [
        "# ReSOT Resource Walkthrough",
        "",
        "This walkthrough follows one released tokenizer artifact from source discovery to a paper-facing SIDScope row. It also includes an invalid public fixture to show that promotion is conditional rather than automatic.",
        "",
        "## Source Boundary",
        "",
        f"- Route: `{payload['paper_label']}`",
        f"- Revision: `{source['source_revision']}`",
        f"- Artifact: `{source['artifact_name']}`",
        f"- License status: `{source['license_status']}`",
        f"- Redistribution: `{source['redistribution_policy']}`",
        "",
        "## Intake-to-Promotion Record",
        "",
        "| Stage | Question | Recorded outcome |",
        "| --- | --- | --- |",
    ]
    for stage in payload["stages"]:
        lines.append(f"| {stage['stage']} | {stage['question']} | {stage['outcome']} |")
    lines.extend(
        [
            "",
            "## Diagnostic Snapshot",
            "",
            f"The normalized row contains {diagnostic['items']:,} items and {diagnostic['interactions']:,} interactions. Its {diagnostic['sid_depth']}-level mapping has {diagnostic['unique_full_sids']:,} unique full SIDs, full-code collision rate {diagnostic['full_collision_rate']:.3f}, and prefix counts `{diagnostic['prefix_counts']}`. Weighted D3 at depths 1-3 is "
            + "/".join(f"{value:.4f}" for value in diagnostic["d3_weighted_by_depth"][:3])
            + "; the deterministic same-dataset category-prefix control reaches "
            + "/".join(f"{value:.4f}" for value in diagnostic["same_dataset_category_control_d3_by_depth"][:3])
            + " under the same bounded protocol. Both mappings reach zero at the item-unique fourth level.",
            "",
            "## Decision Boundary",
            "",
        ]
    )
    lines.extend(f"- {boundary}" for boundary in payload["decision"]["claim_boundary"])
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-bundle", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_walkthrough(args.root.resolve(), args.source_bundle.resolve())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "pass", "output_json": str(args.output_json), "output_md": str(args.output_md)}))


if __name__ == "__main__":
    main()
