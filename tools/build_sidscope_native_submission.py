#!/usr/bin/env python3
"""Thin CLI wrapper over `sidscope.native_bridge` (canonical native submission).

The implementation lives in the installed package. This source-tree entry
registers the hash-pinned RPG v1 verifier as the explicit evidence-full
resource provider and preserves the historical argument surface and codes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidscope.native_bridge import (
    ALIASES,
    DATASETS,
    PRODUCER,
    NativeBridgeError,
    NativeObservationProducer,
    build_documents,
    build_submission,
    digest,
    encode,
    fail,
    native_observations,
    validate_identities,
    validate_metadata,
    verify_submission,
    write_package,
)
from sidscope.native_bridge import validate_observed_inputs

# Explicit evidence-full resource: the unchanged hash-pinned RPG v1 verifier.
from tools.verify_rpg_trained_trace_bundle import verify as _verify_rpg
from sidscope.native_bridge import set_native_verifier_provider

set_native_verifier_provider(_verify_rpg)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument("--verify-submission", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify_submission:
            result = verify_submission(args.input, args.metadata, args.verify_submission)
            print(json.dumps(result, sort_keys=True))
            return 0
        receipt = build_submission(args.input, args.metadata, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps({"status": receipt["status"], "admission": receipt["admission"]["status"], "bundle_sha256": receipt["bundle_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
