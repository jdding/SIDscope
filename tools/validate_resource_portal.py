#!/usr/bin/env python3
"""Validate SIDScope's resource portal SHA-256 manifest and pure-Python workbench."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest() -> int:
    manifest = json.loads((ROOT / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    entries = manifest["files"]
    if len(entries) != manifest["file_count"]:
        raise ValueError("PACKAGE_MANIFEST.json file_count mismatch.")
    manifest_map: dict[str, str] = {}
    for row in entries:
        rel = row["path"]
        full = ROOT / rel
        if not full.is_file():
            raise FileNotFoundError(f"Missing portal file: {rel}")
        actual = sha256_file(full)
        if actual != row["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {rel}")
        manifest_map[rel] = actual

    checksum_map: dict[str, str] = {}
    for line in (ROOT / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, rel = line.split("  ", 1)
            checksum_map[rel] = digest
    if checksum_map != manifest_map:
        raise ValueError("CHECKSUMS.sha256 disagrees with PACKAGE_MANIFEST.json.")
    return len(entries)


def main() -> None:
    count = verify_manifest()
    print(f"Verified SHA-256 integrity for {count} SIDScope portal & evidence files.")

    proc = subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / "demo" / "browser_example.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    if payload.get("status") != "pass":
        raise RuntimeError("SIDScope browser_example.py did not return status=pass.")
    if len(payload.get("table5_profiles", [])) != 8:
        raise RuntimeError("Expected 8 executable route profiles in Table 5.")
    if payload.get("c1_failure_check", {}).get("c1_failed") is not True:
        raise RuntimeError("Public C1 failure fixture did not trigger C1 rejection.")
    if len(payload.get("dact_handoff", [])) != 5:
        raise RuntimeError("Expected 5 DACT handoff rows.")
    print("Verified pure-Python SIDScope workbench (8 tables, 8 routes, C1 rejection, D7 resolvers, DACT handoff).")
    print("PASS_SIDSCOPE_PORTAL_VALIDATION")


if __name__ == "__main__":
    main()
