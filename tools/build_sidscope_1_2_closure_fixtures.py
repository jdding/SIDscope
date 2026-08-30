#!/usr/bin/env python3
"""Build the canonical end-to-end 1.2 pipeline and typed-negative fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import (
    canonical_sha256,
    diagnostic_report_document,
    from_legacy_adapter_manifest,
    load_contract_registry,
    load_dataset_identity,
    load_prepared_dataset,
    load_sid_space_identity,
    validate_checkpoint_binding,
    validate_conformance_report,
    validate_diagnostic_report,
    validate_episode_selection,
    validate_evidence_index,
    validate_run_identity,
    validate_trace_envelope,
    with_content_sha256,
)
from sidinspector.sdk import validate_adapter_capabilities


OUTPUT = ROOT / "examples/canonical_pipeline_fixture"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def binding(artifact: Any) -> dict[str, str]:
    return {
        "schema_id": artifact.schema,
        "schema_revision": artifact.schema_revision,
        "content_sha256": artifact.content_sha256,
    }


def build_documents() -> dict[str, dict[str, Any]]:
    legacy_manifest = json.loads(
        (ROOT / "docs/reproducibility/conformance/rpg_beauty_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    source = from_legacy_adapter_manifest(legacy_manifest)
    dataset = load_dataset_identity(
        ROOT / "examples/prepared_dataset_fixture/dataset_identity.json"
    )
    sid_space = load_sid_space_identity(
        ROOT / "examples/prepared_dataset_fixture/sid_space_identity.json"
    )
    prepared = load_prepared_dataset(
        ROOT / "examples/prepared_dataset_fixture/prepared_dataset.json"
    )
    legacy_prepared = json.loads(
        (ROOT / "examples/rpg_non_ar_bridge_fixture/prepared_dataset.json").read_text(
            encoding="utf-8"
        )
    )
    legacy_selection = json.loads(
        (ROOT / "examples/rpg_non_ar_bridge_fixture/episode_selection.json").read_text(
            encoding="utf-8"
        )
    )
    legacy_trace_path = ROOT / "examples/rpg_non_ar_bridge_fixture/trained_trace_v2.json"
    legacy_trace = json.loads(legacy_trace_path.read_text(encoding="utf-8"))

    selection_doc = with_content_sha256(
        {
            "schema": "sidscope.episode_selection.v1",
            "schema_revision": "1.0.0",
            "selection_id": "rpg:explicit-test-b-only",
            "producer": {"name": "sidinspector.contracts", "version": "1.2.0.dev0"},
            "prepared_dataset_binding": binding(prepared),
            "split": {
                "split_id": legacy_selection["test_split_id"],
                "sha256": legacy_selection["test_split_sha256"],
            },
            "policies": legacy_selection["policies"],
            "rows": [
                {
                    "order": row["order"],
                    "episode_id": row["episode_id"],
                    "split_row_index": row["split_row_index"],
                    "target_normalized_item_id": row["expected_target_normalized_item_id"],
                    "evaluator_labels": {"dormancy_bucket": "fixture"},
                }
                for row in legacy_selection["rows"]
            ],
        }
    )
    selection = validate_episode_selection(selection_doc)

    run_doc = with_content_sha256(
        {
            "schema": "sidscope.run_identity.v1",
            "schema_revision": "1.0.0",
            "run_id": "rpg:fixture-training-run",
            "producer": {"name": "sidinspector.contracts", "version": "1.2.0.dev0"},
            "run_kind": "training",
            "source_binding": binding(source),
            "prepared_dataset_binding": binding(prepared),
            "configuration_sha256": legacy_prepared["configuration_sha256"],
            "seed": legacy_prepared["configuration"]["model_seed"],
            "command_sha256": canonical_sha256(
                ["python", "tools/run_rpg_resumable_training.py", "<external-config>"]
            ),
            "environment_sha256": canonical_sha256(
                {"runtime": "external", "device": "cpu-fixture", "python": "3.9+"}
            ),
            "training_manifest_sha256": legacy_prepared["training"]["training_manifest_sha256"],
        }
    )
    run = validate_run_identity(run_doc)

    checkpoint_sha = legacy_prepared["training"]["checkpoint_sha256"]
    checkpoint_doc = with_content_sha256(
        {
            "schema": "sidscope.checkpoint_binding.v1",
            "schema_revision": "1.0.0",
            "checkpoint_id": "rpg:fixture-checkpoint-epoch-1",
            "producer": {"name": "sidinspector.contracts", "version": "1.2.0.dev0"},
            "run_binding": binding(run),
            "checkpoint_sha256": checkpoint_sha,
            "state_kind": "complete_resumable",
            "completed_epoch": 1,
            "global_step": 1,
            "state_sha256": {
                "model": checkpoint_sha,
                "optimizer": "c" * 64,
                "scheduler": "d" * 64,
                "rng": "e" * 64,
            },
            "epoch_ledger_sha256": "f" * 64,
            "previous_checkpoint_sha256": None,
        }
    )
    checkpoint = validate_checkpoint_binding(checkpoint_doc)

    episode = legacy_trace["episodes"][0]
    trace_doc = with_content_sha256(
        {
            "schema": "sidscope.trace_envelope.v1",
            "schema_revision": "1.0.0",
            "trace_envelope_id": "rpg:fixture-trace-envelope",
            "producer": {"name": "sidinspector.trace", "version": "1.2.0.dev0"},
            "episode_selection_binding": binding(selection),
            "run_binding": binding(run),
            "checkpoint_binding": binding(checkpoint),
            "method_family": "parallel_graph_token_set",
            "payload_schema": legacy_trace["schema"],
            "payload_sha256": file_sha256(legacy_trace_path),
            "observations": [
                {
                    "selection_order": episode["selection_order"],
                    "episode_id": episode["episode_id"],
                    "attempt_count": 1,
                    "termination_state": episode["termination_reason"],
                    "failure_state": None,
                    "target": {
                        "catalog_reachable": True,
                        "generated": True,
                        "resolved": True,
                        "rank_state": "exact",
                        "exact_rank": episode["target_rank"],
                        "rank_lower_bound": None,
                    },
                    "compute": {
                        "nfe": 1,
                        "forward_calls": 1,
                        "candidate_count": episode["visited_item_node_count"],
                        "latency_ms": 0,
                    },
                }
            ],
        }
    )
    trace = validate_trace_envelope(trace_doc)
    diagnostic_doc = diagnostic_report_document(
        trace, selection, evaluation_cutoff=10, publication_depth=100
    )
    diagnostic = validate_diagnostic_report(diagnostic_doc)

    conformance_doc = with_content_sha256(
        {
            "schema": "sidscope.conformance_report.v1",
            "schema_revision": "1.0.0",
            "conformance_report_id": "rpg:fixture-g0-g5",
            "producer": {"name": "sidinspector.conformance", "version": "1.2.0.dev0"},
            "profile": {
                "profile_id": "generator_g0_g5_fixture",
                "profile_revision": "1.0.0",
            },
            "trace_binding": binding(trace),
            "diagnostic_binding": binding(diagnostic),
            "verifier_sha256": file_sha256(ROOT / "tools/verify_rpg_non_ar_bridge.py"),
            "gates": [
                {"gate": f"G{index}", "status": "pass", "failure_code": None}
                for index in range(6)
            ],
            "decision": {
                "status": "fixture_pass",
                "scope": "contract_fixture_only_no_adapter_promotion",
            },
        }
    )
    conformance = validate_conformance_report(conformance_doc)

    core = {
        "source-identity": source,
        "dataset-identity": dataset,
        "sid-space-identity": sid_space,
        "prepared-dataset": prepared,
        "episode-selection": selection,
        "run-identity": run,
        "checkpoint-binding": checkpoint,
        "trace-envelope": trace,
        "diagnostic-report": diagnostic,
        "conformance-report": conformance,
    }
    registry = load_contract_registry()
    rows = []
    artifact_id_by_schema: dict[str, str] = {}
    for contract_type, artifact in core.items():
        descriptor = registry.by_type(contract_type)
        artifact_id = f"{contract_type}:{artifact.to_dict()[descriptor.result_id_field]}"
        artifact_id_by_schema[artifact.schema] = artifact_id
        rows.append(
            {
                "artifact_id": artifact_id,
                "role": contract_type,
                "schema_id": artifact.schema,
                "schema_revision": artifact.schema_revision,
                "content_sha256": artifact.content_sha256,
            }
        )
    rows.sort(key=lambda row: row["artifact_id"])
    edges = []
    for contract_type, artifact in core.items():
        descriptor = registry.by_type(contract_type)
        for dependency in descriptor.dependencies:
            edges.append(
                {
                    "from_artifact": artifact_id_by_schema[artifact.schema],
                    "to_artifact": artifact_id_by_schema[dependency.schema_id],
                    "relation": f"depends_on:{dependency.schema_id}",
                }
            )
    edges.sort(key=lambda row: (row["from_artifact"], row["to_artifact"], row["relation"]))
    evidence_doc = with_content_sha256(
        {
            "schema": "sidscope.evidence_index.v1",
            "schema_revision": "1.0.0",
            "evidence_index_id": "rpg:fixture-evidence-index",
            "producer": {"name": "sidinspector.evidence", "version": "1.2.0.dev0"},
            "artifacts": rows,
            "edges": edges,
            "omissions": [],
            "privacy": {
                "source_user_ids_exported": False,
                "source_item_ids_exported": False,
                "absolute_private_paths_exported": False,
            },
        }
    )
    validate_evidence_index(evidence_doc)

    capabilities_doc = with_content_sha256(
        {
            "schema": "sidscope.adapter_capabilities.alpha.v1",
            "sdk_version": "0.1.0",
            "adapter_id": "rpg:fixture-adapter",
            "producer": {"name": "sidscope.fixture", "version": "1.2.0.dev0"},
            "method_family": "parallel_graph_token_set",
            "contract_types": sorted(
                [
                    "checkpoint-binding", "episode-selection", "prepared-dataset",
                    "run-identity", "source-identity", "trace-envelope",
                ]
            ),
            "telemetry": {
                "supported": ["graph_frontier", "parallel_token_scores", "ranked_items"],
                "unavailable": ["autoregressive_prefix_ancestry"],
            },
            "execution_boundary": "external_runtime",
        }
    )
    validate_adapter_capabilities(capabilities_doc)

    documents = {
        "source_identity.json": source.to_dict(),
        "dataset_identity.json": dataset.to_dict(),
        "sid_space_identity.json": sid_space.to_dict(),
        "prepared_dataset.json": prepared.to_dict(),
        "episode_selection.json": selection.to_dict(),
        "run_identity.json": run.to_dict(),
        "checkpoint_binding.json": checkpoint.to_dict(),
        "trace_envelope.json": trace.to_dict(),
        "diagnostic_report.json": diagnostic.to_dict(),
        "conformance_report.json": conformance.to_dict(),
        "evidence_index.json": evidence_doc,
        "adapter_capabilities.json": capabilities_doc,
    }

    duplicate = json.loads(json.dumps(selection_doc))
    duplicate["rows"].append({**duplicate["rows"][0], "order": 1})
    documents["expected_failure_duplicate_episode.json"] = with_content_sha256(duplicate)
    invalid_seed = json.loads(json.dumps(run_doc))
    invalid_seed["seed"] = -1
    documents["expected_failure_invalid_seed.json"] = with_content_sha256(invalid_seed)
    incomplete = json.loads(json.dumps(checkpoint_doc))
    incomplete["state_sha256"]["optimizer"] = None
    documents["expected_failure_incomplete_resumable_state.json"] = with_content_sha256(incomplete)
    rank_state = json.loads(json.dumps(trace_doc))
    rank_state["observations"][0]["target"]["exact_rank"] = None
    documents["expected_failure_rank_state.json"] = with_content_sha256(rank_state)
    metric = json.loads(json.dumps(diagnostic_doc))
    metric["evaluation"]["hit_at_cutoff"] = 1.1
    documents["expected_failure_metric_mismatch.json"] = with_content_sha256(metric)
    gates = json.loads(json.dumps(conformance_doc))
    gates["gates"][0], gates["gates"][1] = gates["gates"][1], gates["gates"][0]
    documents["expected_failure_gate_order.json"] = with_content_sha256(gates)
    cycle = json.loads(json.dumps(evidence_doc))
    source_artifact = artifact_id_by_schema[source.schema]
    conformance_artifact = artifact_id_by_schema[conformance.schema]
    cycle["edges"].append(
        {
            "from_artifact": source_artifact,
            "to_artifact": conformance_artifact,
            "relation": "invalid_cycle_fixture",
        }
    )
    cycle["edges"].sort(
        key=lambda row: (row["from_artifact"], row["to_artifact"], row["relation"])
    )
    documents["expected_failure_evidence_cycle.json"] = with_content_sha256(cycle)
    telemetry = json.loads(json.dumps(capabilities_doc))
    telemetry["telemetry"]["unavailable"].append("graph_frontier")
    telemetry["telemetry"]["unavailable"].sort()
    documents["expected_failure_telemetry_overlap.json"] = with_content_sha256(telemetry)
    return documents


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    documents = build_documents()
    for name, document in documents.items():
        (OUTPUT / name).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps({"status": "pass", "files": len(documents)}, indent=2))


if __name__ == "__main__":
    main()
