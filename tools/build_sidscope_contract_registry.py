#!/usr/bin/env python3
"""Deterministically build the authoritative 1.2 canonical contract registry."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts.hashing import with_content_sha256


OUTPUT = ROOT / "src/sidinspector/schemas/contract_registry.v1.json"
FIXTURE = "examples/canonical_pipeline_fixture"


def descriptor(
    contract_type: str,
    schema_id: str,
    schema_resource: str,
    fixture_name: str,
    result_id_field: str,
    negative_name: str,
    expected_failure: str,
    dependencies: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "contract_type": contract_type,
        "schema_id": schema_id,
        "schema_revision": "1.0.0",
        "owner": "core:contracts",
        "schema_resource": schema_resource,
        "compatibility": {
            "policy": "exact_major_supported_revision",
            "supported_revisions": ["1.0.0"],
        },
        "canonical_fixture": f"{FIXTURE}/{fixture_name}",
        "negative_fixtures": [
            {
                "path": f"{FIXTURE}/{negative_name}",
                "expected_failure": expected_failure,
            }
        ],
        "dependencies": [
            {"schema_id": schema, "accepted_revisions": ["1.0.0"]}
            for schema in sorted(dependencies)
        ],
        "result_id_field": result_id_field,
    }


NEW_DESCRIPTORS = (
    descriptor(
        "checkpoint-binding", "sidscope.checkpoint_binding.v1",
        "checkpoint_binding.v1.schema.json", "checkpoint_binding.json", "checkpoint_id",
        "expected_failure_incomplete_resumable_state.json", "incomplete_resumable_state",
        ("sidscope.run_identity.v1",),
    ),
    descriptor(
        "conformance-report", "sidscope.conformance_report.v1",
        "conformance_report.v1.schema.json", "conformance_report.json", "conformance_report_id",
        "expected_failure_gate_order.json", "noncanonical_gate_order",
        ("sidscope.diagnostic_report.v1", "sidscope.trace_envelope.v1"),
    ),
    descriptor(
        "diagnostic-report", "sidscope.diagnostic_report.v1",
        "diagnostic_report.v1.schema.json", "diagnostic_report.json", "diagnostic_report_id",
        "expected_failure_metric_mismatch.json", "metric_out_of_range",
        ("sidscope.episode_selection.v1", "sidscope.trace_envelope.v1"),
    ),
    descriptor(
        "episode-selection", "sidscope.episode_selection.v1",
        "episode_selection.v1.schema.json", "episode_selection.json", "selection_id",
        "expected_failure_duplicate_episode.json", "duplicate_episode_id",
        ("sidscope.prepared_dataset.v1",),
    ),
    descriptor(
        "evidence-index", "sidscope.evidence_index.v1",
        "evidence_index.v1.schema.json", "evidence_index.json", "evidence_index_id",
        "expected_failure_evidence_cycle.json", "evidence_cycle",
        ("sidscope.conformance_report.v1",),
    ),
    descriptor(
        "run-identity", "sidscope.run_identity.v1",
        "run_identity.v1.schema.json", "run_identity.json", "run_id",
        "expected_failure_invalid_seed.json", "invalid_seed",
        ("sidscope.prepared_dataset.v1", "sidscope.source_identity.v1"),
    ),
    descriptor(
        "trace-envelope", "sidscope.trace_envelope.v1",
        "trace_envelope.v1.schema.json", "trace_envelope.json", "trace_envelope_id",
        "expected_failure_rank_state.json", "rank_state_mismatch",
        (
            "sidscope.checkpoint_binding.v1",
            "sidscope.episode_selection.v1",
            "sidscope.run_identity.v1",
        ),
    ),
)


def build_registry() -> dict[str, object]:
    current = json.loads(OUTPUT.read_text(encoding="utf-8"))
    replacements = {row["contract_type"]: row for row in NEW_DESCRIPTORS}
    for row in current["contracts"]:
        replacements.setdefault(row["contract_type"], row)
    return with_content_sha256(
        {
            "schema": "sidscope.contract_registry.v1",
            "schema_revision": "1.0.0",
            "registry_id": "sidscope-core-contracts",
            "producer": {"name": "sidinspector.contracts", "version": "1.2.0.dev0"},
            "contracts": [replacements[key] for key in sorted(replacements)],
        }
    )


def main() -> None:
    document = build_registry()
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "contracts": len(document["contracts"]), "content_sha256": document["content_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
