"""External reference adapter used to prove entry-point integration."""

from __future__ import annotations

from typing import Any, Mapping

from sidinspector.contracts import with_content_sha256


def _topk(first: int, second: int) -> list[dict[str, Any]]:
    return [
        {"rank": 1, "token_id": first, "logprob": -0.1},
        {"rank": 2, "token_id": second, "logprob": -0.2},
    ]


class ReferenceAdapterPlugin:
    plugin_api_version = "1.0"

    def get_capabilities(self) -> Mapping[str, Any]:
        return with_content_sha256(
            {
                "schema": "sidscope.adapter_capabilities.v1",
                "schema_revision": "1.0.0",
                "sdk_compatibility": {"minimum": "0.2.0", "maximum_exclusive": "0.3.0"},
                "adapter_id": "reference:parallel-plugin",
                "producer": {"name": "sidscope-reference-adapter", "version": "0.1.0"},
                "method_family": "parallel_graph_token_set",
                "contract_types": ["trace-envelope"],
                "payload_schema": "sidscope.trace_payload.parallel_graph_token_set.v1",
                "telemetry": {
                    "supported": ["graph_frontier", "parallel_position_scores", "resolution_events"],
                    "unavailable": ["autoregressive_prefix_ancestry"],
                },
                "execution_boundary": "external_runtime",
                "runtime_requirements": [],
            }
        )

    def get_payload_fixture(self) -> Mapping[str, Any]:
        return with_content_sha256(
            {
                "schema": "sidscope.trace_payload.parallel_graph_token_set.v1",
                "schema_revision": "1.0.0",
                "payload_id": "reference:parallel-payload",
                "method_family": "parallel_graph_token_set",
                "episodes": [
                    {
                        "episode_id": "episode-0",
                        "attempts": [
                            {
                                "attempt_index": 0,
                                "parallel_position_scores": [
                                    {"position": 0, "topk": _topk(1, 2)},
                                    {"position": 1, "topk": _topk(3, 4)},
                                ],
                                "retained_token_sets": [[1, 3]],
                                "visited_item_nodes": [7],
                                "expanded_item_frontier": [7],
                            }
                        ],
                        "resolution_events": [
                            {"raw_sid": [1, 3], "raw_valid": True, "resolved_normalized_item_id": 7, "collision_count": 1}
                        ],
                        "termination_state": "success",
                        "failure_state": None,
                    }
                ],
                "privacy": {
                    "source_user_ids_exported": False,
                    "source_item_ids_exported": False,
                    "absolute_private_paths_exported": False,
                },
            }
        )
