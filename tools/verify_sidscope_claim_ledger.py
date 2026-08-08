#!/usr/bin/env python3
"""Verify SIDScope claim-ledger evidence boundaries for G7/G5."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "experiments" / "v1_evidence_chain" / "CLAIM_LEDGER.md"
DEFAULT_OUTPUT = ROOT / "experiments" / "v1_evidence_chain" / "runs" / "R510_sidscope_claim_ledger_verification.json"
DEFAULT_RELEASE_MANIFEST = ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"
V1_ROOT = ROOT / "experiments" / "v1_evidence_chain"

ALLOWED_STATUSES = {"supported", "partial", "missing", "avoid"}
ALLOWED_PLACEMENTS = {"main", "appendix", "future_work"}
V1_LOCAL_TOP_LEVEL = {
    "ACCEPTANCE_GATES.md",
    "CLAIM_LEDGER.md",
    "D7_PER_BEAM_TRACE_JOIN_PLAN.md",
    "G14_USAGE_DEMO_PLAN.md",
    "G7_LITE_CLAIM_PACKAGE_BOUNDARY.md",
    "GATE1_RESULT.md",
    "GRID_GATE1_BUILD_PLAN.md",
    "G20_D7_FAILURE_RICH_TRACE_PLAN.md",
    "HANDOFF.md",
    "MANIFEST.md",
    "MOCK_REVIEW_SIGIR_RESOURCE_20260610.md",
    "SCIENTIFIC_CLAIM_DEEP_DIVE_20260610.md",
    "SPEC.md",
    "V0_V1_DELTA_AND_VENUE_GATE.md",
}
FORBIDDEN_PRIVATE_PATH_PATTERNS = (
    "/Users/",
    "/Volumes/",
    "/private/",
    "root@",
    "connect.west",
    "autodl-tmp",
)
REQUIRED_BLOCKED_PHRASES = (
    "Downstream recommendation improvement",
    "Trained generator failure prediction",
    "Causal proof",
    "R138 as faithful GRID named coverage",
    "Final SIGIR-vs-TOIS venue decision before the CIKM V0 result",
)
REQUIRED_G7_FULL_REGISTRY = "docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv"
REQUIRED_G7_FULL_COLUMNS = {
    "paper_artifact_id",
    "paper_artifact_type",
    "paper_placement",
    "intended_caption_or_use",
    "claim_ids",
    "source_rows",
    "package_relative_source_paths",
    "source_sha256_or_regeneration_note",
    "evidence_level",
    "row_count_or_scope",
    "limitations",
}


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def extract_claim_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| C"):
            continue
        cells = split_markdown_row(line)
        if len(cells) != 9:
            raise RuntimeError(f"claim row should have 9 cells, got {len(cells)}: {line}")
        rows.append(
            {
                "id": cells[0],
                "claim": cells[1],
                "status": cells[2],
                "placement": cells[3],
                "evidence": cells[4],
                "command": cells[5],
                "support": cells[6],
                "limitation": cells[7],
                "v0_overlap": cells[8],
            }
        )
    if not rows:
        raise RuntimeError("no claim rows found")
    return rows


def should_resolve_backtick(value: str) -> bool:
    if any(token in value for token in ("*", "<", ">", " ")):
        return False
    suffixes = (".md", ".json", ".csv", ".py")
    if value.endswith(suffixes):
        return True
    if "/" in value and "." not in Path(value).name:
        return True
    return False


def resolve_evidence_path(value: str) -> Path | None:
    path = value.strip()
    if not should_resolve_backtick(path):
        return None
    if path.startswith("runs/"):
        return V1_ROOT / path
    if path in V1_LOCAL_TOP_LEVEL:
        return V1_ROOT / path
    if path.startswith(("gate", "scientific_deep_dive/", "archive/", "autodl/")):
        return V1_ROOT / path
    if path.startswith(("src/", "tools/", "docs/", "tests/", "examples/", "experiments/")):
        return ROOT / path
    return None


def extract_backticks(text: str) -> list[str]:
    return re.findall(r"`([^`]+)`", text)


def read_public_manifest_paths(manifest_path: Path = DEFAULT_RELEASE_MANIFEST) -> set[str]:
    if not manifest_path.exists():
        return set()
    import csv

    public_paths: set[str] = set()
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("public_package") != "yes":
                continue
            path = (row.get("path") or "").strip()
            if path:
                public_paths.add(path)
    return public_paths


def is_manifest_public_path(relative_path: str, public_paths: set[str]) -> bool:
    return any(relative_path == path or relative_path.startswith(f"{path}/") for path in public_paths)


def verify_g7_full_registry(path: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return 0, [f"canonical G9 registry has no rows: {path}"]

    missing_columns = REQUIRED_G7_FULL_COLUMNS - set(rows[0])
    if missing_columns:
        errors.append(f"canonical G9 registry missing columns: {sorted(missing_columns)}")

    placements = {row.get("paper_placement", "").strip() for row in rows}
    missing_required_placements = ALLOWED_PLACEMENTS - placements
    if missing_required_placements:
        errors.append(f"canonical G9 registry missing placements: {sorted(missing_required_placements)}")

    for index, row in enumerate(rows, start=2):
        artifact_id = row.get("paper_artifact_id", "").strip() or f"line {index}"
        placement = row.get("paper_placement", "").strip()
        if placement not in ALLOWED_PLACEMENTS:
            errors.append(f"{artifact_id} has invalid paper_placement: {placement}")
        if not row.get("claim_ids", "").strip():
            errors.append(f"{artifact_id} missing claim_ids")
        if not row.get("source_rows", "").strip():
            errors.append(f"{artifact_id} missing source_rows")
        if not row.get("limitations", "").strip():
            errors.append(f"{artifact_id} missing limitations")

        source_note = row.get("source_sha256_or_regeneration_note", "").strip()
        if "sha256=" not in source_note and "Regenerate" not in source_note:
            errors.append(f"{artifact_id} missing sha256 or regeneration note")

        raw_paths = row.get("package_relative_source_paths", "")
        for raw_path in raw_paths.split(";"):
            rel_path = raw_path.strip()
            if not rel_path:
                continue
            if rel_path.startswith("/") or ".." in Path(rel_path).parts:
                errors.append(f"{artifact_id} has non-package-relative source path: {rel_path}")
            for pattern in FORBIDDEN_PRIVATE_PATH_PATTERNS:
                if pattern in rel_path:
                    errors.append(f"{artifact_id} source path contains private token {pattern}: {rel_path}")

    return len(rows), errors


def verify_ledger(ledger_path: Path = DEFAULT_LEDGER, package_mode: bool = False) -> dict[str, Any]:
    text = ledger_path.read_text(encoding="utf-8")
    rows = extract_claim_rows(text)
    public_paths = read_public_manifest_paths()

    errors: list[str] = []
    warnings: list[str] = []
    resolved_paths: list[str] = []
    package_omitted_paths: list[str] = []
    skipped_backticks: list[str] = []

    for row in rows:
        if row["status"] not in ALLOWED_STATUSES:
            errors.append(f"{row['id']} has invalid status: {row['status']}")
        if row["placement"] not in ALLOWED_PLACEMENTS:
            errors.append(f"{row['id']} has invalid paper placement: {row['placement']}")
        if row["status"] == "avoid" and row["placement"] != "future_work":
            errors.append(f"{row['id']} avoid row must use paper placement=future_work")
        if row["status"] == "avoid" and row["evidence"] != "No supporting artifact.":
            errors.append(f"{row['id']} avoid row should not cite supporting evidence")
        if row["status"] in {"supported", "partial"} and row["limitation"].lower() in {"", "none", "n/a"}:
            warnings.append(f"{row['id']} limitation is missing")

        for value in extract_backticks(row["evidence"]):
            resolved = resolve_evidence_path(value)
            if resolved is None:
                skipped_backticks.append(value)
                continue
            if not resolved.exists():
                relative = str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(resolved)
                if package_mode and not is_manifest_public_path(relative, public_paths):
                    package_omitted_paths.append(relative)
                else:
                    errors.append(f"{row['id']} evidence path missing: {value} -> {resolved}")
            else:
                resolved_paths.append(str(resolved.relative_to(ROOT)))

    for pattern in FORBIDDEN_PRIVATE_PATH_PATTERNS:
        if pattern in text:
            errors.append(f"claim ledger contains forbidden private path/token: {pattern}")

    if REQUIRED_G7_FULL_REGISTRY not in text:
        errors.append(f"claim ledger missing canonical G9 registry path: {REQUIRED_G7_FULL_REGISTRY}")
    registry_path = ROOT / REQUIRED_G7_FULL_REGISTRY
    registry_rows = 0
    if not registry_path.is_file():
        errors.append(f"canonical G9 registry missing: {REQUIRED_G7_FULL_REGISTRY}")
    else:
        registry_rows, registry_errors = verify_g7_full_registry(registry_path)
        errors.extend(registry_errors)

    blocked_section = text.split("## Paper-Facing Claims Currently Blocked", 1)[-1]
    for phrase in REQUIRED_BLOCKED_PHRASES:
        if phrase not in blocked_section:
            errors.append(f"blocked-claims section missing phrase: {phrase}")

    c9 = next((row for row in rows if row["id"] == "C9"), None)
    if c9 is None or c9["status"] != "avoid":
        errors.append("C9 must exist and remain status=avoid")

    c10 = next((row for row in rows if row["id"] == "C10"), None)
    if c10 is None or "R509" not in c10["evidence"] or "R506" not in c10["evidence"]:
        errors.append("C10 must cite R506 archive smoke and R509 tutorial evidence")

    result = {
        "schema": "sidscope.claim_ledger_verification.v1",
        "status": "pass" if not errors else "fail",
        "ledger_path": str(ledger_path.relative_to(ROOT) if ledger_path.is_relative_to(ROOT) else ledger_path),
        "claim_rows": len(rows),
        "supported_rows": sum(1 for row in rows if row["status"] == "supported"),
        "partial_rows": sum(1 for row in rows if row["status"] == "partial"),
        "avoid_rows": sum(1 for row in rows if row["status"] == "avoid"),
        "placement_counts": {
            placement: sum(1 for row in rows if row["placement"] == placement)
            for placement in sorted(ALLOWED_PLACEMENTS)
        },
        "g7_full_registry": REQUIRED_G7_FULL_REGISTRY,
        "g7_full_registry_rows": registry_rows,
        "package_mode": package_mode,
        "package_omitted_evidence_paths": sorted(set(package_omitted_paths)),
        "resolved_evidence_paths": sorted(set(resolved_paths)),
        "skipped_backticks": sorted(set(skipped_backticks)),
        "warnings": warnings,
        "errors": errors,
        "boundary": "Verifies claim-ledger path hygiene, canonical G9 table/figure registry structure, and forbidden-claim boundaries. Local clean-extract and current public URL smoke are evidenced separately by R603/R708; final TeX claim audit remains a paper-writing gate.",
    }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify SIDScope claim-ledger evidence boundaries.")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument(
        "--package-mode",
        action="store_true",
        help=(
            "Validate claim safety from a release archive. Public-package evidence paths "
            "must still exist, while full-repository experiment records may be listed as "
            "package_omitted_evidence_paths."
        ),
    )
    parser.add_argument("--result-json", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_ledger(args.ledger.resolve(), package_mode=args.package_mode)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
