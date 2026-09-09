#!/usr/bin/env python3
"""Verify N07 zero-change controls on supplied RPG and PSID preflight inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_sha256, load_json, with_content_sha256
from sidscope.refresh import compare_snapshots


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_route(path: Path, route: str, semantics: str) -> dict:
    started = time.perf_counter()
    source_sha256 = _file_sha256(path)
    source = load_json(path, max_bytes=None)
    mapping = source.get("mapping")
    if not isinstance(mapping, list):
        raise ValueError(f"{route}: mapping list required")
    snapshot = {
        "dataset": route,
        "item_namespace": f"{route}-items",
        "sid_namespace": f"{route}-sid",
        "semantics": semantics,
        "mapping": mapping,
    }
    snapshot_sha256 = canonical_sha256(snapshot)
    report = compare_snapshots(snapshot, snapshot, max_examples=5)
    if report["classification"]["classification"] != "unchanged":
        raise AssertionError(f"{route}: same-input classification is not unchanged")
    if any(row["affected_items"] for row in report["structural_change"]):
        raise AssertionError(f"{route}: same-input structural control is nonzero")
    if _file_sha256(path) != source_sha256:
        raise AssertionError(f"{route}: source input changed during verification")
    return {
        "route": route,
        "semantics": semantics,
        "source_sha256": source_sha256,
        "mapping_items": len(mapping),
        "snapshot_sha256": snapshot_sha256,
        "report_sha256": report["content_sha256"],
        "structural_scopes": [row["scope"] for row in report["structural_change"]],
        "elapsed_seconds": time.perf_counter() - started,
        "status": "pass",
    }


def verify(rpg_preflight: Path, psid_preflight: Path) -> dict:
    routes = [
        _verify_route(rpg_preflight, "rpg-beauty", "parallel_positions"),
        _verify_route(psid_preflight, "psid-video-games", "ordered_prefix"),
    ]
    return with_content_sha256({
        "format": "sidscope.sid_refresh_real_control.v1",
        "status": "pass",
        "scope": "same_input_zero_change_control_no_model_execution",
        "routes": routes,
        "limitations": [
            "These controls exercise actual mapping shapes but are not a real before/after refresh.",
            "No model, checkpoint or upstream training claim is verified or rerun.",
        ],
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpg-preflight", type=Path, required=True)
    parser.add_argument("--psid-preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.rpg_preflight, args.psid_preflight)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    except (AssertionError, KeyError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"status": "fail", "code": type(error).__name__, "detail": str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
