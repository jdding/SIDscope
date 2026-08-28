#!/usr/bin/env python3
"""Verify an external DiffGRM prepared/selection/trained-trace bundle.

This verifier is deliberately independent of the staged source and license
audit.  It validates only the dataset, episode, checkpoint/training bindings,
native masked trace, resolution, ranking, and compute contracts supplied on
the command line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.adapters.diffgrm import (  # noqa: E402
    DiffGRMContractError,
    canonical_sha256,
    validate_trace_bundle,
)


RESULT_SCHEMA = "sidscope.diffgrm_trained_trace_bundle_verification.v1"


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiffGRMContractError("input_read_error", f"cannot read JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise DiffGRMContractError("input_type_mismatch", "input JSON must be an object")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise DiffGRMContractError("input_read_error", f"cannot hash input: {exc}") from exc
    return digest.hexdigest()


def verify_paths(prepared_path: Path, selection_path: Path, bundle_path: Path) -> dict[str, Any]:
    """Return a stable pass/fail record without inspecting upstream source."""

    paths = {
        "prepared": prepared_path,
        "selection": selection_path,
        "bundle": bundle_path,
    }
    try:
        prepared = _read_object(prepared_path)
        selection = _read_object(selection_path)
        bundle = _read_object(bundle_path)
        verification = validate_trace_bundle(bundle, prepared, selection)
        return {
            "schema": RESULT_SCHEMA,
            "status": "pass",
            "route_id": "diffgrm_www2026",
            "contract_scope": "external_prepared_selection_trained_trace_only",
            "source_audit_checked": False,
            "license_audit_checked": False,
            "canonical_sha256": {
                "prepared": canonical_sha256(prepared),
                "selection": canonical_sha256(selection),
                "bundle": canonical_sha256(bundle),
            },
            "input_file_sha256": {
                name: _file_sha256(path) for name, path in paths.items()
            },
            "episode_count": verification["episode_count"],
            "five_bucket_counts": verification["five_bucket_counts"],
            "bindings": verification["bindings"],
            "metrics": {
                "hit_at_10": verification["hit_at_10"],
                "ndcg_at_10": verification["ndcg_at_10"],
                "per_bucket": verification["per_bucket"],
            },
            "rank_summary": {
                "exact_target_rank_count": verification["exact_target_rank_count"],
                "right_censored_target_rank_count": verification[
                    "right_censored_target_rank_count"
                ],
            },
            "resolution_summary": verification["resolution_summary"],
            "compute_summary": verification["compute_summary"],
            "failure": None,
        }
    except DiffGRMContractError as exc:
        failure_label = exc.label
        failure_message = str(exc)
    except (KeyError, TypeError, ValueError) as exc:
        failure_label = "malformed_bundle"
        failure_message = f"{type(exc).__name__}: {exc}"
    else:
        raise AssertionError("unreachable")

    if failure_label:
        file_hashes: dict[str, str | None] = {}
        for name, path in paths.items():
            try:
                file_hashes[name] = _file_sha256(path)
            except DiffGRMContractError:
                file_hashes[name] = None
        return {
            "schema": RESULT_SCHEMA,
            "status": "fail",
            "route_id": "diffgrm_www2026",
            "contract_scope": "external_prepared_selection_trained_trace_only",
            "source_audit_checked": False,
            "license_audit_checked": False,
            "input_file_sha256": file_hashes,
            "failure": {"label": failure_label, "message": failure_message},
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_paths(args.prepared, args.selection, args.bundle)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
