#!/usr/bin/env python3
"""Verify the frozen deidentified D7 labeled-trace release."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / "docs/reproducibility/d7_labeled_trace_rows.csv.gz"
DEFAULT_METADATA = ROOT / "docs/reproducibility/d7_labeled_trace_release.json"
FORBIDDEN_FIELDS = {
    "user_id",
    "target_item_id",
    "sid_path",
    "generated_code",
    "resolved_item_id",
    "resolved_item_ids",
    "score",
    "checkpoint_sha256",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(release: Path, metadata_path: Path) -> dict[str, object]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    if metadata.get("schema") != "sidscope.d7_labeled_trace_release.v1":
        failures.append("unexpected metadata schema")
    if sha256(release) != metadata.get("release_sha256"):
        failures.append("release SHA-256 mismatch")

    rows_by_case: Counter[str] = Counter()
    traces_by_case: dict[str, set[str]] = defaultdict(set)
    primary_by_case: dict[str, Counter[str]] = defaultdict(Counter)
    family_by_case: dict[str, Counter[str]] = defaultdict(Counter)
    with gzip.open(release, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if fields != metadata.get("release_fields"):
            failures.append("release field order differs from metadata")
        forbidden = FORBIDDEN_FIELDS.intersection(fields)
        if forbidden:
            failures.append(f"forbidden identifying fields present: {sorted(forbidden)}")
        for row in reader:
            case_id = row["case_id"]
            rows_by_case[case_id] += 1
            traces_by_case[case_id].add(row["trace_key"])
            primary_by_case[case_id][row["primary_failure"]] += 1
            family_by_case[case_id][row["failure_family"]] += 1

    if sum(rows_by_case.values()) != int(metadata.get("rows", -1)):
        failures.append("total row count mismatch")
    expected_cases = metadata.get("cases", {})
    for case_id, expected in expected_cases.items():
        if rows_by_case[case_id] != int(expected["rows"]):
            failures.append(f"{case_id}: row count mismatch")
        if len(traces_by_case[case_id]) != int(expected["traces"]):
            failures.append(f"{case_id}: trace count mismatch")
        if dict(sorted(primary_by_case[case_id].items())) != expected["primary_failure_counts"]:
            failures.append(f"{case_id}: primary-failure distribution mismatch")
        if dict(sorted(family_by_case[case_id].items())) != expected["failure_family_counts"]:
            failures.append(f"{case_id}: failure-family distribution mismatch")

    result = {
        "schema": "sidscope.d7_labeled_trace_release.verification.v1",
        "status": "pass" if not failures else "fail",
        "release": str(release.relative_to(ROOT)),
        "release_sha256": sha256(release),
        "rows": sum(rows_by_case.values()),
        "cases": len(rows_by_case),
        "traces": sum(len(value) for value in traces_by_case.values()),
        "failures": failures,
    }
    if failures:
        raise SystemExit(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    args = parser.parse_args()
    print(json.dumps(verify(args.release.resolve(), args.metadata.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
