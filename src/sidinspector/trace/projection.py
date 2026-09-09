"""Verify only native facts actually present; never invent a ranking order."""
from __future__ import annotations
from sidinspector.contracts import validate_trace_envelope, validate_episode_selection
from .native_payloads import validate_native_payload, NativePayloadValidationError


def validate_native_projection(payload: dict, trace: dict, selection: dict) -> dict:
    native = validate_native_payload(payload)
    envelope = validate_trace_envelope(trace)
    selected = validate_episode_selection(selection)
    def fail(code, detail):
        raise NativePayloadValidationError(code, detail)
    if trace["payload_schema"] != native.schema or trace["payload_sha256"] != native.content_sha256 or trace["method_family"] != native.method_family:
        fail("native_projection_binding_mismatch", "payload")
    if trace["episode_selection_binding"]["content_sha256"] != selected.content_sha256:
        fail("native_projection_binding_mismatch", "selection")
    episodes = payload["episodes"]
    ids = [row["episode_id"] for row in selection["rows"]]
    if [row["episode_id"] for row in episodes] != ids or [row["episode_id"] for row in trace["observations"]] != ids:
        fail("native_projection_population_mismatch", "episode order")
    verified, unavailable = ["payload_binding", "method_family", "episode_order", "termination", "target_resolution"], ["catalog_reachability", "target_generation", "latency", "native_execution_authenticity"]
    for ep, observation, label in zip(episodes, trace["observations"], selection["rows"]):
        target_id = label["target_normalized_item_id"]
        target = observation["target"]
        if ep["termination_state"] != observation["termination_state"] or ep["failure_state"] != observation["failure_state"]:
            fail("native_projection_termination_mismatch", ep["episode_id"])
        resolved = any(row["raw_valid"] and row["collision_count"] == 1 and row["resolved_normalized_item_id"] == target_id for row in ep["resolution_events"])
        if resolved != target["resolved"]:
            fail("native_projection_resolution_mismatch", ep["episode_id"])
        if native.method_family == "decoder_overlay":
            rank = next((row["rank"] for row in ep["fused_ranked_items"] if row["normalized_item_id"] == target_id), None)
            if rank is not None and (target["rank_state"] != "exact" or target["exact_rank"] != rank):
                fail("native_projection_rank_mismatch", ep["episode_id"])
            if rank is None and (target["rank_state"] != "right_censored" or target["rank_lower_bound"] != len(ep["fused_ranked_items"]) + 1):
                fail("native_projection_rank_mismatch", ep["episode_id"])
        else:
            # Resolution events have no ranking contract. Their array order is
            # not permission to invent beam order, AR ancestry or exact ranks.
            if "target_rank" not in unavailable:
                unavailable.append("target_rank")
    if native.method_family == "decoder_overlay":
        verified.append("target_rank")
    return {"status": "partial", "verified_fields": verified, "unverified_fields": unavailable, "trace_sha256": envelope.content_sha256, "payload_sha256": native.content_sha256, "selection_sha256": selected.content_sha256}
