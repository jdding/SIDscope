#!/usr/bin/env python3
"""Installed-distribution probe for the pure-data native bridge (positive path).

Copied outside the repository and executed under the installed interpreter by
the operator's chain script. In every mode `sidscope` must import from the
installed site-packages (never a checkout/extraction on sys.path ahead of it).
PSID runs on the plain installed library; the RPG mode additionally registers
the unchanged hash-pinned verifier from the evidence-full provider tree, whose
provenance is recorded. The probe runs the canonical build plus the
original-input recheck on the authorized observation inputs, compares the
bundle against the expected SHA-256, and prints a machine-checkable result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("psid-wheel", "psid-sdist", "rpg-installed"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    args = parser.parse_args()

    import sidscope
    from sidscope import native_bridge

    sidscope_file = str(Path(sidscope.__file__).resolve())
    bridge_file = str(Path(native_bridge.__file__).resolve())
    if "site-packages" not in sidscope_file or "site-packages" not in bridge_file:
        print(json.dumps({"status": "fail", "code": "bridge_not_installed",
                          "sidscope_file": sidscope_file, "native_bridge_file": bridge_file}))
        return 2
    provider_file = None
    if args.mode == "rpg-installed":
        from tools.verify_rpg_trained_trace_bundle import verify as verify_rpg

        provider_file = str(Path(__import__("tools.verify_rpg_trained_trace_bundle", fromlist=["__file__"]).__file__).resolve())
        native_bridge.set_native_verifier_provider(verify_rpg)
    else:
        native_bridge.clear_native_verifier_provider()

    with tempfile.TemporaryDirectory(prefix="sidscope-installed-bridge-") as tmp:
        output = Path(tmp) / "installed-build"
        receipt = native_bridge.build_submission(args.input, args.metadata, output)
        bundle_sha = receipt["bundle_sha256"]
        if bundle_sha != args.expected_bundle_sha256:
            print(json.dumps({"status": "fail", "code": "installed_bundle_mismatch",
                              "installed": bundle_sha, "expected": args.expected_bundle_sha256}))
            return 2
        recheck = native_bridge.verify_submission(args.input, args.metadata, output / "submission")
        if recheck.get("status") != "accepted":
            print(json.dumps({"status": "fail", "code": "installed_recheck_failed", "detail": recheck}))
            return 2
    result = {
        "status": "pass",
        "mode": args.mode,
        "bundle_sha256": bundle_sha,
        "expected_bundle_sha256": args.expected_bundle_sha256,
        "sidscope_file": sidscope_file,
        "native_bridge_file": bridge_file,
        "provider_file": provider_file,
        "input_native_sha256": sha(args.input / "native.json"),
        "input_selection_sha256": sha(args.input / "selection.json"),
        "input_observations_sha256": sha(args.input / "observations.json"),
        "input_preflight_sha256": sha(args.input / "preflight.json"),
        "input_metadata_sha256": sha(args.metadata),
        "recheck_status": recheck.get("status"),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
