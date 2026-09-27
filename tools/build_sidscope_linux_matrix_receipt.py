#!/usr/bin/env python3
"""Assemble and validate the Linux matrix receipt from executed cell results.

The operator runs each container cell with the documented docker commands and
records one structured cell JSON plus the combined log per version; a cell
records the frozen image, the real interpreter and OS, a content-manifest
digest of the mounted tree, and one entry per required step with its exit code,
pytest passed-count and log marker. This tool executes nothing. It validates
all of the above against the clean candidate tree — image, OS, interpreter,
manifest digest, source identity, every required step with exit 0, every log
digest and marker — then writes the receipt the delivery summary consumes.
Existing outputs are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_json_bytes, with_content_sha256
from tools.sidscope_delivery_summary import (
    LINUX_FORMAT,
    LINUX_REQUIRED_STEPS,
    DeliverySummaryError,
    short_source,
)

IMAGES = {"3.9": "python:3.9-slim", "3.10": "python:3.10-slim",
          "3.11": "python:3.11-slim", "3.12": "python:3.12-slim"}
CELL_FIELDS = {"python", "image", "os", "arch", "interpreter", "source_manifest_sha256",
               "source_check", "status", "exit_code", "head", "steps", "log"}
STEP_FIELDS = {"name", "exit_code", "passed_count", "log_marker"}


def _tree_manifest_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def build(output: Path, cells_dir: Path) -> dict:
    source = short_source()
    if not source["clean"]:
        raise DeliverySummaryError("dirty_candidate", "the Linux matrix receipt requires a clean candidate")
    expected_manifest = _tree_manifest_digest(ROOT)
    cells = []
    for version in ("3.9", "3.10", "3.11", "3.12"):
        path = cells_dir / f"cell-{version}.json"
        if not path.is_file():
            raise DeliverySummaryError("missing_matrix_cell", version)
        cell = json.loads(path.read_text(encoding="utf-8"))
        if not CELL_FIELDS <= set(cell) or cell.get("python") != version:
            raise DeliverySummaryError("invalid_matrix_cell", version)
        if cell.get("image") != IMAGES[version]:
            raise DeliverySummaryError("invalid_matrix_cell", f"{version}: image {cell.get('image')!r}")
        if not str(cell.get("os", "")).startswith("Linux"):
            raise DeliverySummaryError("invalid_matrix_cell", f"{version}: os={cell.get('os')!r} is not Linux")
        if cell.get("source_manifest_sha256") != expected_manifest:
            raise DeliverySummaryError("stale_matrix_head",
                                       f"{version}: container tree manifest does not match the clean candidate")
        source_check = cell.get("source_check") or {}
        if (source_check.get("head") != source["head"]
                or source_check.get("public_snapshot_digest") != source["public_snapshot_digest"]
                or source_check.get("clean") is not True):
            raise DeliverySummaryError("matrix_identity_unchecked", version)
        if cell.get("status") != "pass" or cell.get("exit_code") != 0:
            raise DeliverySummaryError("failed_matrix_cell", version)
        steps = cell.get("steps") or []
        names = [step.get("name") for step in steps]
        if sorted(names) != sorted(LINUX_REQUIRED_STEPS):
            raise DeliverySummaryError("invalid_matrix_cell", f"{version}: steps {names}")
        for step in steps:
            if not STEP_FIELDS <= set(step):
                raise DeliverySummaryError("invalid_matrix_cell", f"{version}: step fields")
            if step["exit_code"] != 0:
                raise DeliverySummaryError("failed_matrix_cell", f"{version}: step {step['name']}")
            if step["name"] == "pytest" and not step.get("passed_count"):
                raise DeliverySummaryError("invalid_matrix_cell", f"{version}: pytest passed_count")
        log_relative = (cell.get("log") or {}).get("path", "")
        log_path = cells_dir / log_relative
        if not log_path.is_file() or hashlib.sha256(log_path.read_bytes()).hexdigest() != cell["log"]["sha256"]:
            raise DeliverySummaryError("matrix_log_integrity", version)
        combined = log_path.read_text(errors="replace")
        for step in steps:
            marker = step.get("log_marker") or ""
            if not marker or marker not in combined:
                raise DeliverySummaryError("matrix_log_integrity", f"{version}: marker for {step['name']}")
        cells.append(cell)
    receipt = with_content_sha256({
        "format": LINUX_FORMAT, "source": source, "os_family": "Linux",
        "invocation_digest": hashlib.sha256(canonical_json_bytes(sorted(IMAGES))).hexdigest(),
        "cells": cells,
    })
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        if ".local_artifacts" not in output.parts:
            raise DeliverySummaryError("receipt_output_invalid", "write the receipt beside the evidence")
    if output.exists() or output.is_symlink():
        raise DeliverySummaryError("receipt_output_exists", f"{output} already exists; use a new attempt path")
    output.write_bytes(canonical_json_bytes(receipt) + b"\n")
    return {"status": "pass", "receipt_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "cells": [cell["python"] for cell in cells]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.output, args.cells_dir)
    except DeliverySummaryError as error:
        print(json.dumps({"status": "fail", "code": error.code, "detail": error.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
