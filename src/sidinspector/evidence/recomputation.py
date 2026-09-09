"""Recompute bounded diagnostic evidence; never infer native/training authenticity."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from sidinspector.contracts import canonical_json_bytes, validate_trace_envelope, validate_episode_selection, validate_diagnostic_report, diagnostic_report_document
from sidinspector.contracts import validate_evaluation_protocol
from .bundle import EvidenceBundle, EvidenceBundleValidationError, validate_evidence_bundle

VERIFIED_LABEL = "diagnostics_verified"
ROLES = {"evaluation_protocol": "sidscope.evaluation_protocol.v1", "selection": "sidscope.episode_selection.v1", "trace": "sidscope.trace_envelope.v1", "diagnostics": "sidscope.diagnostic_report.v1"}


def _fail(code: str, detail: str) -> None:
    raise EvidenceBundleValidationError(code, detail)


def result_card_from_diagnostic(diagnostic: Mapping[str, Any], trace: Mapping[str, Any], rank_semantics: str) -> dict[str, Any]:
    k = diagnostic["evaluation"]["evaluation_cutoff"]
    def metrics(row):
        return {f"hit_at_{k}": row["hit_at_cutoff"], f"ndcg_at_{k}": row["ndcg_at_cutoff"]}
    ranks = [row["target"]["exact_rank"] for row in trace["observations"] if row["target"]["rank_state"] == "exact"] if rank_semantics == "exact_with_censoring" else []
    return {
        "overall_metrics": metrics(diagnostic["evaluation"]),
        "slice_metrics": {row["slice_id"]: metrics(row) for row in diagnostic["slices"][1:] if row["episode_count"] > 0},
        "failure_counts": dict(diagnostic["failure_decomposition"]),
        "compute": dict(diagnostic["compute"]),
        "rank_observations": {"exact_ranks": ranks, "exact_count": len(ranks), "censored_count": len(trace["observations"]) - len(ranks)},
    }


def recompute_bundle(bundle: EvidenceBundle | Mapping[str, Any], objects: Mapping[str, bytes]) -> dict[str, Any]:
    validated = validate_evidence_bundle(bundle.to_dict() if isinstance(bundle, EvidenceBundle) else bundle)
    docs = {}
    for role, schema in ROLES.items():
        rows = [row for row in validated.artifacts if row["role"] == role]
        if len(rows) != 1:
            _fail("verification_artifact_required", role)
        row = rows[0]
        if row["availability"] != "embedded_public" or row["object_sha256"] not in objects:
            _fail("verification_input_unavailable", role)
        payload = objects[row["object_sha256"]]
        if not isinstance(payload, bytes) or len(payload) > 8 * 1024 * 1024:
            _fail("verification_input_budget_exceeded", role)
        if len(payload) != row["size_bytes"] or hashlib.sha256(payload).hexdigest() != row["object_sha256"]:
            _fail("verification_object_hash_mismatch", role)
        try:
            doc = json.loads(payload)
            if payload != canonical_json_bytes(doc) + b"\n":
                _fail("noncanonical_verification_input", role)
        except (ValueError, UnicodeError, RecursionError) as error:
            if isinstance(error, EvidenceBundleValidationError):
                raise
            _fail("invalid_verification_json", role)
        if not isinstance(doc, dict) or doc.get("schema") != schema or row["schema_id"] != schema or doc.get("schema_revision") != "1.0.0" or row["schema_revision"] != "1.0.0" or doc.get("content_sha256") != row["content_sha256"]:
            _fail("verification_artifact_binding_mismatch", role)
        docs[role] = doc
    try:
        protocol = validate_evaluation_protocol(docs["evaluation_protocol"])
        trace = validate_trace_envelope(docs["trace"])
        selection = validate_episode_selection(docs["selection"])
        diagnostic = validate_diagnostic_report(docs["diagnostics"])
        for field in ("dataset_identity_sha256", "target_universe_sha256", "evaluation_cutoff", "publication_depth", "rank_semantics"):
            if protocol[field] != validated.compatibility[field]:
                _fail("evaluation_protocol_binding_mismatch", field)
        if protocol["episode_selection_sha256"] != selection.content_sha256:
            _fail("evaluation_population_mismatch", "selection")
        if docs["trace"]["method_family"] != validated.subject["method_family"]:
            _fail("method_family_mismatch", "trace")
        if docs["diagnostics"]["trace_binding"]["content_sha256"] != trace.content_sha256 or docs["diagnostics"]["episode_selection_binding"]["content_sha256"] != selection.content_sha256:
            _fail("diagnostic_input_binding_mismatch", "diagnostics")
        rebuilt = diagnostic_report_document(trace, selection, evaluation_cutoff=protocol["evaluation_cutoff"], publication_depth=protocol["publication_depth"], report_id=diagnostic.artifact_id)
        for field in ("evaluation", "failure_decomposition", "compute", "censoring", "slices"):
            if docs["diagnostics"][field] != rebuilt[field]:
                _fail("recomputed_diagnostic_mismatch", field)
        if validated.result_card != result_card_from_diagnostic(rebuilt, docs["trace"], protocol["rank_semantics"]):
            _fail("recomputed_result_card_mismatch", "result_card")
    except ValueError as error:
        if isinstance(error, EvidenceBundleValidationError):
            raise
        _fail(getattr(error, "code", "invalid_verification_input"), str(error))
    return {"status_label": VERIFIED_LABEL, "verification_scope": "diagnostics_from_supplied_trace", "evaluation_protocol": protocol, "unverified_claims": ["native_trace_authenticity", "training_reproducibility", "named_adapter"]}
