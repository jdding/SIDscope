"""Closed metric/population identity for independently recomputed diagnostics."""
from __future__ import annotations

from typing import Any, Mapping

from .hashing import SHA256_PATTERN, verify_content_sha256, with_content_sha256

SCHEMA = "sidscope.evaluation_protocol.v1"
FIXED = {
    "schema": SCHEMA, "schema_revision": "1.0.0",
    "evaluator": "sidscope.diagnostic_report.v1@1.0.0",
    "metrics": ["single_target_hit", "single_target_ndcg"],
    "aggregation": "macro_per_selected_episode",
    "non_exact_policy": "count_as_miss",
    "slice_definition": "selection.evaluator_labels.dormancy_bucket.v1",
    "compute_unit": "milliseconds_total",
}
BINDINGS = ("dataset_identity_sha256", "target_universe_sha256", "episode_selection_sha256")


class EvaluationProtocolError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def validate_evaluation_protocol(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = set(FIXED) | set(BINDINGS) | {"evaluation_cutoff", "publication_depth", "rank_semantics", "compute_environment_sha256", "content_sha256"}
    if not isinstance(value, Mapping) or set(value) != fields:
        raise EvaluationProtocolError("invalid_evaluation_protocol_fields", "protocol")
    if any(value[key] != expected for key, expected in FIXED.items()):
        raise EvaluationProtocolError("unsupported_evaluation_definition", "protocol")
    for key in (*BINDINGS, "content_sha256", "compute_environment_sha256"):
        if key == "compute_environment_sha256" and value[key] is None:
            continue
        if not isinstance(value[key], str) or SHA256_PATTERN.fullmatch(value[key]) is None:
            raise EvaluationProtocolError("invalid_evaluation_protocol_hash", key)
    k, depth = value["evaluation_cutoff"], value["publication_depth"]
    if type(k) is not int or type(depth) is not int or not 1 <= k <= depth:
        raise EvaluationProtocolError("invalid_evaluation_depth", "protocol")
    if value["rank_semantics"] not in {"exact_with_censoring", "cutoff_only"} or (value["rank_semantics"] == "cutoff_only" and depth != k):
        raise EvaluationProtocolError("unsupported_rank_semantics", "protocol")
    if not verify_content_sha256(value):
        raise EvaluationProtocolError("content_hash_mismatch", "protocol")
    return dict(value)


def build_evaluation_protocol(*, dataset_identity_sha256: str, target_universe_sha256: str, episode_selection_sha256: str, evaluation_cutoff: int, publication_depth: int, rank_semantics: str = "exact_with_censoring", compute_environment_sha256: str | None = None) -> dict[str, Any]:
    return validate_evaluation_protocol(with_content_sha256({
        **FIXED, "dataset_identity_sha256": dataset_identity_sha256,
        "target_universe_sha256": target_universe_sha256,
        "episode_selection_sha256": episode_selection_sha256,
        "evaluation_cutoff": evaluation_cutoff, "publication_depth": publication_depth,
        "rank_semantics": rank_semantics, "compute_environment_sha256": compute_environment_sha256,
    }))
