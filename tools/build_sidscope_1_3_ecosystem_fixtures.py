#!/usr/bin/env python3
"""Build deterministic native-payload, profile, and SDK 0.2 fixtures."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import with_content_sha256
from sidinspector.trace.native_payloads import FAMILY_SCHEMAS


OUT = ROOT / "examples/native_trace_payload_fixtures"
SCHEMAS = ROOT / "src/sidinspector/schemas"
ZERO = "0" * 64


def topk(*tokens: int) -> list[dict[str, Any]]:
    return [
        {"rank": index + 1, "token_id": token, "logprob": -0.1 * (index + 1)}
        for index, token in enumerate(tokens)
    ]


def resolution(raw: list[int], item: int = 7) -> dict[str, Any]:
    return {
        "raw_sid": raw,
        "raw_valid": True,
        "resolved_normalized_item_id": item,
        "collision_count": 1,
    }


def base(family: str, episode: dict[str, Any]) -> dict[str, Any]:
    return with_content_sha256(
        {
            "schema": FAMILY_SCHEMAS[family],
            "schema_revision": "1.0.0",
            "payload_id": f"fixture:{family}",
            "method_family": family,
            "episodes": [episode],
            "privacy": {
                "source_user_ids_exported": False,
                "source_item_ids_exported": False,
                "absolute_private_paths_exported": False,
            },
        }
    )


def payloads() -> dict[str, dict[str, Any]]:
    return {
        "autoregressive_prefix": base(
            "autoregressive_prefix",
            {
                "episode_id": "episode-0",
                "beams": [
                    {
                        "beam_id": "beam-0",
                        "parent_beam_id": None,
                        "steps": [
                            {
                                "step_index": 0,
                                "prefix_before": [],
                                "topk": topk(10, 11),
                                "selected_token_id": 10,
                                "prefix_after": [10],
                            },
                            {
                                "step_index": 1,
                                "prefix_before": [10],
                                "topk": topk(20, 21),
                                "selected_token_id": 20,
                                "prefix_after": [10, 20],
                            },
                        ],
                        "retained": True,
                    }
                ],
                "resolution_events": [resolution([10, 20])],
                "termination_state": "success",
                "failure_state": None,
            },
        ),
        "parallel_graph_token_set": base(
            "parallel_graph_token_set",
            {
                "episode_id": "episode-0",
                "attempts": [
                    {
                        "attempt_index": 0,
                        "parallel_position_scores": [
                            {"position": 0, "topk": topk(1, 2)},
                            {"position": 1, "topk": topk(3, 4)},
                        ],
                        "retained_token_sets": [[1, 3], [2, 3]],
                        "visited_item_nodes": [7, 8],
                        "expanded_item_frontier": [7, 8],
                    }
                ],
                "resolution_events": [resolution([1, 3])],
                "termination_state": "success",
                "failure_state": None,
            },
        ),
        "masked_diffusion": base(
            "masked_diffusion",
            {
                "episode_id": "episode-0",
                "steps": [
                    {
                        "step_index": 0,
                        "mask_positions_before": [0, 1],
                        "mask_positions_after": [1],
                        "position_topk": [{"position": 0, "topk": topk(5, 6)}],
                        "selected_positions": [0],
                        "selected_order": [0],
                        "retained_beams": ["beam-0"],
                        "pruned_beams": [],
                    },
                    {
                        "step_index": 1,
                        "mask_positions_before": [1],
                        "mask_positions_after": [],
                        "position_topk": [{"position": 1, "topk": topk(9, 10)}],
                        "selected_positions": [1],
                        "selected_order": [1],
                        "retained_beams": ["beam-0"],
                        "pruned_beams": [],
                    },
                ],
                "final_raw_tuples": [[5, 9]],
                "resolution_events": [resolution([5, 9])],
                "termination_state": "success",
                "failure_state": None,
            },
        ),
        "latent_retry": base(
            "latent_retry",
            {
                "episode_id": "episode-0",
                "retries": [
                    {
                        "retry_index": 0,
                        "latent_state_sha256": "1" * 64,
                        "beams": [{"beam_id": "beam-0", "ordered_tokens": [4, 6], "score": -0.2}],
                        "accepted": True,
                        "failure_state": None,
                    }
                ],
                "resolution_events": [resolution([4, 6])],
                "termination_state": "success",
                "failure_state": None,
            },
        ),
        "decoder_overlay": base(
            "decoder_overlay",
            {
                "episode_id": "episode-0",
                "base_ranked_items": [
                    {"rank": 1, "normalized_item_id": 7, "score": 0.8},
                    {"rank": 2, "normalized_item_id": 8, "score": 0.7},
                ],
                "overlay_support": [
                    {"normalized_item_id": 8, "support_source": "catalog_prefix", "support_score": 0.4}
                ],
                "fused_ranked_items": [
                    {"rank": 1, "normalized_item_id": 8, "score": 1.1},
                    {"rank": 2, "normalized_item_id": 7, "score": 0.8},
                ],
                "resolution_events": [resolution([2, 8], 8)],
                "termination_state": "success",
                "failure_state": None,
            },
        ),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def schema_document(family: str, schema_id: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://sidscope.dev/schemas/{family}.v1.schema.json",
        "title": f"SIDScope {family} native trace payload",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema", "schema_revision", "payload_id", "method_family", "episodes", "privacy", "content_sha256"],
        "properties": {
            "schema": {"const": schema_id},
            "schema_revision": {"const": "1.0.0"},
            "payload_id": {"type": "string", "minLength": 1},
            "method_family": {"const": family},
            "episodes": {"type": "array", "minItems": 1},
            "privacy": {"type": "object"},
            "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
    }


def profile_registry() -> dict[str, Any]:
    common_gates = [
        {"gate_id": "binding_integrity", "owner": "core:contracts", "depends_on": [], "failure_code": "binding_mismatch"},
        {"gate_id": "capability_coverage", "owner": "core:sdk", "depends_on": ["binding_integrity"], "failure_code": "capability_mismatch"},
        {"gate_id": "privacy_boundary", "owner": "core:contracts", "depends_on": ["binding_integrity"], "failure_code": "privacy_boundary_violation"},
        {"gate_id": "resolution_integrity", "owner": "core:evaluation", "depends_on": ["binding_integrity"], "failure_code": "resolution_mismatch"},
        {"gate_id": "termination_accounting", "owner": "core:trace", "depends_on": ["binding_integrity"], "failure_code": "termination_failure_mismatch"},
        {"gate_id": "censoring_integrity", "owner": "core:evaluation", "depends_on": ["termination_accounting"], "failure_code": "rank_state_mismatch"},
    ]
    family_gates = {
        "autoregressive_prefix": ("ancestry_integrity", "unknown_parent_beam"),
        "decoder_overlay": ("overlay_noninsertion", "provider_only_item_insertion"),
        "latent_retry": ("retry_provenance", "invalid_retry_order"),
        "masked_diffusion": ("unmask_transition", "invalid_mask_transition"),
        "parallel_graph_token_set": ("parallel_semantics", "synthetic_ancestry_forbidden"),
    }
    profiles = [
        {
            "profile_id": "common.generator.v1",
            "revision": "1.0.0",
            "extends": [],
            "method_family": None,
            "gates": common_gates,
        }
    ]
    for family, (gate_id, failure) in sorted(family_gates.items()):
        profiles.append(
            {
                "profile_id": f"family.{family}.v1",
                "revision": "1.0.0",
                "extends": ["common.generator.v1"],
                "method_family": family,
                "gates": [
                    {
                        "gate_id": gate_id,
                        "owner": "core:trace",
                        "depends_on": ["capability_coverage", "termination_accounting"],
                        "failure_code": failure,
                    }
                ],
            }
        )
    return with_content_sha256(
        {
            "schema": "sidscope.conformance_profile_registry.v1",
            "schema_revision": "1.0.0",
            "profiles": sorted(profiles, key=lambda row: row["profile_id"]),
        }
    )


def main() -> None:
    documents = payloads()
    for family, document in documents.items():
        write_json(OUT / f"{family}.json", document)
        write_json(SCHEMAS / f"trace_payload_{family}.v1.schema.json", schema_document(family, document["schema"]))

    ancestry = copy.deepcopy(documents["autoregressive_prefix"])
    ancestry["episodes"][0]["beams"][0]["parent_beam_id"] = "missing"
    write_json(OUT / "expected_failure_ancestry.json", with_content_sha256(ancestry))
    privacy = copy.deepcopy(documents["parallel_graph_token_set"])
    privacy["privacy"]["source_item_ids_exported"] = True
    write_json(OUT / "expected_failure_privacy.json", with_content_sha256(privacy))
    termination = copy.deepcopy(documents["latent_retry"])
    termination["episodes"][0]["failure_state"] = "retry_exhausted"
    write_json(OUT / "expected_failure_termination.json", with_content_sha256(termination))
    resolution_bad = copy.deepcopy(documents["decoder_overlay"])
    resolution_bad["episodes"][0]["resolution_events"][0]["collision_count"] = 0
    write_json(OUT / "expected_failure_resolution.json", with_content_sha256(resolution_bad))

    trace = json.loads((ROOT / "examples/canonical_pipeline_fixture/trace_envelope.json").read_text(encoding="utf-8"))
    trace["observations"][0]["target"]["exact_rank"] = None
    write_json(OUT / "expected_failure_censoring.json", with_content_sha256(trace))

    capabilities = with_content_sha256(
        {
            "schema": "sidscope.adapter_capabilities.v1",
            "schema_revision": "1.0.0",
            "sdk_compatibility": {"minimum": "0.2.0", "maximum_exclusive": "0.3.0"},
            "adapter_id": "fixture:parallel-plugin",
            "producer": {"name": "sidscope.fixture", "version": "1.3.0.dev0"},
            "method_family": "parallel_graph_token_set",
            "contract_types": ["trace-envelope"],
            "payload_schema": FAMILY_SCHEMAS["parallel_graph_token_set"],
            "telemetry": {
                "supported": ["graph_frontier", "parallel_position_scores", "resolution_events"],
                "unavailable": ["autoregressive_prefix_ancestry"],
            },
            "execution_boundary": "external_runtime",
            "runtime_requirements": [],
        }
    )
    write_json(OUT / "adapter_capabilities.v1.json", capabilities)
    capability_bad = copy.deepcopy(capabilities)
    capability_bad["payload_schema"] = FAMILY_SCHEMAS["autoregressive_prefix"]
    write_json(OUT / "expected_failure_capability.json", with_content_sha256(capability_bad))

    manifest = {
        "schema": "sidscope.adapter_fixture_manifest.v1",
        "cases": [
            *[
                {"case_id": f"positive_{family}", "validator": "native_payload", "path": f"{family}.json", "expected_status": "pass", "expected_failure": None}
                for family in sorted(documents)
            ],
            {"case_id": "negative_ancestry", "validator": "native_payload", "path": "expected_failure_ancestry.json", "expected_status": "fail", "expected_failure": "unknown_parent_beam"},
            {"case_id": "negative_privacy", "validator": "native_payload", "path": "expected_failure_privacy.json", "expected_status": "fail", "expected_failure": "privacy_boundary_violation"},
            {"case_id": "negative_termination", "validator": "native_payload", "path": "expected_failure_termination.json", "expected_status": "fail", "expected_failure": "termination_failure_mismatch"},
            {"case_id": "negative_resolution", "validator": "native_payload", "path": "expected_failure_resolution.json", "expected_status": "fail", "expected_failure": "resolution_collision_mismatch"},
            {"case_id": "negative_censoring", "validator": "trace_envelope", "path": "expected_failure_censoring.json", "expected_status": "fail", "expected_failure": "rank_state_mismatch"},
            {"case_id": "negative_capability", "validator": "adapter_capabilities", "path": "expected_failure_capability.json", "expected_status": "fail", "expected_failure": "payload_capability_mismatch"},
            {"case_id": "negative_binding", "validator": "payload_binding", "path": "parallel_graph_token_set.json", "binding": {"schema_id": FAMILY_SCHEMAS["parallel_graph_token_set"], "content_sha256": ZERO}, "expected_status": "fail", "expected_failure": "payload_binding_mismatch"},
        ],
    }
    write_json(OUT / "fixture_manifest.json", manifest)

    registry_rows = []
    negative_by_family = {
        "autoregressive_prefix": [("expected_failure_ancestry.json", "unknown_parent_beam")],
        "parallel_graph_token_set": [("expected_failure_privacy.json", "privacy_boundary_violation")],
        "masked_diffusion": [],
        "latent_retry": [("expected_failure_termination.json", "termination_failure_mismatch")],
        "decoder_overlay": [("expected_failure_resolution.json", "resolution_collision_mismatch")],
    }
    for family, schema_id in sorted(FAMILY_SCHEMAS.items()):
        registry_rows.append(
            {
                "method_family": family,
                "schema_id": schema_id,
                "schema_revision": "1.0.0",
                "schema_resource": f"trace_payload_{family}.v1.schema.json",
                "canonical_fixture": f"examples/native_trace_payload_fixtures/{family}.json",
                "negative_fixtures": [
                    {"path": f"examples/native_trace_payload_fixtures/{path}", "expected_failure": failure}
                    for path, failure in negative_by_family[family]
                ],
            }
        )
    write_json(
        SCHEMAS / "trace_payload_registry.v1.json",
        with_content_sha256(
            {
                "schema": "sidscope.trace_payload_registry.v1",
                "schema_revision": "1.0.0",
                "payload_contracts": registry_rows,
            }
        ),
    )
    write_json(SCHEMAS / "conformance_profile_registry.v1.json", profile_registry())
    write_json(
        SCHEMAS / "adapter_capabilities.v1.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://sidscope.dev/schemas/adapter_capabilities.v1.schema.json",
            "title": "SIDScope Adapter Capabilities v1",
            "type": "object",
            "additionalProperties": False,
            "required": ["schema", "schema_revision", "sdk_compatibility", "adapter_id", "producer", "method_family", "contract_types", "payload_schema", "telemetry", "execution_boundary", "runtime_requirements", "content_sha256"],
            "properties": {"schema": {"const": "sidscope.adapter_capabilities.v1"}, "schema_revision": {"const": "1.0.0"}, "content_sha256": {"type": "string"}},
        },
    )
    print(json.dumps({"status": "pass", "payload_families": 5, "fixture_cases": len(manifest["cases"])}, sort_keys=True))


if __name__ == "__main__":
    main()
