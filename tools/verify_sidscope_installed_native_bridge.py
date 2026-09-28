#!/usr/bin/env python3
"""Validate the installed native-bridge probe receipt (E02).

Executes nothing. The operator's chain script installs the wheel or sdist into
a fresh environment, copies `tools/sidscope_installed_bridge_probe.py` outside
the repository, runs it there, and saves the printed JSON plus the installed
artifact digest. This tool re-checks: installed (site-packages) import
provenance for sidscope and native_bridge in every mode, provider provenance
from the evidence-full tree for the RPG mode, input digests, expected-bundle
equality and artifact binding — then writes the receipt exclusively
(symlinks refused, never overwritten).
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
MODES = ("psid-wheel", "psid-sdist", "rpg-installed")
REQUIRED_PROBE_FIELDS = {"status", "mode", "bundle_sha256", "expected_bundle_sha256",
                         "sidscope_file", "native_bridge_file", "provider_file",
                         "input_native_sha256", "input_selection_sha256",
                         "input_observations_sha256", "input_preflight_sha256",
                         "input_metadata_sha256", "recheck_status"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path, *, result_json: Path, artifact: Path, expected_bundle_sha256: str,
          mode: str, provider_prefix: str | None = None) -> dict:
    result = json.loads(result_json.read_text(encoding="utf-8"))
    if result.get("status") != "pass" or not REQUIRED_PROBE_FIELDS <= set(result):
        raise DeliverySummaryError("installed_bridge_probe_failed", str(result_json))
    if result.get("mode") != mode or mode not in MODES:
        raise DeliverySummaryError("installed_bridge_mode_mismatch", str(result.get("mode")))
    if result["bundle_sha256"] != expected_bundle_sha256 or result["expected_bundle_sha256"] != expected_bundle_sha256:
        raise DeliverySummaryError("installed_bundle_mismatch", result["bundle_sha256"])
    for field in ("sidscope_file", "native_bridge_file"):
        if "site-packages" not in result[field]:
            raise DeliverySummaryError("bridge_not_installed", f"{field}: {result[field]}")
    if result["recheck_status"] != "accepted":
        raise DeliverySummaryError("installed_bridge_probe_failed", "recheck")
    if mode == "rpg-installed":
        provider = result.get("provider_file")
        if not provider or not provider_prefix or not provider.startswith(provider_prefix):
            raise DeliverySummaryError("provider_provenance_mismatch", str(provider))
        if "/tools/" not in provider:
            raise DeliverySummaryError("provider_provenance_mismatch", provider)
    elif result.get("provider_file") is not None:
        raise DeliverySummaryError("installed_bridge_mode_mismatch", "provider recorded for a PSID mode")
    receipt = with_content_sha256({
        "format": RECEIPT_FORMAT,
        "mode": mode,
        "probe": result,
        "artifact_sha256": _sha(artifact) if artifact.is_file() else None,
        "expected_bundle_sha256": expected_bundle_sha256,
        "status": "pass",
    })
    output = Path(output)
    if output.is_symlink() or output.exists():
        raise DeliverySummaryError("receipt_output_exists", f"{output} already exists; use a new attempt path")
    resolved_parent = output.resolve().parent
    if ROOT in [resolved_parent, *resolved_parent.parents] and ".local_artifacts" not in output.parts:
        raise DeliverySummaryError("receipt_output_invalid", "write the receipt beside the evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(canonical_json_bytes(receipt) + b"\n")
    return {"status": "pass", "receipt_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "bundle_sha256": result["bundle_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True,
                        help="installed wheel or sdist whose digest binds the receipt")
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--provider-prefix", default=None,
                        help="evidence-full tree prefix required for rpg-installed provider provenance")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.output, result_json=args.result_json, artifact=args.artifact,
                       expected_bundle_sha256=args.expected_bundle_sha256,
                       mode=args.mode, provider_prefix=args.provider_prefix)
    except DeliverySummaryError as error:
        print(json.dumps({"status": "fail", "code": error.code, "detail": error.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
