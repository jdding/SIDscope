#!/usr/bin/env python3
"""Check containment and requirement completeness separately from readiness."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.submission import check_submission
from sidinspector.submission.recomputed import build_recomputed_submission
from sidinspector.submission.checker import validate_submission_package
from sidinspector.submission.indexes import generate_status_index, generate_result_index
from sidinspector.evidence.comparison import compare_evidence_bundles
from tools.inspect_sidscope_native_export import inspect_export
from tools.verify_sidscope_sdlc_acceptance import user_acceptance_status


def verify() -> dict:
    ledger = ROOT / "docs/reproducibility/sidscope_sdlc_requirements.csv"
    with ledger.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = {f"F{i:02d}" for i in range(1, 15)} | {f"N{i:02d}" for i in range(1, 11)}
    assert len(rows) == len(expected) and {row["id"] for row in rows} == expected
    for row in rows:
        assert row["owner"] and row["acceptance"] and row["priority"] in {"P0", "P1", "P2"}
        assert row["state"] in {"verified", "contained", "partial", "open", "blocked"}
        assert (ROOT / row["verification"]).is_file(), row["id"]
    user_acceptance = user_acceptance_status(rows)
    positive = ROOT / "examples/conformance_ecosystem_fixture/submission/positive"
    assert check_submission(positive).failures[0]["code"] == "independent_gate_verification_required"
    with tempfile.TemporaryDirectory(prefix="sidscope-positive-admission-") as tmp:
        fixture = ROOT / "examples/canonical_pipeline_fixture"
        output = Path(tmp) / "submission"
        result = build_recomputed_submission(positive, output,
            trace=json.loads((fixture / "trace_envelope.json").read_text()),
            selection=json.loads((fixture / "episode_selection.json").read_text()))
        assert result["status"] == "accepted", result
        package = validate_submission_package(output)
        assert generate_status_index([package])["entries"][0]["status_label"] == "diagnostics_verified"
        assert generate_result_index([package])["entries"][0]["result_card"] == package.evidence_bundle.result_card
        comparison = compare_evidence_bundles(package.evidence_bundle, package.evidence_bundle, left_objects=package.objects, right_objects=package.objects)
        assert comparison["status"] == "compatible"
    native = [inspect_export(ROOT / relative) for relative in (
        "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json",
        "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json")]
    assert native[0]["metrics"]["hit_at_cutoff"] == 0.2
    assert native[1]["metrics"]["status"] == "not_verified"
    with tempfile.TemporaryDirectory(prefix="sidscope-bounded-json-") as tmp:
        path = Path(tmp)
        (path / "submission.json").write_text("[" * 1500 + "0" + "]" * 1500)
        assert check_submission(path).failures[0]["code"] == "submission_json_depth_exceeded"
    # Findings remain technical obligations; proposed features are a backlog,
    # not an implicitly approved expansion of the certification scope.
    blockers = [row["id"] for row in rows if row["id"].startswith("F") and row["state"] != "verified"]
    # F09 and N01 retain the deliberately human acceptance condition. They do
    # not conceal a technical failure and automation must never mark them done.
    acceptance_only = {"F09", "N01"}
    engineering_blockers = [item for item in blockers if item not in acceptance_only]
    # Explicitly approved local work is distinct from unapproved candidate scope.
    # Neither list creates a public 2.0 compatibility/release promise.
    approved_local = {"N01", "N02", "N03", "N04", "N05", "N06", "N07", "N08"}
    pending_local = [row["id"] for row in rows if row["id"] in approved_local and row["state"] != "verified"]
    engineering_pending_local = [item for item in pending_local if item not in acceptance_only]
    candidates = [row["id"] for row in rows if row["id"].startswith("N") and row["id"] not in approved_local and row["state"] != "verified"]
    pending_acceptance = ["independent_user_actual_use"] if user_acceptance != "accepted" else []
    engineering_ready = not engineering_blockers and not engineering_pending_local
    certification_ready = not blockers and not pending_local and not pending_acceptance
    return {"status": "pass", "scope": "recomputed_admission_comparison_and_real_native_consumers",
            "positive_admission": "diagnostics_verified", "real_native_consumers": native,
            "engineering_ready": engineering_ready, "certification_ready": certification_ready,
            "blocking_requirements": blockers,
            "engineering_blocking_requirements": engineering_blockers + engineering_pending_local,
            "approved_local_workflow_pending": pending_local,
            "approved_local_workflow_ready": not blockers and not pending_local,
            "pending_acceptance": pending_acceptance,
            "candidate_requirements": candidates,
            "boundary": "Regression checks do not verify private training claims or independent user acceptance."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--require-engineering-ready", action="store_true")
    args = parser.parse_args()
    result = verify()
    if (args.require_ready and not result["certification_ready"]) or (args.require_engineering_ready and not result["engineering_ready"]):
        result["status"] = "blocked"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
