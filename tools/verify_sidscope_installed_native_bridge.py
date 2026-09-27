#!/usr/bin/env python3
"""Validate the installed native-bridge probe receipt (E02).

Executes nothing. The operator's chain script builds/installs the wheel (or
extracts the evidence-full archive), copies
`tools/sidscope_installed_bridge_probe.py` outside the repository, runs it
under the installed interpreter, and saves the printed JSON plus the wheel
digest. This tool re-checks: import provenance, input digests, expected bundle
equality and wheel binding, then writes the receipt the delivery evidence
keeps. Existing outputs are never overwritten.
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
from tools.sidscope_delivery_summary import DeliverySummaryError

RECEIPT_FORMAT = "sidscope.installed_bridge_receipt.v1"
REQUIRED_PROBE_FIELDS = {"status", "mode", "bundle_sha256", "expected_bundle_sha256",
                         "sidscope_file", "native_bridge_file", "import_prefix",
                         "input_native_sha256", "input_selection_sha256",
                         "input_observations_sha256", "input_preflight_sha256",
                         "input_metadata_sha256", "recheck_status"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path, *, result_json: Path, wheel: Path, expected_bundle_sha256: str,
          mode: str, import_prefix: str) -> dict:
    result = json.loads(result_json.read_text(encoding="utf-8"))
    if result.get("status") != "pass" or not REQUIRED_PROBE_FIELDS <= set(result):
        raise DeliverySummaryError("installed_bridge_probe_failed", str(result_json))
    if result["mode"] != mode:
        raise DeliverySummaryError("installed_bridge_mode_mismatch", f"{result['mode']} != {mode}")
    if result["bundle_sha256"] != expected_bundle_sha256 or result["expected_bundle_sha256"] != expected_bundle_sha256:
        raise DeliverySummaryError("installed_bundle_mismatch", result["bundle_sha256"])
    if result["import_prefix"] != import_prefix or import_prefix not in result["sidscope_file"] \
            or import_prefix not in result["native_bridge_file"]:
        raise DeliverySummaryError("bridge_import_prefix_mismatch", result["sidscope_file"])
    if result["recheck_status"] != "accepted":
        raise DeliverySummaryError("installed_bridge_probe_failed", "recheck")
    if "site-packages" not in result["sidscope_file"] and mode == "psid-runtime":
        raise DeliverySummaryError("bridge_import_prefix_mismatch",
                                   "runtime mode must import from site-packages")
    receipt = with_content_sha256({
        "format": RECEIPT_FORMAT,
        "mode": mode,
        "probe": result,
        "wheel_sha256": _sha(wheel) if wheel.is_file() else None,
        "expected_bundle_sha256": expected_bundle_sha256,
        "status": "pass",
    })
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        if ".local_artifacts" not in output.parts:
            raise DeliverySummaryError("receipt_output_invalid", "write the receipt beside the evidence")
    if output.exists() or output.is_symlink():
        raise DeliverySummaryError("receipt_output_exists", f"{output} already exists; use a new attempt path")
    output.write_bytes(canonical_json_bytes(receipt) + b"\n")
    return {"status": "pass", "receipt_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "bundle_sha256": result["bundle_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--mode", choices=("psid-runtime", "rpg-evidence-full"), required=True)
    parser.add_argument("--import-prefix", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.output, result_json=args.result_json, wheel=args.wheel,
                       expected_bundle_sha256=args.expected_bundle_sha256,
                       mode=args.mode, import_prefix=args.import_prefix)
    except DeliverySummaryError as error:
        print(json.dumps({"status": "fail", "code": error.code, "detail": error.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
