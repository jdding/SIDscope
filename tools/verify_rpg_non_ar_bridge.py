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
from tools.verify_rpg_trained_trace_bundle import verify  # noqa: E402


FIXTURE = ROOT / "examples/rpg_non_ar_bridge_fixture"
EVIDENCE = ROOT / "docs/reproducibility/rpg_non_ar_bridge_smoke.json"
BEAUTY = ROOT / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"


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
        "verifier_sha256": ROOT / "tools/verify_rpg_trained_trace_bundle.py",
    }
    for key, path in tool_paths.items():
        if evidence.get("tools", {}).get(key) != sha256_file(path):
            failures.append(f"tool hash mismatch: {key}")
    runtime = evidence.get("runtime_smoke", {})
    if runtime.get("status") != "pass" or runtime.get("verifier_status") != "pass":
        failures.append("runtime smoke status mismatch")
    if runtime.get("gpu_required") is not False or runtime.get("device") != "cpu":
        failures.append("runtime smoke must remain CPU-only")

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
        "beauty_regression": {
            "status": beauty.get("status"),
            "episodes": beauty.get("episodes"),
            "target_universe_rows": beauty.get("target_universe_rows"),
        },
        "runtime_smoke": runtime,
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
