#!/usr/bin/env python3
"""Verify the bounded RPG source audit and parallel-generator contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.adapters.rpg import (  # noqa: E402
    RPGContractError,
    canonical_unordered_token_set,
    run_deterministic_graph_fixture,
)


AUDIT = ROOT / "docs/reproducibility/rpg_kdd2025_source_audit.json"
FIXTURE = ROOT / "examples/rpg_generator_fixture/manifest.json"
OFFICIAL_SMOKE = ROOT / "docs/reproducibility/rpg_kdd2025_official_source_smoke.json"
STATUS = ROOT / "docs/reproducibility/rpg_kdd2025_adapter_status.json"
BUILD = ROOT / "docs/reproducibility/rpg_beauty_cache_build.json"
INTAKE = ROOT / "docs/reproducibility/rpg_beauty_intake.json"
CONFORMANCE = ROOT / "docs/reproducibility/conformance/rpg_beauty_report.json"
PINNED_REVISION = "7dcf95ce9e08601810efdd1c850ed6dada5f97c2"


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
    smoke = _read_json(OFFICIAL_SMOKE)
    status = _read_json(STATUS)
    build = _read_json(BUILD)
    intake = _read_json(INTAKE)
    conformance = _read_json(CONFORMANCE)

    if audit.get("schema") != "sidscope.generator_source_audit.v1":
        failures.append("source audit schema mismatch")
    source = audit.get("source", {})
    if source.get("revision") != PINNED_REVISION:
        failures.append("source audit revision mismatch")
    if source.get("license_identifier") != "CC-BY-NC-4.0":
        failures.append("source audit must preserve the CC-BY-NC-4.0 code boundary")
    assets = audit.get("asset_audit", {})
    for field in ("checkpoint_found", "semantic_id_cache_found", "processed_dataset_found"):
        if assets.get(field) is not False:
            failures.append(f"source audit must not claim released {field}")
    external = audit.get("external_input_audit", {})
    if external.get("beauty_reviews", {}).get("sha256") != (
        "e5925ec99023f1dc9c7d3dff7ef34cfeacd40d1b981b5525e1e4ba9c8abc18fe"
    ):
        failures.append("Beauty review input hash mismatch")
    if external.get("beauty_metadata", {}).get("sha256") != (
        "c7977dc0e0ead14ac7df8c1c6de74da00e4bebfad87a0f0c5763d4c5bc9b53a0"
    ):
        failures.append("Beauty metadata input hash mismatch")
    if external.get("sentence_transformer", {}).get("revision") != (
        "fc5d4628481afbbaaacd7af6bb07cf9d3865f781"
    ):
        failures.append("Sentence-T5 revision mismatch")
    if fixture.get("source", {}).get("revision") != PINNED_REVISION:
        failures.append("fixture is not bound to the pinned source revision")

    try:
        trace = run_deterministic_graph_fixture(fixture)
    except Exception as exc:
        trace = {}
        failures.append(f"positive CPU fixture failed: {type(exc).__name__}: {exc}")
    else:
        if trace.get("decode_state_kind") != "unordered_token_set_graph_propagation":
            failures.append("fixture flattened the method-specific parallel decode state")
        if [row.get("normalized_item_id") for row in trace.get("ranked_items", [])] != ["2", "1"]:
            failures.append("fixture ranked-item export mismatch")
        if trace.get("ambiguity", {}).get("token_set_collision_count") != 1:
            failures.append("fixture did not preserve duplicate-token-set ambiguity")
        if "prefix_depth" in json.dumps(trace, sort_keys=True):
            failures.append("RPG fixture must not expose autoregressive prefix depth")

    expected_failure = fixture.get("expected_failure", {})
    observed_failure = None
    try:
        canonical_unordered_token_set(
            expected_failure.get("predicted_token_set", []),
            n_codebooks=int(fixture["configuration"]["n_codebooks"]),
            codebook_size=int(fixture["configuration"]["codebook_size"]),
        )
    except RPGContractError as exc:
        observed_failure = exc.label
    if observed_failure != expected_failure.get("failure_label"):
        failures.append(
            "expected-failure fixture mismatch: "
            f"expected={expected_failure.get('failure_label')!r} observed={observed_failure!r}"
        )

    if smoke.get("schema") != "sidscope.rpg_official_source_smoke.v1" or smoke.get("status") != "pass":
        failures.append("official-source CPU smoke snapshot does not pass")
    if smoke.get("source_revision") != PINNED_REVISION:
        failures.append("official-source smoke revision mismatch")
    if smoke.get("source_model_sha256") != "8d70fa9fde44279b3d0da9409e8e877b46ca4388d79442a2659d615336de6abc":
        failures.append("official-source smoke model hash mismatch")
    if smoke.get("outputs", {}).get("graph_ranked_item_ids") != [[2, 1]]:
        failures.append("official-source smoke ranked-item output mismatch")

    expected_counts = {
        "users": 22363,
        "items": 12101,
        "interactions": 198502,
        "training_items": 12068,
        "metadata_items": 12101,
    }
    if build.get("status") != "pass" or build.get("source_revision") != PINNED_REVISION:
        failures.append("real Beauty cache build report mismatch")
    if build.get("counts") != expected_counts:
        failures.append("real Beauty cache build counts mismatch")
    cache_hash = build.get("output_sha256", {}).get(
        "sentence-t5-base_OPQ32,IVF1,PQ32x8.sem_ids"
    )
    replay = build.get("deterministic_replay", {})
    if (
        not isinstance(cache_hash, str)
        or replay.get("status") != "pass"
        or replay.get("cache_sha256_first_build") != cache_hash
        or replay.get("cache_sha256_replay") != cache_hash
    ):
        failures.append("real Beauty cache deterministic replay mismatch")
    if intake.get("status") != "pass" or intake.get("source_sha256", {}).get(
        "sentence-t5-base_OPQ32,IVF1,PQ32x8.sem_ids"
    ) != cache_hash:
        failures.append("normalized intake is not bound to the frozen RPG cache")
    if intake.get("rows") != {
        "sid_assignments": 12101,
        "item_metadata": 12101,
        "interactions": 198502,
    }:
        failures.append("normalized RPG intake row counts mismatch")
    roundtrip = intake.get("roundtrip", {})
    if roundtrip.get("checked_items") != 12101 or any(
        roundtrip.get(field) != "pass"
        for field in (
            "source_item_to_normalized_item",
            "normalized_item_to_sid",
            "sid_to_model_vocabulary",
            "model_vocabulary_to_item_nodes",
        )
    ):
        failures.append("real RPG cache G1 identity round-trip mismatch")
    if (
        roundtrip.get("unique_unordered_token_sets") != 12099
        or roundtrip.get("colliding_token_set_count") != 2
        or roundtrip.get("items_in_collision_groups") != 4
    ):
        failures.append("real RPG collision accounting mismatch")
    if conformance.get("status") != "pass" or conformance.get("failed_levels") != []:
        failures.append("real RPG cache C0-C5 report does not pass")

    gates = {
        "C0_C5": "pass_official_code_derived_beauty_cache_non_paper_counted_summary_only",
        "G0": "pass_with_noncommercial_reuse_restriction",
        "G1": "pass_real_official_beauty_item_sid_vocabulary_item_node_roundtrip",
        "G2": "bounded_fixture_parallel_state_pass",
        "G3": "bounded_fixture_validity_ambiguity_resolution_pass",
        "G4": "bounded_fixture_trace_and_ranked_export_pass",
        "G5": "partial_real_cache_cpu_fixture_and_official_source_untrained_smoke_pass_trained_asset_smoke_pending",
    }
    input_sha256 = {
        "source_audit": _sha256(AUDIT),
        "fixture_manifest": _sha256(FIXTURE),
        "official_source_smoke": _sha256(OFFICIAL_SMOKE),
        "cache_build_report": _sha256(BUILD),
        "normalized_intake": _sha256(INTAKE),
        "c0_c5_report": _sha256(CONFORMANCE),
    }
    if status.get("schema") != "sidscope.rpg_generator_adapter_status.v1":
        failures.append("adapter status schema mismatch")
    if status.get("gates") != gates:
        failures.append("adapter status G0-G5 fields differ from the executable verifier")
    if status.get("input_sha256") != input_sha256:
        failures.append("adapter status input hashes differ from current evidence")
    promotion = status.get("promotion", {})
    if promotion.get("named_adapter") is not False or promotion.get("decision") != "close_named_adapter":
        failures.append("adapter status promotion boundary mismatch")
    if status.get("verified_outputs", {}).get("expected_failure_label") != observed_failure:
        failures.append("adapter status expected-failure label mismatch")

    result = {
        "schema": "sidscope.rpg_generator_adapter_verification.v1",
        "status": "pass" if not failures else "fail",
        "route_id": "rpg_kdd2025",
        "source_revision": PINNED_REVISION,
        "gates": gates,
        "promotion": {
            "named_adapter": False,
            "reason": "The real official-data static cache now passes C0-C5 and G1, but no trained checkpoint or fully recorded official training output has passed G2-G5.",
        },
        "fixture": {
            "trace_schema": trace.get("schema"),
            "ranked_item_ids": [row.get("normalized_item_id") for row in trace.get("ranked_items", [])],
            "collision_count": trace.get("ambiguity", {}).get("token_set_collision_count"),
            "expected_failure_label": observed_failure,
            "real_cache_checked_items": roundtrip.get("checked_items"),
            "real_cache_collision_count": roundtrip.get("colliding_token_set_count"),
        },
        "official_source_smoke": {
            "status": smoke.get("status"),
            "runtime": smoke.get("runtime"),
            "boundary": smoke.get("boundary"),
        },
        "input_sha256": input_sha256,
        "adapter_status_sha256": _sha256(STATUS),
        "failures": failures,
    }
    return result


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
