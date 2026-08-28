#!/usr/bin/env python3
"""Verify the packaged RPG dataset-neutral bridge, fixtures, and CPU smoke record."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rpg_non_ar_bridge import (  # noqa: E402
    BridgeFailure,
    canonical_hash,
    sha256_file,
    validate_episode_selection,
)
from tools.verify_rpg_trained_trace_bundle import (  # noqa: E402
    Failure,
    verify,
    verify_target_rank_claim,
)


FIXTURE = ROOT / "examples/rpg_non_ar_bridge_fixture"
EVIDENCE = ROOT / "docs/reproducibility/rpg_non_ar_bridge_smoke.json"
BEAUTY = ROOT / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"
RANK_DEPTH_FIXTURE = ROOT / "examples/rpg_rank_depth_fixture/target_rank_claims.json"


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be an object")
    return value


def main() -> None:
    evidence = read(EVIDENCE)
    prepared = read(FIXTURE / "prepared_dataset.json")
    selection = read(FIXTURE / "episode_selection.json")
    bundle = read(FIXTURE / "trained_trace_v2.json")
    expected_failure = read(FIXTURE / "expected_failure_duplicate_selection.json")
    rank_depth_fixture = read(RANK_DEPTH_FIXTURE)
    failures = []

    if evidence.get("schema") != "sidscope.rpg_non_ar_bridge_smoke.v1" or evidence.get("status") != "pass":
        failures.append("evidence status/schema mismatch")
    fixture = evidence.get("fixture", {})
    checks = {
        "prepared_dataset_file_sha256": sha256_file(FIXTURE / "prepared_dataset.json"),
        "prepared_dataset_canonical_sha256": canonical_hash(prepared),
        "episode_selection_file_sha256": sha256_file(FIXTURE / "episode_selection.json"),
        "episode_selection_canonical_sha256": canonical_hash(selection),
        "positive_bundle_file_sha256": sha256_file(FIXTURE / "trained_trace_v2.json"),
        "rank_depth_claim_fixture_sha256": sha256_file(RANK_DEPTH_FIXTURE),
    }
    for key, observed in checks.items():
        if fixture.get(key) != observed:
            failures.append(f"fixture hash mismatch: {key}")

    try:
        positive = verify(bundle, prepared, selection)
    except Exception as exc:
        positive = {}
        failures.append(f"positive fixture failed: {type(exc).__name__}: {exc}")
    observed_failure = None
    try:
        validate_episode_selection(expected_failure, prepared)
    except BridgeFailure as exc:
        observed_failure = str(exc).split(":", 1)[0]
    if observed_failure != fixture.get("expected_failure_label"):
        failures.append("typed expected failure mismatch")

    rank_depth_cases = {}
    observed_rank_failure = None
    for case in rank_depth_fixture.get("cases", []):
        try:
            rank, state, _ = verify_target_rank_claim(
                case["episode"],
                case["ranked_rows"],
                published_rank_depth=rank_depth_fixture["published_rank_depth"],
                trace_id=case["case_id"],
            )
            rank_depth_cases[case["case_id"]] = {"rank": rank, "state": state}
        except Failure as exc:
            label = str(exc).split(":", 1)[0]
            if case.get("expected_failure") == label:
                observed_rank_failure = label
            else:
                failures.append(f"unexpected rank-depth fixture failure: {case['case_id']}:{label}")
    if observed_rank_failure != fixture.get("rank_depth_expected_failure_label"):
        failures.append("rank-depth expected failure mismatch")

    try:
        beauty = verify(read(BEAUTY))
    except Exception as exc:
        beauty = {}
        failures.append(f"Beauty regression failed: {type(exc).__name__}: {exc}")
    beauty_evidence = evidence.get("beauty_v1_regression", {})
    if beauty_evidence.get("bundle_sha256") != sha256_file(BEAUTY):
        failures.append("Beauty bundle hash mismatch")
    if beauty.get("status") != "pass" or beauty.get("episodes") != 5:
        failures.append("Beauty verifier regression mismatch")

    tool_paths = {
        "prepared_bridge_sha256": ROOT / "tools/rpg_non_ar_bridge.py",
        "runner_sha256": ROOT / "tools/run_rpg_resumable_training.py",
        "finalizer_sha256": ROOT / "tools/finalize_rpg_prepared_dataset.py",
        "exporter_sha256": ROOT / "tools/export_rpg_trained_trace.py",
        "trained_trace_verifier_sha256": ROOT / "tools/verify_rpg_trained_trace_bundle.py",
    }
    for key, path in tool_paths.items():
        if evidence.get("tools", {}).get(key) != sha256_file(path):
            failures.append(f"tool hash mismatch: {key}")
    runtime = evidence.get("runtime_smoke", {})
    if runtime.get("status") != "pass" or runtime.get("verifier_status") != "pass":
        failures.append("runtime smoke status mismatch")
    if runtime.get("gpu_required") is not False or runtime.get("device") != "cpu":
        failures.append("runtime smoke must remain CPU-only")
    rank_depth_runtime = evidence.get("rank_depth_runtime_smoke", {})
    if (
        rank_depth_runtime.get("status") != "pass"
        or rank_depth_runtime.get("schema") != "sidscope.rpg_rank_depth_diagnostic.v1"
    ):
        failures.append("rank-depth runtime smoke status/schema mismatch")
    if (
        rank_depth_runtime.get("gpu_required") is not False
        or rank_depth_runtime.get("device") != "cpu"
    ):
        failures.append("rank-depth runtime smoke must remain CPU-only")
    if (
        rank_depth_runtime.get("requested_published_rank_depth") != 100
        or rank_depth_runtime.get("published_rank_depth") != 2
        or rank_depth_runtime.get("evaluation_cutoff") != 2
        or rank_depth_runtime.get("publication_scope")
        != "complete_resolved_final_frontier"
    ):
        failures.append("rank-depth runtime publication contract mismatch")
    if (
        rank_depth_runtime.get("target_rank_state") != "target_not_in_published_depth"
        or rank_depth_runtime.get("target_rank_lower_bound") != 3
        or rank_depth_runtime.get("right_censored_target_rank_count") != 1
    ):
        failures.append("rank-depth runtime censoring mismatch")
    for key in (
        "checkpoint_sha256",
        "prepared_dataset_contract_sha256",
        "trace_sha256",
        "verification_sha256",
        "handoff_sha256",
    ):
        value = rank_depth_runtime.get(key)
        if not isinstance(value, str) or len(value) != 64:
            failures.append(f"rank-depth runtime hash invalid: {key}")
    recovery = evidence.get("interrupted_resume_smoke", {})
    if recovery.get("status") != "pass":
        failures.append("interrupted resume smoke status mismatch")
    if recovery.get("gpu_required") is not False or recovery.get("device") != "cpu":
        failures.append("interrupted resume smoke must remain CPU-only")
    if recovery.get("checkpoint_schema") != "sidscope.rpg_resumable_state.v2":
        failures.append("interrupted resume checkpoint schema mismatch")
    if recovery.get("epoch_ledger_schema") != "sidscope.rpg_epoch_ledger.v1":
        failures.append("interrupted resume ledger schema mismatch")
    if recovery.get("final_manifest_schema") != "sidscope.rpg_trained_closure_run.v1":
        failures.append("interrupted resume final manifest schema mismatch")
    if recovery.get("completed_epochs") != [1, 2] or recovery.get("global_steps") != [1, 2]:
        failures.append("interrupted resume continuity mismatch")
    model_hashes = recovery.get("model_state_sha256", [])
    if len(model_hashes) != 2 or any(
        not isinstance(value, str) or len(value) != 64 for value in model_hashes
    ):
        failures.append("interrupted resume model-state hashes invalid")
    if recovery.get("resume_epoch_record_source") != "checkpoint_embedded":
        failures.append("interrupted resume did not recover checkpoint records")
    if recovery.get("resume_prior_manifest_sha256") is not None:
        failures.append("interrupted resume unexpectedly used a final manifest")
    if recovery.get("resume_prior_epoch_ledger_status") != "exact":
        failures.append("interrupted resume ledger was not checkpoint-bound")
    if recovery.get("stage1_invocation_manifest_removed_before_resume") is not True:
        failures.append("interrupted resume simulation boundary missing")
    for key in (
        "resume_input_sha256",
        "stage1_invocation_manifest_sha256",
        "final_manifest_sha256",
        "final_epoch_ledger_sha256",
        "final_last_state_sha256",
        "source_model_sha256",
    ):
        value = recovery.get(key)
        if not isinstance(value, str) or len(value) != 64:
            failures.append(f"interrupted resume hash invalid: {key}")

    result = {
        "schema": "sidscope.rpg_non_ar_bridge_verification.v1",
        "status": "pass" if not failures else "fail",
        "source_revision": evidence.get("source", {}).get("revision"),
        "prepared_dataset_contract_sha256": canonical_hash(prepared),
        "episode_selection_manifest_sha256": canonical_hash(selection),
        "positive_fixture": {
            "status": positive.get("status"),
            "episodes": positive.get("episodes"),
            "handoff_rows": positive.get("downstream_handoff", {}).get("episode_count"),
        },
        "expected_failure_label": observed_failure,
        "rank_depth_fixture": {
            "cases": rank_depth_cases,
            "expected_failure_label": observed_rank_failure,
        },
        "beauty_regression": {
            "status": beauty.get("status"),
            "episodes": beauty.get("episodes"),
            "target_universe_rows": beauty.get("target_universe_rows"),
        },
        "runtime_smoke": runtime,
        "rank_depth_runtime_smoke": rank_depth_runtime,
        "interrupted_resume_smoke": {
            "status": recovery.get("status"),
            "completed_epochs": recovery.get("completed_epochs"),
            "global_steps": recovery.get("global_steps"),
            "epoch_record_source": recovery.get("resume_epoch_record_source"),
            "prior_manifest_sha256": recovery.get("resume_prior_manifest_sha256"),
        },
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
