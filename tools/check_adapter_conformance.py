#!/usr/bin/env python3
"""Run the SIDScope C0-C5 adapter conformance protocol."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.conformance import redact_private_input_paths, run_conformance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-fail", action="store_true", help="Write a failing report without a non-zero exit.")
    parser.add_argument(
        "--redact-input-paths",
        action="store_true",
        help="Keep C1 counts and replace local normalized-table paths with a public availability marker.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_conformance(
        args.manifest.resolve(),
        root=args.root.resolve(),
        inventory_path=args.inventory.resolve() if args.inventory else None,
    )
    if args.redact_input_paths:
        report = redact_private_input_paths(report)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if report["status"] != "pass" and not args.allow_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
