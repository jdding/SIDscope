#!/usr/bin/env python3
"""Validate one external bounded PSID/Latte trained-trace handoff bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sidinspector.adapters.latte import (
    LatteCacheContractError,
    validate_latte_psid_trained_trace_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        result = validate_latte_psid_trained_trace_bundle(bundle)
        result["bundle_sha256"] = hashlib.sha256(args.bundle.read_bytes()).hexdigest()
    except (OSError, json.JSONDecodeError, LatteCacheContractError) as exc:
        result = {
            "schema": "sidscope.latte_psid_trained_trace_verification.v1",
            "status": "fail",
            "failure_label": getattr(exc, "label", "invalid_bundle_file"),
            "detail": str(exc),
        }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
