#!/usr/bin/env python3
"""Verify the frozen Latte/PSID cache evidence and bounded adapter contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from sidinspector.adapters.latte import (
    LatteCacheContractError,
    export_latte_trace,
    normalize_latte_interactions,
    normalize_latte_metadata,
    normalize_latte_sem_ids,
    read_latte_item_mapping,
    read_sem_ids_cache,
    validate_latte_psid_trained_trace_bundle,
)
from sidinspector.preflight import build_metric_smoke_summary


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "examples/latte_psid_cache_fixture"
FIXTURE = FIXTURE_DIR / "manifest.json"
AUDIT = ROOT / "docs/reproducibility/latte_psid_source_audit.json"
SMOKE = ROOT / "docs/reproducibility/latte_psid_official_source_smoke.json"
BUILD = ROOT / "docs/reproducibility/latte_psid_musical_cache_build.json"
INTAKE = ROOT / "docs/reproducibility/latte_psid_musical_intake.json"
CONFORMANCE = ROOT / "docs/reproducibility/conformance/latte_psid_musical_report.json"
STATUS = ROOT / "docs/reproducibility/latte_psid_adapter_status.json"
TRAINED_TRACE_EVIDENCE = ROOT / "docs/reproducibility/latte_psid_trained_trace_evidence.json"
REAL_TRAINED_TRACE_SMOKES = {
    "PSID": ROOT
    / "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json",
    "Latte": ROOT
    / "examples/latte_psid_trained_trace_real_smoke/latte_amazon_vg_1_per_bucket_s2024.json",
}
PINNED_REVISION = "05e4e6d983225bcb7172f148a076890e80c524d1"
DATASET_REVISION = "2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e"
MODEL_REVISION = "fc5d4628481afbbaaacd7af6bb07cf9d3865f781"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify() -> dict[str, object]:
    failures: list[str] = []
    fixture = load(FIXTURE)
    audit = load(AUDIT)
    smoke = load(SMOKE)
    build = load(BUILD)
    intake = load(INTAKE)
    conformance = load(CONFORMANCE)
    status = load(STATUS)
    trained_trace_evidence = load(TRAINED_TRACE_EVIDENCE)
    config = fixture["configuration"]
    paths = {key: FIXTURE_DIR / value for key, value in fixture["inputs"].items()}

    if audit.get("source", {}).get("revision") != PINNED_REVISION:
        failures.append("source audit revision mismatch")
    if audit.get("source", {}).get("license_identifier") != "MIT":
        failures.append("source audit code license mismatch")
    assets = audit.get("asset_audit", {})
    for field in ("checkpoint_found", "precomputed_sem_ids_found", "processed_dataset_found_in_source_repository"):
        if assets.get(field) is not False:
            failures.append(f"source audit must not claim released {field}")
    dataset = audit.get("external_sources", {}).get("dataset", {})
    if dataset.get("revision") != DATASET_REVISION or dataset.get("license_identifier") != "NOASSERTION":
        failures.append("dataset revision/license boundary mismatch")

    try:
        sid = normalize_latte_sem_ids(
            paths["sem_ids"],
            paths["item_mapping"],
            method="latte_psid_rqkmeans_fixture",
            dataset=config["dataset"],
            vq_method=config["vq_method"],
            n_codebooks=config["vq_n_codebooks"],
            codebook_size=config["vq_codebook_size"],
        )
        metadata = normalize_latte_metadata(
            paths["item_mapping"],
            dataset=config["dataset"],
            category=config["category"],
            metadata_path=paths["metadata"],
        )
        interactions = normalize_latte_interactions(
            paths["all_item_seqs"], paths["item_mapping"], dataset=config["dataset"]
        )
        metrics = build_metric_smoke_summary(
            sid, metadata, interactions, top_k=2, max_pair_events=100, max_user_items=10
        )
        identities = read_latte_item_mapping(paths["item_mapping"])
        cache = read_sem_ids_cache(
            paths["sem_ids"],
            expected_source_items=(item.source_item_id for item in identities),
            n_codebooks=config["vq_n_codebooks"],
            codebook_size=config["vq_codebook_size"],
        )
        trace = export_latte_trace(
            route_id=fixture["route_id"],
            trace_id="latte-fixture-001",
            split_id=config["split_id"],
            cache=cache,
            normalized_item_ids={item.source_item_id: item.normalized_item_id for item in identities},
            beams=fixture["beams"],
            codebook_size=config["vq_codebook_size"],
            n_latent_tokens=config["n_latent_tokens"],
            aggregation_method=config["aggregation_method"],
        )
    except Exception as exc:
        metrics = []
        trace = {}
        failures.append(f"positive fixture failed: {type(exc).__name__}: {exc}")

    if trace.get("decode_state_kind") != "latent_token_then_ordered_sid_prefix":
        failures.append("fixture lost Latte method-specific state")
    if [row.get("source_item_id") for row in trace.get("ranked_items", [])] != [
        "fixture-asin-a",
        "fixture-asin-b",
    ]:
        failures.append("fixture ranked-item aggregation mismatch")
    if not metrics or metrics[0].get("d1_level_count") != 3:
        failures.append("fixture D1-D5 smoke mismatch")

    expected_failure = fixture["expected_failure"]
    observed_failure = None
    with tempfile.TemporaryDirectory() as temp_dir:
        collision_path = Path(temp_dir) / "collision.sem_ids"
        collision_path.write_text(json.dumps(expected_failure["cache"]), encoding="utf-8")
        try:
            read_sem_ids_cache(
                collision_path,
                expected_source_items=expected_failure["cache"],
                n_codebooks=config["vq_n_codebooks"],
                codebook_size=config["vq_codebook_size"],
            )
        except LatteCacheContractError as exc:
            observed_failure = exc.label
    if observed_failure != expected_failure["failure_label"]:
        failures.append("expected-failure label mismatch")

    if smoke.get("status") != "pass" or smoke.get("source_revision") != PINNED_REVISION:
        failures.append("official-source method smoke mismatch")
    if build.get("status") != "pass" or build.get("source_revision") != PINNED_REVISION:
        failures.append("real cache build report mismatch")
    if build.get("dataset_revision") != DATASET_REVISION:
        failures.append("real cache dataset revision mismatch")
    if build.get("sentence_transformer_revision") != MODEL_REVISION:
        failures.append("real cache model revision mismatch")
    expected_counts = {
        "users": 57439,
        "items": 24587,
        "interactions": 511836,
        "training_items": 24556,
        "metadata_items": 24587,
    }
    if build.get("counts") != expected_counts:
        failures.append("real cache build counts mismatch")
    cache_name = "sentence-t5-base_rqkmeans_3x256_psid.sem_ids"
    cache_hash = build.get("output_sha256", {}).get(cache_name)
    if not isinstance(cache_hash, str) or len(cache_hash) != 64:
        failures.append("real cache SHA-256 is missing")
    if intake.get("status") != "pass" or intake.get("source_cache_sha256") != cache_hash:
        failures.append("normalized intake is not bound to the frozen cache")
    if intake.get("rows") != {
        "sid_assignments": 24587,
        "item_metadata": 24587,
        "interactions": 511836,
    }:
        failures.append("normalized intake row counts mismatch")
    roundtrip = intake.get("roundtrip", {})
    if roundtrip.get("checked_items") != 24587 or any(
        roundtrip.get(field) != "pass"
        for field in (
            "source_to_normalized_item",
            "normalized_item_to_sid",
            "sid_to_psid_vocabulary_to_source_item",
            "sid_to_latte_vocabulary_to_source_item",
        )
    ):
        failures.append("real cache G1 identity round-trip mismatch")
    if conformance.get("status") != "pass" or conformance.get("failed_levels") != []:
        failures.append("real cache C0-C5 report does not pass")

    if (
        trained_trace_evidence.get("schema") != "sidscope.latte_psid_trained_trace_evidence.v1"
        or trained_trace_evidence.get("status") != "pass"
        or trained_trace_evidence.get("gates")
        != {f"G{level}": "pass" for level in range(6)}
    ):
        failures.append("trained-trace evidence summary does not close G0-G5")
    source = trained_trace_evidence.get("source", {})
    if source.get("revision") != PINNED_REVISION or source.get("license") != "MIT":
        failures.append("trained-trace source identity mismatch")
    if source.get("sidscope_contract_commit") != "b07c071842d9780f0458deb94b597608b4c943dd":
        failures.append("trained-trace contract revision mismatch")

    trained_trace_results: dict[str, dict[str, object]] = {}
    for method, path in REAL_TRAINED_TRACE_SMOKES.items():
        try:
            result = validate_latte_psid_trained_trace_bundle(load(path))
            trained_trace_results[method] = result
        except Exception as exc:
            failures.append(f"real {method} trained-trace smoke failed: {type(exc).__name__}: {exc}")
            continue
        method_evidence = trained_trace_evidence.get("methods", {}).get(method, {})
        smoke_evidence = method_evidence.get("smoke", {})
        full_evidence = method_evidence.get("full", {})
        expected_failure = method_evidence.get("expected_failures", {})
        if sha256(path) != smoke_evidence.get("bundle_sha256"):
            failures.append(f"real {method} smoke hash mismatch")
        expected_smoke = {
            "episode_count": smoke_evidence.get("episodes"),
            "beam_row_count": smoke_evidence.get("beam_rows"),
            "checkpoint_sha256": method_evidence.get("checkpoint_sha256"),
            "target_universe_sha256": method_evidence.get("target_universe_sha256"),
            "target_universe_row_count": method_evidence.get("target_universe_rows"),
        }
        if any(result.get(field) != value for field, value in expected_smoke.items()):
            failures.append(f"real {method} smoke verification summary mismatch")
        if method == "PSID":
            if result.get("evaluation_slot_count") != smoke_evidence.get("evaluation_slots"):
                failures.append("real PSID evaluation-slot count mismatch")
            if full_evidence.get("invalid_evaluation_slots") != 4:
                failures.append("full PSID invalid evaluation slots were not retained")
        else:
            if result.get("retry_episode_count") != smoke_evidence.get("retry_episodes"):
                failures.append("real Latte retry count mismatch")
            if result.get("ranked_item_row_count") != smoke_evidence.get("ranked_item_rows"):
                failures.append("real Latte ranked-item count mismatch")
        if (
            full_evidence.get("verifier") != "pass"
            or full_evidence.get("episodes") != 250
            or full_evidence.get("episodes_per_bucket") != 50
            or full_evidence.get("redistributed") is not False
        ):
            failures.append(f"full {method} diagnostic boundary mismatch")
        if expected_failure.get("failure_label") != "missing_beam_ancestry":
            failures.append(f"real {method} expected-failure label mismatch")

    gates = {
        "C0_C5": "pass_official_code_derived_cache_non_paper_counted_summary_only",
        "G0": "pass_source_config_and_hash_bound_downstream_training_boundary",
        "G1": "pass_real_cache_item_sid_vocabulary_resolution_roundtrip",
        "G2": "pass_real_psid_ordered_beams_and_latte_latent_retry_state",
        "G3": "pass_typed_validity_collision_and_resolution_contract",
        "G4": "pass_real_deidentified_traces_psid_raw_slots_and_latte_dense_ranks",
        "G5": "pass_cpu_fixture_real_five_episode_smokes_250_episode_diagnostics_expected_failures_hashes_and_verifier",
    }
    evidence_hashes = {
        "source_audit": sha256(AUDIT),
        "fixture_manifest": sha256(FIXTURE),
        "official_source_smoke": sha256(SMOKE),
        "cache_build_report": sha256(BUILD),
        "normalized_intake": sha256(INTAKE),
        "c0_c5_report": sha256(CONFORMANCE),
        "trained_trace_evidence": sha256(TRAINED_TRACE_EVIDENCE),
        "real_psid_smoke_bundle": sha256(REAL_TRAINED_TRACE_SMOKES["PSID"]),
        "real_latte_smoke_bundle": sha256(REAL_TRAINED_TRACE_SMOKES["Latte"]),
    }
    if status.get("gates") != gates:
        failures.append("adapter status gates differ from verifier")
    if status.get("input_sha256") != evidence_hashes:
        failures.append("adapter status hashes differ from verifier")
    promotion = status.get("promotion", {})
    if promotion.get("named_adapter") is not True or promotion.get("decision") != "named_adapter":
        failures.append("named-adapter promotion boundary mismatch")

    return {
        "schema": "sidscope.latte_psid_adapter_verification.v1",
        "status": "pass" if not failures else "fail",
        "route_id": "latte_psid",
        "source_revision": PINNED_REVISION,
        "gates": gates,
        "frozen_cache_sha256": cache_hash,
        "fixture": {
            "trace_schema": trace.get("schema"),
            "ranked_source_items": [row.get("source_item_id") for row in trace.get("ranked_items", [])],
            "expected_failure_label": observed_failure,
        },
        "promotion": {
            "named_adapter": True,
            "reason": "Configuration-bound real PSID and Latte traces pass G0-G5 with public CPU smoke bundles.",
        },
        "real_trained_trace_results": trained_trace_results,
        "input_sha256": evidence_hashes,
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
