#!/usr/bin/env python3
"""Assemble the Linux matrix receipt from executed cell results.

The committed in-container entry is `tools/run_sidscope_linux_matrix_cell.sh`
(fixed commands) plus `tools/sidscope_linux_matrix_cell.py` (pure assembler);
the host loop is documented in docs/SIDSCOPE_LINUX_MATRIX_RUNBOOK.md. This
builder executes nothing. It validates every cell with the shared
`sidscope_linux_matrix_cells.validate_cell` — the identical rule the delivery
summary applies — copies each cell log next to the receipt under linux-cells/
and rewrites the receipt's log paths relative to the receipt directory, then
writes the receipt exclusively (symlinks refused). Use --print-manifest to
print the expected clean-candidate manifest for the runbook loop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_json_bytes, with_content_sha256
from tools.sidscope_delivery_summary import DeliverySummaryError, short_source
from tools.sidscope_linux_matrix_cells import (
    LINUX_FORMAT,
    LINUX_PYTHONS,
    MatrixCellError,
    cell_log_filename,
    validate_cell,
)
from tools.sidscope_source_manifest import tree_manifest_digest

# Compatibility alias for external audits that exercise the manifest rule
# through this module; the implementation lives in the shared source module.
_tree_manifest_digest = tree_manifest_digest

RECEIPT_FORMAT = LINUX_FORMAT


def _exclusive_write(path: Path, payload: bytes) -> None:
    if path.is_symlink() or path.exists():
        raise DeliverySummaryError("receipt_output_exists", f"{path} already exists; use a new attempt path")
    resolved_parent = path.resolve().parent
    if ROOT in [resolved_parent, *resolved_parent.parents] and ".local_artifacts" not in path.parts:
        raise DeliverySummaryError("receipt_output_invalid", "write under the ignored evidence area or outside the source tree")
    with path.open("xb") as handle:
        handle.write(payload)


def build(output: Path, cells_dir: Path) -> dict:
    source = short_source()
    if not source["clean"]:
        raise DeliverySummaryError("dirty_candidate", "the Linux matrix receipt requires a clean candidate")
    expected_manifest = tree_manifest_digest(ROOT)
    cells = []
    for version in LINUX_PYTHONS:
        path = cells_dir / f"cell-{version}.json"
        if not path.is_file():
            raise DeliverySummaryError("missing_matrix_cell", version)
        cell = json.loads(path.read_text(encoding="utf-8"))
        # Shared rule; log digests verified against the collected cells dir first.
        try:
            validate_cell(cell, expected_manifest=expected_manifest, head=source["head"],
                          public_snapshot_digest=source["public_snapshot_digest"], log_base=cells_dir)
        except MatrixCellError as error:
            raise DeliverySummaryError(error.code, error.detail) from error
        cells.append(cell)
    output = Path(output)
    receipt_dir = output.parent
    logs_dir = receipt_dir / "linux-cells"
    if output.is_symlink() or output.exists():
        raise DeliverySummaryError("receipt_output_exists", f"{output} already exists; use a new attempt path")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    receipt_cells = []
    for cell in cells:
        collected = cells_dir / cell["log"]["path"]
        relocated = logs_dir / cell_log_filename(cell["python"])
        if relocated.is_symlink() or relocated.exists():
            raise DeliverySummaryError("receipt_output_exists", f"{relocated} already exists")
        shutil.copyfile(collected, relocated)
        receipt_cell = dict(cell)
        receipt_cell["log"] = {"path": f"linux-cells/{cell_log_filename(cell['python'])}",
                               "sha256": hashlib.sha256(relocated.read_bytes()).hexdigest()}
        # Re-validate the relocated binding before it enters the receipt.
        validate_cell(receipt_cell, expected_manifest=expected_manifest, head=source["head"],
                      public_snapshot_digest=source["public_snapshot_digest"], log_base=receipt_dir)
        receipt_cells.append(receipt_cell)
    receipt = with_content_sha256({
        "format": RECEIPT_FORMAT, "source": source, "os_family": "Linux",
        "invocation_digest": hashlib.sha256(canonical_json_bytes([IMAGES_NOTE])).hexdigest(),
        "cells": receipt_cells,
    })
    _exclusive_write(output, canonical_json_bytes(receipt) + b"\n")
    return {"status": "pass", "receipt_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "cells": [cell["python"] for cell in receipt_cells]}


IMAGES_NOTE = "python:{version}-slim for 3.9-3.12 per the runbook"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--print-manifest", action="store_true",
                        help="print the expected clean-candidate source manifest digest")
    args = parser.parse_args()
    try:
        if args.print_manifest:
            print(tree_manifest_digest(ROOT))
            return 0
        if not args.cells_dir or not args.output:
            parser.error("--cells-dir and --output are required unless --print-manifest")
        result = build(args.output, args.cells_dir)
    except DeliverySummaryError as error:
        print(json.dumps({"status": "fail", "code": error.code, "detail": error.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
