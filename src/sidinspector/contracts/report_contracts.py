"""Canonical diagnostic, conformance, and evidence-index contracts."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .hashing import SHA256_PATTERN, verify_content_sha256, with_content_sha256
from .runtime_contracts import RuntimeContract, validate_trace_envelope, validate_episode_selection
from .producer_versions import EVALUATION_PRODUCER_VERSION


DIAGNOSTIC_REPORT_SCHEMA = "sidscope.diagnostic_report.v1"
CONFORMANCE_REPORT_SCHEMA = "sidscope.conformance_report.v1"
EVIDENCE_INDEX_SCHEMA = "sidscope.evidence_index.v1"
REPORT_SCHEMA_REVISION = "1.0.0"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
GATE_ORDER = tuple(f"G{index}" for index in range(6))


class ReportContractValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ReportContract:
    schema: str
    schema_revision: str
    artifact_id: str
    content_sha256: str
    document: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.document))


def _fail(code: str, detail: str) -> None:
    raise ReportContractValidationError(code, detail)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be non-empty")
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("invalid_count", field)
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("invalid_number", field)
    number = float(value)
    if not math.isfinite(number):
        _fail("invalid_number", field)
    return number


def _object(parent: Mapping[str, Any], key: str, fields: set[str]) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("invalid_fields", key)
    return value


def _binding(parent: Mapping[str, Any], key: str, schema_id: str) -> Mapping[str, Any]:
    binding = _object(parent, key, {"schema_id", "schema_revision", "content_sha256"})
    if binding.get("schema_id") != schema_id:
        _fail("dependency_schema_mismatch", key)
    if binding.get("schema_revision") != REPORT_SCHEMA_REVISION:
        _fail("dependency_revision_mismatch", key)
    _sha(binding.get("content_sha256"), f"{key}.content_sha256")
    return binding


def _base(
    value: Mapping[str, Any], *, schema: str, id_field: str, fields: set[str]
) -> tuple[str, str]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("contract_fields_mismatch", schema)
    if value.get("schema") != schema:
        _fail("schema_mismatch", schema)
    if value.get("schema_revision") != REPORT_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    artifact_id = _text(value.get(id_field), id_field)
    if ID_PATTERN.fullmatch(artifact_id) is None:
        _fail("invalid_artifact_id", artifact_id)
    producer = _object(value, "producer", {"name", "version"})
    _text(producer.get("name"), "producer.name")
    _text(producer.get("version"), "producer.version")
    content_sha256 = _sha(value.get("content_sha256"), "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", schema)
    return artifact_id, content_sha256


def validate_diagnostic_report(value: Mapping[str, Any]) -> ReportContract:
    fields = {
        "schema", "schema_revision", "diagnostic_report_id", "producer",
        "trace_binding", "episode_selection_binding", "evaluation",
        "failure_decomposition", "compute", "censoring", "slices",
        "content_sha256",
    }
    artifact_id, content_sha256 = _base(
        value, schema=DIAGNOSTIC_REPORT_SCHEMA, id_field="diagnostic_report_id", fields=fields
    )
    _binding(value, "trace_binding", "sidscope.trace_envelope.v1")
    _binding(value, "episode_selection_binding", "sidscope.episode_selection.v1")
    evaluation = _object(
        value,
        "evaluation",
        {"episode_count", "evaluation_cutoff", "publication_depth", "hit_at_cutoff", "ndcg_at_cutoff"},
    )
    episode_count = _count(evaluation.get("episode_count"), "evaluation.episode_count")
    if episode_count < 1:
        _fail("empty_diagnostic", "episode_count")
    cutoff = _count(evaluation.get("evaluation_cutoff"), "evaluation.evaluation_cutoff")
    depth = _count(evaluation.get("publication_depth"), "evaluation.publication_depth")
    if cutoff < 1 or depth < cutoff:
        _fail("invalid_evaluation_depth", f"cutoff={cutoff}, depth={depth}")
    for field in ("hit_at_cutoff", "ndcg_at_cutoff"):
        metric = _number(evaluation.get(field), f"evaluation.{field}")
        if metric < 0.0 or metric > 1.0:
            _fail("metric_out_of_range", field)
    failures = _object(
        value,
        "failure_decomposition",
        {
            "catalog_unreachable", "generation_search_miss", "resolution_loss",
            "ranking_conversion_miss", "success", "typed_failure",
        },
    )
    if sum(_count(failures.get(field), f"failure_decomposition.{field}") for field in failures) != episode_count:
        _fail("failure_partition_mismatch", str(dict(failures)))
    if not math.isclose(evaluation["hit_at_cutoff"] * episode_count, failures["success"], abs_tol=1e-9):
        _fail("success_hit_mismatch", "success count and Hit denominator disagree")
    compute = _object(
        value, "compute", {"nfe", "forward_calls", "candidate_count", "latency_ms"}
    )
    for field in set(compute) - {"latency_ms"}:
        _count(compute.get(field), f"compute.{field}")
    latency = _number(compute.get("latency_ms"), "compute.latency_ms")
    if latency < 0:
        _fail("invalid_number", "compute.latency_ms")
    censoring = _object(
        value, "censoring", {"exact_rank_count", "right_censored_rank_count", "not_applicable_rank_count"}
    )
    if sum(_count(censoring.get(field), f"censoring.{field}") for field in censoring) != episode_count:
        _fail("censoring_partition_mismatch", str(dict(censoring)))
    slices = value.get("slices")
    if not isinstance(slices, Sequence) or isinstance(slices, (str, bytes)) or not slices:
        _fail("invalid_slices", "slices")
    slice_ids: list[str] = []
    for index, row in enumerate(slices):
        if not isinstance(row, Mapping) or set(row) != {
            "slice_id", "episode_count", "hit_at_cutoff", "ndcg_at_cutoff"
        }:
            _fail("invalid_slice", str(index))
        slice_ids.append(_text(row.get("slice_id"), f"slices[{index}].slice_id"))
        _count(row.get("episode_count"), f"slices[{index}].episode_count")
        for field in ("hit_at_cutoff", "ndcg_at_cutoff"):
            metric = row.get(field)
            if metric is not None:
                metric_value = _number(metric, f"slices[{index}].{field}")
                if metric_value < 0.0 or metric_value > 1.0:
                    _fail("metric_out_of_range", f"slices[{index}].{field}")
    if slice_ids[0] != "overall" or slice_ids != ["overall", *sorted(slice_ids[1:])]:
        _fail("noncanonical_slice_order", str(slice_ids))
    overall = slices[0]
    if (
        overall["episode_count"] != episode_count
        or overall["hit_at_cutoff"] != evaluation["hit_at_cutoff"]
        or overall["ndcg_at_cutoff"] != evaluation["ndcg_at_cutoff"]
    ):
        _fail("overall_slice_mismatch", str(dict(overall)))
    return ReportContract(
        DIAGNOSTIC_REPORT_SCHEMA,
        REPORT_SCHEMA_REVISION,
        artifact_id,
        content_sha256,
        dict(value),
    )


def _metric_rows(observations: Sequence[Mapping[str, Any]], cutoff: int) -> tuple[float, float]:
    hits = 0
    ndcg = 0.0
    for row in observations:
        target = row["target"]
        rank = target["exact_rank"] if target["rank_state"] == "exact" else None
        if rank is not None and rank <= cutoff:
            hits += 1
            ndcg += 1.0 / math.log2(rank + 1)
    count = len(observations)
    return hits / count, ndcg / count


def diagnostic_report_document(
    trace: RuntimeContract,
    selection: RuntimeContract,
    *,
    evaluation_cutoff: int = 10,
    publication_depth: int = 100,
    report_id: str | None = None,
) -> dict[str, Any]:
    trace_doc = validate_trace_envelope(trace.to_dict()).to_dict()
    selection_doc = validate_episode_selection(selection.to_dict()).to_dict()
    if trace_doc["episode_selection_binding"]["content_sha256"] != selection.content_sha256:
        _fail("diagnostic_selection_binding_mismatch", "selection")
    if [row["episode_id"] for row in trace_doc["observations"]] != [row["episode_id"] for row in selection_doc["rows"]]:
        _fail("trace_selection_episode_mismatch", "selection")
    observations = trace_doc["observations"]
    hit, ndcg = _metric_rows(observations, evaluation_cutoff)
    failures = {
        "catalog_unreachable": 0,
        "generation_search_miss": 0,
        "resolution_loss": 0,
        "ranking_conversion_miss": 0,
        "success": 0,
        "typed_failure": 0,
    }
    censoring = {
        "exact_rank_count": 0,
        "right_censored_rank_count": 0,
        "not_applicable_rank_count": 0,
    }
    for row in observations:
        target = row["target"]
        if row["failure_state"] is not None:
            failures["typed_failure"] += 1
        elif not target["catalog_reachable"]:
            failures["catalog_unreachable"] += 1
        elif not target["generated"]:
            failures["generation_search_miss"] += 1
        elif not target["resolved"]:
            failures["resolution_loss"] += 1
        elif target["rank_state"] == "exact" and target["exact_rank"] <= evaluation_cutoff:
            failures["success"] += 1
        else:
            failures["ranking_conversion_miss"] += 1
        censoring[f"{target['rank_state']}_rank_count"] += 1
    compute = {
        field: sum(row["compute"][field] for row in observations)
        for field in ("nfe", "forward_calls", "candidate_count", "latency_ms")
    }
    labels = {
        row["episode_id"]: row["evaluator_labels"] for row in selection_doc["rows"]
    }
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in observations:
        bucket = labels[row["episode_id"]].get("dormancy_bucket")
        if isinstance(bucket, str) and bucket:
            groups.setdefault(bucket, []).append(row)
    slices = [
        {
            "slice_id": "overall",
            "episode_count": len(observations),
            "hit_at_cutoff": hit,
            "ndcg_at_cutoff": ndcg,
        }
    ]
    for slice_id in sorted(groups):
        slice_hit, slice_ndcg = _metric_rows(groups[slice_id], evaluation_cutoff)
        slices.append(
            {
                "slice_id": slice_id,
                "episode_count": len(groups[slice_id]),
                "hit_at_cutoff": slice_hit,
                "ndcg_at_cutoff": slice_ndcg,
            }
        )
    return with_content_sha256(
        {
            "schema": DIAGNOSTIC_REPORT_SCHEMA,
            "schema_revision": REPORT_SCHEMA_REVISION,
            "diagnostic_report_id": report_id or f"diagnostic:{trace.artifact_id}",
            "producer": {
                "name": "sidinspector.evaluation",
                "version": EVALUATION_PRODUCER_VERSION,
            },
            "trace_binding": {
                "schema_id": trace.schema,
                "schema_revision": trace.schema_revision,
                "content_sha256": trace.content_sha256,
            },
            "episode_selection_binding": {
                "schema_id": selection.schema,
                "schema_revision": selection.schema_revision,
                "content_sha256": selection.content_sha256,
            },
            "evaluation": {
                "episode_count": len(observations),
                "evaluation_cutoff": evaluation_cutoff,
                "publication_depth": publication_depth,
                "hit_at_cutoff": hit,
                "ndcg_at_cutoff": ndcg,
            },
            "failure_decomposition": failures,
            "compute": compute,
            "censoring": censoring,
            "slices": slices,
        }
    )


def validate_conformance_report(value: Mapping[str, Any]) -> ReportContract:
    fields = {
        "schema", "schema_revision", "conformance_report_id", "producer",
        "profile", "trace_binding", "diagnostic_binding", "verifier_sha256",
        "gates", "decision", "content_sha256",
    }
    artifact_id, content_sha256 = _base(
        value,
        schema=CONFORMANCE_REPORT_SCHEMA,
        id_field="conformance_report_id",
        fields=fields,
    )
    profile = _object(value, "profile", {"profile_id", "profile_revision"})
    _text(profile.get("profile_id"), "profile.profile_id")
    _text(profile.get("profile_revision"), "profile.profile_revision")
    _binding(value, "trace_binding", "sidscope.trace_envelope.v1")
    _binding(value, "diagnostic_binding", DIAGNOSTIC_REPORT_SCHEMA)
    _sha(value.get("verifier_sha256"), "verifier_sha256")
    gates = value.get("gates")
    if not isinstance(gates, Sequence) or isinstance(gates, (str, bytes)):
        _fail("invalid_gates", "gates")
    gate_names: list[str] = []
    gate_statuses: list[str] = []
    for index, gate in enumerate(gates):
        if not isinstance(gate, Mapping) or set(gate) != {"gate", "status", "failure_code"}:
            _fail("invalid_gate", str(index))
        gate_names.append(_text(gate.get("gate"), f"gates[{index}].gate"))
        status = _text(gate.get("status"), f"gates[{index}].status")
        if status not in {"pass", "fail", "partial"}:
            _fail("unsupported_gate_status", status)
        gate_statuses.append(status)
        failure_code = gate.get("failure_code")
        if status == "pass" and failure_code is not None:
            _fail("pass_gate_has_failure", gate_names[-1])
        if status != "pass" and failure_code is None:
            _fail("failed_gate_missing_failure", gate_names[-1])
    if tuple(gate_names) != GATE_ORDER:
        _fail("noncanonical_gate_order", str(gate_names))
    decision = _object(value, "decision", {"status", "scope"})
    decision_status = _text(decision.get("status"), "decision.status")
    if decision_status not in {"pass", "fail", "partial", "fixture_pass"}:
        _fail("unsupported_decision", decision_status)
    _text(decision.get("scope"), "decision.scope")
    expected_decision = (
        "fail"
        if "fail" in gate_statuses
        else "partial"
        if "partial" in gate_statuses
        else "pass"
    )
    if expected_decision == "pass" and decision_status not in {"pass", "fixture_pass"}:
        _fail("decision_gate_mismatch", decision_status)
    if expected_decision != "pass" and decision_status != expected_decision:
        _fail("decision_gate_mismatch", decision_status)
    return ReportContract(
        CONFORMANCE_REPORT_SCHEMA,
        REPORT_SCHEMA_REVISION,
        artifact_id,
        content_sha256,
        dict(value),
    )


def validate_evidence_index(value: Mapping[str, Any]) -> ReportContract:
    fields = {
        "schema", "schema_revision", "evidence_index_id", "producer", "artifacts",
        "edges", "omissions", "privacy", "content_sha256",
    }
    artifact_id, content_sha256 = _base(
        value, schema=EVIDENCE_INDEX_SCHEMA, id_field="evidence_index_id", fields=fields
    )
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, Sequence) or isinstance(artifacts, (str, bytes)) or not artifacts:
        _fail("invalid_evidence_artifacts", "artifacts")
    identifiers: list[str] = []
    hashes: set[str] = set()
    for index, row in enumerate(artifacts):
        if not isinstance(row, Mapping) or set(row) != {
            "artifact_id", "role", "schema_id", "schema_revision", "content_sha256"
        }:
            _fail("invalid_evidence_artifact", str(index))
        identifiers.append(_text(row.get("artifact_id"), f"artifacts[{index}].artifact_id"))
        _text(row.get("role"), f"artifacts[{index}].role")
        _text(row.get("schema_id"), f"artifacts[{index}].schema_id")
        if row.get("schema_revision") != REPORT_SCHEMA_REVISION:
            _fail("dependency_revision_mismatch", identifiers[-1])
        hashes.add(_sha(row.get("content_sha256"), f"artifacts[{index}].content_sha256"))
    if identifiers != sorted(set(identifiers)) or len(hashes) != len(artifacts):
        _fail("noncanonical_evidence_artifacts", str(identifiers))
    edges = value.get("edges")
    if not isinstance(edges, Sequence) or isinstance(edges, (str, bytes)):
        _fail("invalid_evidence_edges", "edges")
    graph = {identifier: set() for identifier in identifiers}
    edge_keys: list[tuple[str, str, str]] = []
    for index, row in enumerate(edges):
        if not isinstance(row, Mapping) or set(row) != {"from_artifact", "to_artifact", "relation"}:
            _fail("invalid_evidence_edge", str(index))
        source = _text(row.get("from_artifact"), f"edges[{index}].from_artifact")
        target = _text(row.get("to_artifact"), f"edges[{index}].to_artifact")
        relation = _text(row.get("relation"), f"edges[{index}].relation")
        if source not in graph or target not in graph:
            _fail("unknown_evidence_artifact", f"{source}->{target}")
        graph[source].add(target)
        edge_keys.append((source, target, relation))
    if edge_keys != sorted(set(edge_keys)):
        _fail("noncanonical_evidence_edges", str(edge_keys))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            _fail("evidence_cycle", node)
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    omissions = value.get("omissions")
    if not isinstance(omissions, Sequence) or isinstance(omissions, (str, bytes)):
        _fail("invalid_omissions", "omissions")
    for index, row in enumerate(omissions):
        if not isinstance(row, Mapping) or set(row) != {"artifact", "reason", "policy"}:
            _fail("invalid_omission", str(index))
        for field in row:
            _text(row.get(field), f"omissions[{index}].{field}")
    privacy = _object(
        value,
        "privacy",
        {"source_user_ids_exported", "source_item_ids_exported", "absolute_private_paths_exported"},
    )
    if any(privacy.values()) or any(not isinstance(item, bool) for item in privacy.values()):
        _fail("privacy_boundary_violation", str(dict(privacy)))
    return ReportContract(
        EVIDENCE_INDEX_SCHEMA,
        REPORT_SCHEMA_REVISION,
        artifact_id,
        content_sha256,
        dict(value),
    )


def validate_report_bindings(
    diagnostic: ReportContract,
    conformance: ReportContract,
    trace: RuntimeContract,
    selection: RuntimeContract,
) -> None:
    diagnostic_doc = diagnostic.to_dict()
    conformance_doc = conformance.to_dict()
    primary_expected = (
        (diagnostic_doc["trace_binding"]["content_sha256"], trace.content_sha256, "diagnostic_trace_binding_mismatch"),
        (diagnostic_doc["episode_selection_binding"]["content_sha256"], selection.content_sha256, "diagnostic_selection_binding_mismatch"),
        (conformance_doc["trace_binding"]["content_sha256"], trace.content_sha256, "conformance_trace_binding_mismatch"),
    )
    for observed, wanted, code in primary_expected:
        if observed != wanted:
            _fail(code, f"{observed} != {wanted}")
    evaluation = diagnostic_doc["evaluation"]
    rebuilt = diagnostic_report_document(
        trace,
        selection,
        evaluation_cutoff=evaluation["evaluation_cutoff"],
        publication_depth=evaluation["publication_depth"],
        report_id=diagnostic.artifact_id,
    )
    for field in ("evaluation", "failure_decomposition", "compute", "censoring", "slices"):
        if diagnostic_doc[field] != rebuilt[field]:
            _fail("metric_mismatch", field)
    observed_diagnostic = conformance_doc["diagnostic_binding"]["content_sha256"]
    if observed_diagnostic != diagnostic.content_sha256:
        _fail(
            "conformance_diagnostic_binding_mismatch",
            f"{observed_diagnostic} != {diagnostic.content_sha256}",
        )


def _load(path: Path, validator: Any) -> ReportContract:
    from .json_io import load_json
    value = load_json(path)
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain an object")
    return validator(value)


def load_diagnostic_report(path: Path) -> ReportContract:
    return _load(path, validate_diagnostic_report)


def load_conformance_report(path: Path) -> ReportContract:
    return _load(path, validate_conformance_report)


def load_evidence_index(path: Path) -> ReportContract:
    return _load(path, validate_evidence_index)
