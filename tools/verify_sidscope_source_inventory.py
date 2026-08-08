#!/usr/bin/env python3
"""Verify the SIDScope source, license, and configuration inventory."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
DEFAULT_INVENTORY = ROOT / "docs/reproducibility/sidscope_source_license_config_inventory.csv"
DEFAULT_COVERAGE = ROOT / "docs/reproducibility/paper_table_sources/table2_artifact_coverage_source.csv"
ROUTE_SUMMARY = ROOT / "docs/reproducibility/source_route_evidence_summary.json"

EXPECTED_ROUTE_IDS = {
    "resid_musical_snapshot",
    "resid_gaoq_video",
    "grid_p5_beauty",
    "card_p5_beauty",
    "diger_beauty",
    "resot_instruments",
    "letter_instruments",
    "lcrec_instruments",
}

REQUIRED_COLUMNS = {
    "route_id",
    "paper_label",
    "method_family",
    "dataset",
    "item_count",
    "derivation",
    "evidence_role",
    "source_url",
    "source_revision",
    "artifact_name",
    "configuration",
    "sid_depth",
    "license_status",
    "license_identifier",
    "redistribution_policy",
    "source_evidence",
    "conformance_status",
    "conformance_evidence",
    "last_verified",
}

ALLOWED_LICENSE_STATUSES = {
    "licensed",
    "restricted_source_license",
    "source_licensed_artifact_boundary_unresolved",
    "no_license_detected",
}

ALLOWED_CONFORMANCE_STATUSES = {
    "c0_c5_pass",
    "legacy_preflight_and_metrics_evidence",
    "auditable_snapshot_not_fully_regenerable",
}

ALLOWED_EVIDENCE_ROLES = {
    "source_traced_named_route",
    "released_index_route",
    "official_code_derived_route",
    "tracked_snapshot",
}

ALLOWED_REDISTRIBUTION_POLICIES = {
    "licensed": {"summary_and_derived_tables"},
    "restricted_source_license": {"summary_and_derived_tables_no_upstream_data"},
    "source_licensed_artifact_boundary_unresolved": {"summary_only"},
    "no_license_detected": {
        "summary_only",
        "summary_only_no_archive_redistribution",
        "summary_only_no_upstream_artifact_redistribution",
    },
}


def _package_file(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"path must be package-relative: {raw_path}")
    resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes package root: {raw_path}") from exc
    return resolved


def _verify_c0_c5_report(
    row: dict[str, str], report_path: Path, inventory_path: Path
) -> str | None:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            return "C0-C5 report must be a JSON object"
    except (OSError, json.JSONDecodeError) as exc:
        return f"cannot read C0-C5 report: {exc}"
    expected_levels = ["C0", "C1", "C2", "C3", "C4", "C5"]
    checks = report.get("checks")
    if not isinstance(checks, list) or not all(isinstance(check, dict) for check in checks):
        return "C0-C5 report checks must be a list of objects"
    observed_levels = [check.get("level") for check in checks]
    if report.get("schema") != "sidscope.adapter_conformance_report.v1":
        return "C0-C5 report schema mismatch"
    if report.get("status") != "pass" or report.get("failed_levels") != []:
        return "C0-C5 report does not pass"
    if observed_levels != expected_levels or any(check.get("status") != "pass" for check in checks):
        return "C0-C5 report has incomplete or failing levels"
    if report.get("paper_label") != row["paper_label"]:
        return "C0-C5 report paper label does not match inventory"
    try:
        manifest_path = _package_file(str(report["manifest"]))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return f"cannot bind C0-C5 report to manifest: {exc}"
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "sidscope.adapter_manifest.v1":
        return "C0-C5 manifest schema mismatch"
    if report.get("artifact_id") != manifest.get("artifact_id"):
        return "C0-C5 report artifact ID does not match manifest"
    if manifest.get("paper_label") != row["paper_label"]:
        return "C0-C5 manifest paper label does not match inventory"
    promotion = manifest.get("promotion", {})
    if not isinstance(promotion, dict):
        return "C0-C5 manifest promotion must be an object"
    if promotion.get("route_id") != row["route_id"]:
        return "C0-C5 manifest route ID does not match inventory"
    if promotion.get("evidence_role") != row["evidence_role"]:
        return "C0-C5 manifest evidence role does not match inventory"
    if promotion.get("conformance_status") != row["conformance_status"]:
        return "C0-C5 manifest conformance status does not match inventory"
    if promotion.get("conformance_evidence") != row["conformance_evidence"]:
        return "C0-C5 manifest conformance evidence does not match inventory"
    c4 = next(check for check in checks if check["level"] == "C4")
    report_hashes = c4.get("details", {}).get("input_sha256")
    if report_hashes != manifest.get("input_sha256"):
        return "C0-C5 report hashes do not match manifest"
    c5 = next(check for check in checks if check["level"] == "C5")
    c5_details = c5.get("details", {})
    if c5_details.get("route_id") != row["route_id"] or c5_details.get("inventory_match") is not True:
        return "C0-C5 report promotion does not match inventory route"

    try:
        input_paths = [_package_file(str(path)) for path in manifest.get("inputs", {}).values()]
    except ValueError as exc:
        return f"C0-C5 manifest input path invalid: {exc}"
    if input_paths and all(path.is_file() for path in input_paths):
        from sidinspector.conformance import redact_private_input_paths, run_conformance

        regenerated = run_conformance(manifest_path, root=ROOT, inventory_path=inventory_path)
        if redact_private_input_paths(regenerated) != report:
            return "C0-C5 report differs from regeneration over current inputs"
    return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"inventory missing columns: {sorted(missing)}")
        return list(reader)


def _route_summaries(path: Path) -> dict[str, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "sidscope.source_route_evidence_summary.v1":
        raise ValueError("source-route evidence summary schema mismatch")
    routes = value.get("routes")
    if not isinstance(routes, list) or not all(isinstance(route, dict) for route in routes):
        raise ValueError("source-route evidence summary routes must be objects")
    result = {str(route.get("route_id")): route for route in routes}
    if len(result) != len(routes):
        raise ValueError("source-route evidence summary route IDs must be unique")
    return result


def _coverage_rows(path: Path) -> dict[str, int]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        result: dict[str, int] = {}
        for row in rows:
            if row["group"] == "Stress/reference and controls":
                continue
            result[row["artifact_catalog"]] = int(row["artifact_local_items"].replace(",", ""))
        return result


def verify_inventory(inventory_path: Path, coverage_path: Path) -> dict[str, Any]:
    rows = _read_csv(inventory_path)
    failures: list[str] = []
    try:
        route_summaries = _route_summaries(ROUTE_SUMMARY)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        route_summaries = {}
        failures.append(f"cannot load source-route evidence summary: {exc}")
    route_ids = [row["route_id"] for row in rows]

    if len(route_ids) != len(set(route_ids)):
        failures.append("route_id values must be unique")
    if set(route_ids) != EXPECTED_ROUTE_IDS:
        failures.append(
            f"route set mismatch: expected={sorted(EXPECTED_ROUTE_IDS)} observed={sorted(set(route_ids))}"
        )

    coverage = _coverage_rows(coverage_path)
    inventory_labels: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=2):
        for column in REQUIRED_COLUMNS:
            if not row[column].strip():
                failures.append(f"row {row_number} has blank {column}")

        try:
            item_count = int(row["item_count"])
            sid_depth = int(row["sid_depth"])
        except ValueError:
            failures.append(f"row {row_number} item_count and sid_depth must be integers")
            continue
        if item_count <= 0 or sid_depth <= 0:
            failures.append(f"row {row_number} item_count and sid_depth must be positive")

        inventory_labels[row["paper_label"]] = item_count
        if not row["source_url"].startswith("https://"):
            failures.append(f"row {row_number} source_url must use https")
        if row["license_status"] not in ALLOWED_LICENSE_STATUSES:
            failures.append(f"row {row_number} has unsupported license_status={row['license_status']!r}")
        if row["conformance_status"] not in ALLOWED_CONFORMANCE_STATUSES:
            failures.append(
                f"row {row_number} has unsupported conformance_status={row['conformance_status']!r}"
            )
        if row["evidence_role"] not in ALLOWED_EVIDENCE_ROLES:
            failures.append(f"row {row_number} has unsupported evidence_role={row['evidence_role']!r}")
        if row["license_status"] == "no_license_detected" and not row["license_identifier"].startswith(
            "NOASSERTION"
        ):
            failures.append(f"row {row_number} no-license status must use NOASSERTION")
        allowed_policies = ALLOWED_REDISTRIBUTION_POLICIES.get(row["license_status"], set())
        if row["redistribution_policy"] not in allowed_policies:
            failures.append(
                f"row {row_number} redistribution_policy={row['redistribution_policy']!r} is incompatible "
                f"with license_status={row['license_status']!r}"
            )

        summary = route_summaries.get(row["route_id"])
        if summary is None:
            failures.append(f"row {row_number} missing route-evidence summary")
        elif (
            summary.get("source_revision") != row["source_revision"]
            or int(summary.get("item_count", -1)) != item_count
            or int(summary.get("sid_depth", -1)) != sid_depth
            or summary.get("evidence_status") != row["conformance_status"]
        ):
            failures.append(f"row {row_number} route-evidence summary does not match inventory")

        for evidence in row["source_evidence"].split(";"):
            try:
                evidence_path = _package_file(evidence)
            except ValueError as exc:
                failures.append(f"row {row_number} source evidence: {exc}")
                continue
            if not evidence_path.is_file():
                failures.append(f"row {row_number} evidence path does not exist: {evidence}")

        try:
            conformance_path = _package_file(row["conformance_evidence"])
        except ValueError as exc:
            failures.append(f"row {row_number} conformance evidence: {exc}")
            continue
        if not conformance_path.is_file():
            failures.append(f"row {row_number} conformance evidence does not exist: {row['conformance_evidence']}")
        elif row["conformance_status"] == "c0_c5_pass":
            report_failure = _verify_c0_c5_report(row, conformance_path, inventory_path)
            if report_failure:
                failures.append(f"row {row_number} {report_failure}")

    if inventory_labels != coverage:
        failures.append(f"paper-facing inventory does not match Table 2: inventory={inventory_labels} coverage={coverage}")

    def report_path(path: Path) -> str:
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    return {
        "schema": "sidscope.source_license_config_inventory.verification.v1",
        "status": "pass" if not failures else "fail",
        "inventory": report_path(inventory_path),
        "coverage_source": report_path(coverage_path),
        "route_count": len(rows),
        "license_status_counts": {
            status: sum(row["license_status"] == status for row in rows)
            for status in sorted(ALLOWED_LICENSE_STATUSES)
        },
        "conformance_status_counts": {
            status: sum(row["conformance_status"] == status for row in rows)
            for status in sorted(ALLOWED_CONFORMANCE_STATUSES)
        },
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_inventory(args.inventory.resolve(), args.coverage.resolve())
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
