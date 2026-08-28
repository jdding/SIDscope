#!/usr/bin/env python3
"""Inspect pinned DiffGRM source identity without importing or executing it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


PINNED_REVISION = "ad7b971c7e525e9fea6fb8e362a5c49dccb2473c"
PINNED_HASHES = {
    "README.md": "a822a2461afae4428e41f8985486616a0f566434b92b5d44e77b533f22b48096",
    "main.py": "02cf49c69e1b35e4a8442ccafcaeb78eb8924243d3667e35cafabc78ac477507",
    "genrec/models/DIFF_GRM/model.py": "bf8de24f164fe2d7a765b5d4d443d5f10872cba40cc420c58875d3f6bb93c5a1",
    "genrec/models/DIFF_GRM/tokenizer.py": "15c18ff56461662c20a7ec9571517a409d01a1e2a82e799ea1674415e0cf1a32",
    "genrec/models/DIFF_GRM/beam.py": "ff0699d1dacd6a9c6f8b859d49ee6ba817119b10f8617d6f82bdd062e3cdf0b6",
}
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "NOTICE")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_source(source: Path | None = None) -> dict[str, Any]:
    """Return a non-executing source-identity and license-marker result."""

    observed_revision = PINNED_REVISION
    observed_hashes = dict(PINNED_HASHES)
    license_files: list[str] = []
    inspection_scope = "recorded_revision_audit"
    failures: list[str] = []
    if source is not None:
        source = source.resolve()
        inspection_scope = "local_checkout_read_only"
        try:
            observed_revision = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            failures.append(f"cannot resolve git revision: {exc}")
        observed_hashes = {}
        for relative, expected in PINNED_HASHES.items():
            path = source / relative
            if not path.is_file():
                failures.append(f"missing pinned source file: {relative}")
                continue
            observed = _sha256(path)
            observed_hashes[relative] = observed
            if observed != expected:
                failures.append(f"source hash mismatch: {relative}")
        license_files = [name for name in LICENSE_NAMES if (source / name).is_file()]

    if observed_revision != PINNED_REVISION:
        failures.append(
            f"revision mismatch: expected {PINNED_REVISION}, observed {observed_revision}"
        )
    if license_files:
        failures.append(
            "a license file now exists; re-audit its terms and update the recorded G0 decision"
        )

    return {
        "schema": "sidscope.diffgrm_staged_preflight.v2",
        "status": "pass" if not failures else "fail",
        "route_id": "diffgrm_www2026",
        "inspection_scope": inspection_scope,
        "source_revision": observed_revision,
        "source_sha256": observed_hashes,
        "source_code_imported": False,
        "source_code_executed": False,
        "license_files_found": license_files,
        "g0": {
            "publication_and_revision_identity": "pass",
            "license_state": "NOASSERTION_marker",
            "development_and_execution": "not_blocked_by_license_marker",
            "redistribution": "not_authorized_by_this_preflight",
        },
        "execution_authorized": not failures,
        "redistribution_authorized": False,
        "next_gate": "validate the frozen prepared selection and checkpoint-bound native trace bundle",
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-execution-ready", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = inspect_source(args.source)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(1)
    if args.require_execution_ready and not result["execution_authorized"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
