#!/usr/bin/env python3
"""Shared Linux matrix cell rules: one validator for builder and summary.

A cell is acceptable only when it carries the frozen container image, a Linux
OS and real architecture, the container interpreter, a source-tree manifest
digest equal to the clean candidate, a structured source check, and every
required step executed with exit 0 — pytest with a positive integer pass
count — plus per-step unique log markers present in the cell log. Labels,
shared markers, boolean claims or a zero pass count are refused everywhere.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

LINUX_FORMAT = "sidscope.linux_matrix_receipt.v1"
LINUX_PYTHONS = ("3.9", "3.10", "3.11", "3.12")
IMAGES = {"3.9": "python:3.9-slim", "3.10": "python:3.10-slim",
          "3.11": "python:3.11-slim", "3.12": "python:3.12-slim"}
REQUIRED_STEPS = ("pytest", "metadata", "architecture", "sdlc_acceptance",
                  "sdlc_hardening", "profiles", "resource")
CELL_FIELDS = {"python", "image", "os", "arch", "interpreter", "python_full", "raw_platform",
               "source_manifest_sha256", "source_check", "status", "exit_code", "head", "steps", "log"}
STEP_FIELDS = {"name", "exit_code", "passed_count", "log_marker"}


class MatrixCellError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def validate_cell(cell: dict[str, Any], *, expected_manifest: str, head: str,
                  public_snapshot_digest: str, log_base: Path) -> None:
    version = cell.get("python")
    if version not in LINUX_PYTHONS:
        raise MatrixCellError("invalid_matrix_cell", f"python {version!r}")
    if not CELL_FIELDS <= set(cell):
        raise MatrixCellError("invalid_matrix_cell", f"{version}: fields {sorted(CELL_FIELDS - set(cell))}")
    if cell.get("image") != IMAGES[version]:
        raise MatrixCellError("invalid_matrix_cell", f"{version}: image {cell.get('image')!r} != {IMAGES[version]!r}")
    os_text = str(cell.get("os", ""))
    if not os_text.startswith("Linux"):
        raise MatrixCellError("invalid_matrix_cell", f"{version}: os={cell.get('os')!r} is not Linux")
    # Third-round finding 3: the recorded runtime identity must agree with the
    # claimed version and OS, so a cell assembled on a different machine or
    # interpreter can never be relabeled into the matrix.
    python_full = str(cell.get("python_full", ""))
    if not python_full.startswith(f"{version}."):
        raise MatrixCellError("invalid_matrix_cell",
                              f"{version}: recorded interpreter {python_full!r} does not match claimed {version}")
    raw_platform = str(cell.get("raw_platform", ""))
    if raw_platform.split("-")[0] != os_text.split()[0]:
        raise MatrixCellError("invalid_matrix_cell",
                              f"{version}: recorded platform {raw_platform!r} does not match claimed OS")
    if not str(cell.get("arch", "")):
        raise MatrixCellError("invalid_matrix_cell", f"{version}: arch")
    if not Path(str(cell.get("interpreter", ""))).name.startswith("python"):
        raise MatrixCellError("invalid_matrix_cell", f"{version}: interpreter")
    if cell.get("source_manifest_sha256") != expected_manifest:
        raise MatrixCellError("stale_matrix_head",
                              f"{version}: container tree manifest does not match the clean candidate")
    source_check = cell.get("source_check") or {}
    if (source_check.get("head") != head
            or source_check.get("public_snapshot_digest") != public_snapshot_digest
            or source_check.get("clean") is not True):
        raise MatrixCellError("matrix_identity_unchecked", f"{version}: source check does not match the candidate")
    if cell.get("status") != "pass" or cell.get("exit_code") != 0:
        raise MatrixCellError("failed_matrix_cell", f"{version}: status/exit")
    steps = cell.get("steps") or []
    names = [step.get("name") for step in steps]
    if sorted(n or "" for n in names) != sorted(REQUIRED_STEPS) or len(set(names)) != len(names):
        raise MatrixCellError("invalid_matrix_cell", f"{version}: steps {names}")
    markers = []
    for step in steps:
        if not STEP_FIELDS <= set(step):
            raise MatrixCellError("invalid_matrix_cell", f"{version}: step {step.get('name')} fields")
        if step.get("exit_code") != 0:
            raise MatrixCellError("failed_matrix_cell", f"{version}: step {step['name']}")
        marker = step.get("log_marker")
        if not isinstance(marker, str) or not marker:
            raise MatrixCellError("invalid_matrix_cell", f"{version}: step {step['name']} marker")
        markers.append(marker)
        if step.get("name") == "pytest":
            passed = step.get("passed_count")
            if isinstance(passed, bool) or not isinstance(passed, int) or passed <= 0:
                raise MatrixCellError("invalid_matrix_cell", f"{version}: pytest passed_count {passed!r}")
    if len(set(markers)) != len(markers):
        raise MatrixCellError("invalid_matrix_cell", f"{version}: step markers must be unique")
    log = cell.get("log") or {}
    relative = log.get("path", "")
    relative_path = Path(relative)
    if not relative or relative_path.is_absolute() or ".." in relative_path.parts:
        raise MatrixCellError("invalid_matrix_cell", f"{version}: log path")
    log_path = log_base / relative_path
    if not log_path.is_file() or hashlib.sha256(log_path.read_bytes()).hexdigest() != log.get("sha256"):
        raise MatrixCellError("matrix_log_integrity", f"{version}: {relative}")
    combined = log_path.read_text(errors="replace")
    for step, marker in zip(steps, markers):
        if marker not in combined:
            raise MatrixCellError("matrix_log_integrity", f"{version}: marker for {step['name']} absent from log")


def cell_log_filename(version: str) -> str:
    return f"linux-{version}.log"
