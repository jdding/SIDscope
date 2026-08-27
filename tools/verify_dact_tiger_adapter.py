#!/usr/bin/env python3
"""Verify the DACT/TIGER G0--G5 report and bounded AR contract."""

from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.adapters.dact import (  # noqa: E402
    DACTContractError,
    run_deterministic_autoregressive_fixture,
)


AUDIT = ROOT / "docs/reproducibility/dact_tiger_source_audit.json"
FIXTURE = ROOT / "examples/dact_tiger_autoregressive_fixture/manifest.json"
PREFLIGHT = ROOT / "docs/reproducibility/dact_tiger_ancestry_preflight.json"
G21 = ROOT / "docs/reproducibility/g21_released_tiger_trace_summary.json"
G22 = ROOT / "docs/reproducibility/g22_diagnose_repair_handoff_summary.json"
TRACE_MANIFEST = ROOT / "docs/reproducibility/d7_labeled_trace_release.json"
TRACE_ROWS = ROOT / "docs/reproducibility/d7_labeled_trace_rows.csv.gz"
RUNNER = ROOT / "tools/run_v1_gate21_tiger_d7_trace.py"
STATUS = ROOT / "docs/reproducibility/dact_tiger_adapter_status.json"
PINNED_REVISION = "0b8d8cec88fee83b2384dd236628c2802f337d26"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict[str, Any]:
    failures: list[str] = []
    audit = _read_json(AUDIT)
    fixture = _read_json(FIXTURE)
    preflight = _read_json(PREFLIGHT)
    g21 = _read_json(G21)
    g22 = _read_json(G22)
    trace_manifest = _read_json(TRACE_MANIFEST)
    status = _read_json(STATUS)

    source = audit.get("source", {})
    if audit.get("schema") != "sidscope.generator_source_audit.v1":
        failures.append("source audit schema mismatch")
    if source.get("revision") != PINNED_REVISION:
        failures.append("source audit revision mismatch")
    if source.get("license_status") != "no_license_detected":
        failures.append("source audit must preserve the absent-license boundary")
    if source.get("license_identifier") != "NOASSERTION":
        failures.append("source audit license identifier must be NOASSERTION")
    if source.get("license_files_found") != [] or source.get("github_api_license") is not None:
        failures.append("source audit incorrectly claims a code or asset license")
    if source.get("paper_license_is_not_code_license") is not True:
        failures.append("paper and code license boundaries were conflated")
    assets = audit.get("asset_audit", {})
    if assets.get("released_tiger_checkpoint", {}).get("sha256") != (
        "2e13d9e31788fe4471bd70e6a480aa27e144dbd84bc21337f54808d99e077f01"
    ):
        failures.append("released checkpoint hash mismatch")
    if assets.get("released_sid_mapping", {}).get("unique_full_codes") != 9610:
        failures.append("released mapping identity count mismatch")
    if assets.get("source_item_mapping", {}).get("entries") != 10217:
        failures.append("source item mapping count mismatch")

    try:
        trace = run_deterministic_autoregressive_fixture(fixture)
    except Exception as exc:
        trace = {}
        failures.append(f"positive CPU fixture failed: {type(exc).__name__}: {exc}")
    else:
        if trace.get("decode_state_kind") != "ordered_autoregressive_prefix_beam":
            failures.append("fixture lost the ordered autoregressive state")
        if [step.get("prefix_depth") for step in trace.get("steps", [])] != [1, 2, 3, 4]:
            failures.append("fixture prefix depths are not complete and ordered")
        if [row.get("normalized_item_id") for row in trace.get("ranked_items", [])] != [
            "1", "2", "3", "4"
        ]:
            failures.append("fixture ranked-item export mismatch")
        if trace.get("ambiguity", {}).get("catalog_collision_count") != 1:
            failures.append("fixture did not preserve the full-SID collision")

    expected = fixture.get("expected_failure", {})
    invalid = copy.deepcopy(fixture)
    transition = invalid["steps"][int(expected["prefix_depth"]) - 1]["transitions"][
        int(expected["transition_index"])
    ]
    transition["appended_token"] = int(expected["invalid_appended_token"])
    observed_failure = None
    try:
        run_deterministic_autoregressive_fixture(invalid)
    except DACTContractError as exc:
        observed_failure = exc.label
    if observed_failure != expected.get("failure_label"):
        failures.append(
            "expected-failure mismatch: "
            f"expected={expected.get('failure_label')!r} observed={observed_failure!r}"
        )

    if preflight.get("status") != "pass" or preflight.get("source_revision") != PINNED_REVISION:
        failures.append("released-checkpoint ancestry preflight revision/status mismatch")
    preflight_outputs = preflight.get("outputs", {})
    for field in (
        "ordered_prefixes_present",
        "beam_ancestry_present",
        "finite_ranked_sequence_scores",
        "exporter_labeler_resolution_match",
    ):
        if preflight_outputs.get(field) is not True:
            failures.append(f"released-checkpoint preflight did not pass {field}")
    if preflight_outputs.get("status") != "PASS_G21_PREFLIGHT":
        failures.append("released-checkpoint preflight contract did not pass")

    if g21.get("source", {}).get("source_revision") != PINNED_REVISION:
        failures.append("G21 primary source revision mismatch")
    if g21.get("protocol", {}).get("target_traces") != 500:
        failures.append("G21 primary target count mismatch")
    if g21.get("protocol", {}).get("beam_rows_per_mode") != 25000:
        failures.append("G21 primary beam-row count mismatch")
    if g21.get("results", {}).get("constrained", {}).get("invalid_path_rows") != 0:
        failures.append("G21 constrained validity accounting mismatch")
    if g21.get("results", {}).get("unconstrained", {}).get("invalid_path_rows") != 988:
        failures.append("G21 unconstrained invalid-path accounting mismatch")
    if g22.get("source", {}).get("source_revision") != PINNED_REVISION:
        failures.append("G22 lifecycle source revision mismatch")

    cases = trace_manifest.get("cases", {})
    expected_cases = {
        "dact_tiger_constrained": 25000,
        "dact_tiger_unconstrained": 25000,
    }
    for case_id, rows in expected_cases.items():
        if cases.get(case_id, {}).get("rows") != rows:
            failures.append(f"deidentified trace manifest row mismatch for {case_id}")
    case_counts: dict[str, int] = {case_id: 0 for case_id in expected_cases}
    with gzip.open(TRACE_ROWS, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        forbidden_columns = {"user_id", "target_item_id", "sid_path", "score"}
        if forbidden_columns & set(reader.fieldnames or []):
            failures.append("public deidentified trace rows contain forbidden identity/path/score columns")
        for row in reader:
            case_id = row.get("case_id")
            if case_id in case_counts:
                case_counts[case_id] += 1
    if case_counts != expected_cases:
        failures.append(f"public deidentified DACT row counts mismatch: {case_counts}")

    gates = {
        "G0": "blocked_no_source_or_asset_license",
        "G1": "pass_released_source_normalized_sid_vocabulary_resolved_item_round_trip",
        "G2": "pass_ordered_prefix_beam_ancestry_and_step_logprob_contract",
        "G3": "pass_validity_ambiguity_collision_resolution_and_failure_labels",
        "G4": "pass_deidentified_trace_ranked_item_score_and_split_export",
        "G5": "pass_cpu_fixture_released_checkpoint_smoke_expected_failure_hashes_and_verifier",
    }
    input_sha256 = {
        "source_audit": _sha256(AUDIT),
        "fixture_manifest": _sha256(FIXTURE),
        "ancestry_preflight": _sha256(PREFLIGHT),
        "g21_primary_summary": _sha256(G21),
        "g22_handoff_summary": _sha256(G22),
        "deidentified_trace_manifest": _sha256(TRACE_MANIFEST),
        "deidentified_trace_rows": _sha256(TRACE_ROWS),
        "released_trace_runner": _sha256(RUNNER),
    }
    if status.get("schema") != "sidscope.dact_tiger_adapter_status.v1":
        failures.append("adapter status schema mismatch")
    if status.get("gates") != gates:
        failures.append("adapter status G0-G5 fields differ from the executable verifier")
    if status.get("input_sha256") != input_sha256:
        failures.append("adapter status hashes differ from current evidence")
    promotion = status.get("promotion", {})
    if promotion.get("named_adapter") is not False or promotion.get("decision") != "close_named_adapter":
        failures.append("adapter promotion boundary mismatch")

    return {
        "schema": "sidscope.dact_tiger_adapter_verification.v1",
        "status": "pass" if not failures else "fail",
        "route_id": "dact_tiger",
        "source_revision": PINNED_REVISION,
        "gates": gates,
        "fixture": {
            "trace_schema": trace.get("schema"),
            "ranked_item_ids": [
                row.get("normalized_item_id") for row in trace.get("ranked_items", [])
            ],
            "catalog_collision_count": trace.get("ambiguity", {}).get("catalog_collision_count"),
            "expected_failure_label": observed_failure,
        },
        "released_checkpoint_smoke": {
            "status": preflight_outputs.get("status"),
            "ordered_prefixes_present": preflight_outputs.get("ordered_prefixes_present"),
            "beam_ancestry_present": preflight_outputs.get("beam_ancestry_present"),
        },
        "public_deidentified_trace_rows": sum(case_counts.values()),
        "promotion": {
            "named_adapter": False,
            "reason": "G1-G5 pass, but G0 is blocked because the official source and assets have no explicit license.",
        },
        "input_sha256": input_sha256,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
