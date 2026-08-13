#!/usr/bin/env python3
"""Rebuild and compare all eight SIDScope manuscript table snapshots."""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DIR = ROOT / "docs" / "reproducibility" / "paper_tables"
EXPECTED = (
    "table1_resource_delta.csv",
    "table2_artifact_coverage.csv",
    "table4_adapter_conformance.csv",
    "table5_diagnostic_profile.csv",
    "table6_evidence_ladder.csv",
    "table8_resot_walkthrough.csv",
    "table9_resource_contract.csv",
    "table10_g20_trained_trace.csv",
)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if not fields or not rows:
        raise RuntimeError(f"Empty paper table: {path}")
    return fields, rows


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sidscope-paper-tables-") as tmp:
        output_dir = Path(tmp)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build_sidscope_paper_tables.py"),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            check=True,
        )
        total_rows = 0
        for name in EXPECTED:
            expected_fields, expected_rows = read_rows(EXPECTED_DIR / name)
            observed_fields, observed_rows = read_rows(output_dir / name)
            if observed_fields != expected_fields:
                raise RuntimeError(f"{name} header drift: {observed_fields} != {expected_fields}")
            if observed_rows != expected_rows:
                raise RuntimeError(f"{name} row drift after deterministic rebuild")
            total_rows += len(observed_rows)

    print("SIDScope paper-table regeneration verification passed.")
    print(f"Verified {len(EXPECTED)} tables and {total_rows} manuscript-facing rows.")


if __name__ == "__main__":
    main()
