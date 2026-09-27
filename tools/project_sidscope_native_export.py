#!/usr/bin/env python3
"""Thin CLI wrapper over `sidscope.native_bridge` (pure-data projection).

The implementation lives in the installed package. This source-tree entry
registers the hash-pinned RPG v1 verifier as the explicit evidence-full
resource provider, keeps the dependency-free fixture regression available,
and preserves the historical argument surface and error codes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidscope import native_bridge
from sidscope.native_bridge import NativeBridgeError, compare_exports, fail, project_export

# Explicit evidence-full resource: the unchanged hash-pinned RPG v1 verifier.
from tools.verify_rpg_trained_trace_bundle import verify as _verify_rpg

native_bridge.set_native_verifier_provider(_verify_rpg)

# Historical name kept for callers of this wrapper.
NativeInspectionError = NativeBridgeError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-fixtures", action="store_true", help="Dependency-free evidence-full packaged regression")
    args = parser.parse_args(argv)
    try:
        if args.check_fixtures:
            if args.input or args.selection or args.output:
                fail("invalid_projection_arguments", "fixture check takes no input/output")
            rpg = ROOT / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"
            psid = ROOT / "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json"
            if project_export(rpg)["metrics"]["overall"]["hit_at_cutoff"] != .2:
                fail("packaged_projection_regression", "RPG metric")
            if project_export(psid)["metrics"] is not None:
                fail("packaged_projection_regression", "target-free PSID")
            if compare_exports(rpg, rpg)["comparison_kind"] != "same_export_recomputation":
                fail("packaged_projection_regression", "self comparison boundary")
            try:
                compare_exports(psid, psid)
            except NativeBridgeError as error:
                if error.code != "native_target_labels_required":
                    raise
            else:
                fail("packaged_projection_regression", "missing-label comparison accepted")
            print(json.dumps({"status": "pass", "checks": 4, "scope": "supplied_native_exports_only"}))
            return 0
        if args.input is None or args.output is None:
            fail("invalid_projection_arguments", "input and output required")
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError(args.output)
        result = project_export(args.input, selection=args.selection)
        with args.output.open("x") as handle:
            json.dump(result, handle, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps({"status": result["status"], "content_sha256": result["content_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
