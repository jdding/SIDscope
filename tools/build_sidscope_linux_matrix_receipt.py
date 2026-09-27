#!/usr/bin/env python3
"""Assemble and validate the Linux matrix receipt from executed cell results.

The operator runs each container cell with the documented docker commands and
records one JSON result file per cell plus the combined log; this tool never
executes anything. It validates the shape, the per-cell source identity, the
four CPython versions and every log digest, then emits the receipt that the
delivery summary consumes.
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
from tools.sidscope_delivery_summary import short_source

RECEIPT_FORMAT = "sidscope.linux_matrix_receipt.v1"
EXPECTED_PYTHONS = ("3.9", "3.10", "3.11", "3.12")
CELL_FIELDS = {"python", "image", "os", "status", "exit_code", "head",
               "source_identity_checked", "log"}


class MatrixReceiptError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def build(output: Path, cells_dir: Path) -> dict:
    source = short_source()
    if not source["clean"]:
        raise MatrixReceiptError("dirty_candidate", "the Linux matrix receipt requires a clean candidate")
    cells = []
    for version in EXPECTED_PYTHONS:
        path = cells_dir / f"cell-{version}.json"
        if not path.is_file():
            raise MatrixReceiptError("missing_matrix_cell", version)
        cell = json.loads(path.read_text(encoding="utf-8"))
        if not CELL_FIELDS <= set(cell) or cell.get("python") != version:
            raise MatrixReceiptError("invalid_matrix_cell", version)
        if cell["head"] != source["head"]:
            raise MatrixReceiptError("stale_matrix_head", f"{version}: {cell['head']} != {source['head']}")
        if not cell["source_identity_checked"]:
            raise MatrixReceiptError("matrix_identity_unchecked", version)
        if cell["status"] != "pass" or cell["exit_code"] != 0:
            raise MatrixReceiptError("failed_matrix_cell", version)
        log_path = cells_dir / cell["log"]["path"]
        if not log_path.is_file() or hashlib.sha256(log_path.read_bytes()).hexdigest() != cell["log"]["sha256"]:
            raise MatrixReceiptError("matrix_log_integrity", version)
        cells.append(cell)
    receipt = with_content_sha256({
        "format": RECEIPT_FORMAT, "source": source, "os_family": "Linux",
        "invocation_digest": hashlib.sha256(canonical_json_bytes(EXPECTED_PYTHONS)).hexdigest(),
        "cells": cells,
    })
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise MatrixReceiptError("receipt_output_invalid", "write the receipt beside the evidence")
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
    except MatrixReceiptError as error:
        print(json.dumps({"status": "fail", "code": error.code, "detail": error.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
