"""Fail-closed comparison of immutable SIDScope evidence bundles."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from sidinspector.evidence.bundle import (
    EvidenceBundle,
    EvidenceBundleValidationError,
    validate_evidence_bundle,
)
from sidinspector.contracts import SHA256_PATTERN


EVIDENCE_COMPARISON_SCHEMA = "sidscope.evidence_comparison.v1"
EVIDENCE_COMPARISON_SCHEMA_REVISION = "1.0.0"


_COMPATIBILITY_FIELDS = (
    ("profile_id", "profile_id_mismatch"),
    ("profile_revision", "profile_revision_mismatch"),
    ("dataset_identity_sha256", "dataset_identity_mismatch"),
    ("target_universe_sha256", "target_universe_mismatch"),
    ("evaluation_cutoff", "evaluation_cutoff_mismatch"),
    ("publication_depth", "publication_depth_mismatch"),
    ("rank_semantics", "rank_semantics_mismatch"),
)


def _raw_document(bundle: EvidenceBundle | Mapping[str, Any]) -> dict[str, Any]:
    return bundle.to_dict() if isinstance(bundle, EvidenceBundle) else dict(bundle)


def _compatibility_view(document: Mapping[str, Any]) -> dict[str, Any]:
    profile = document["profile_binding"]
    compatibility = document["compatibility"]
    return {
        "profile_id": profile["profile_id"],
        "profile_revision": profile["profile_revision"],
        "dataset_identity_sha256": compatibility["dataset_identity_sha256"],
        "target_universe_sha256": compatibility["target_universe_sha256"],
        "evaluation_cutoff": compatibility["evaluation_cutoff"],
        "publication_depth": compatibility["publication_depth"],
        "rank_semantics": compatibility["rank_semantics"],
    }


def _rank_rejections(side: str, document: Mapping[str, Any]) -> list[dict[str, Any]]:
    compatibility = document["compatibility"]
    observations = document["result_card"].get("rank_observations", {})
    if not isinstance(observations, Mapping):
        return [{"code": "invalid_rank_observations", "side": side}]
    exact_ranks = observations.get("exact_ranks", [])
    if not isinstance(exact_ranks, list):
        return [{"code": "invalid_exact_ranks", "side": side}]
    exact_count = observations.get("exact_count", len(exact_ranks))
    if isinstance(exact_count, bool) or not isinstance(exact_count, int) or exact_count < 0:
        return [{"code": "invalid_exact_count", "side": side}]
    rejections: list[dict[str, Any]] = []
    if exact_count != len(exact_ranks):
        rejections.append(
            {
                "code": "exact_rank_count_mismatch",
                "side": side,
                "exact_count": exact_count,
                "observed_count": len(exact_ranks),
            }
        )
    if compatibility["rank_semantics"] == "cutoff_only" and exact_count > 0:
        rejections.append(
            {
                "code": "unsupported_exact_rank_claim",
                "side": side,
                "rank_semantics": "cutoff_only",
            }
        )
    publication_depth = compatibility["publication_depth"]
    invalid = sorted(
        {
            rank
            for rank in exact_ranks
            if isinstance(rank, bool)
            or not isinstance(rank, int)
            or rank < 1
            or rank > publication_depth
        },
        key=lambda value: (str(type(value)), str(value)),
    )
    if invalid:
        rejections.append(
            {
                "code": "exact_rank_exceeds_publication_depth",
                "side": side,
                "publication_depth": publication_depth,
                "invalid_exact_ranks": invalid,
            }
        )
    return rejections


def _numeric_delta(left: Any, right: Any) -> dict[str, Any] | None:
    if (
        isinstance(left, bool)
        or isinstance(right, bool)
        or not isinstance(left, (int, float))
        or not isinstance(right, (int, float))
    ):
        return None
    return {"left": left, "right": right, "delta": right - left}


def _mapping_deltas(left: Any, right: Any, *, metrics: bool = False) -> dict[str, Any]:
    left_values = left if isinstance(left, Mapping) else {}
    right_values = right if isinstance(right, Mapping) else {}
    result: dict[str, Any] = {}
    for name in sorted(set(left_values) | set(right_values)):
        if metrics and re.fullmatch(r"(?:hit|recall|ndcg)_at_[1-9][0-9]*", str(name)) is None:
            result[str(name)] = {
                "left": left_values.get(name), "right": right_values.get(name),
                "delta": None, "status": "unregistered_metric_definition",
            }
            continue
        if name not in left_values or name not in right_values:
            result[str(name)] = {
                "left": left_values.get(name),
                "right": right_values.get(name),
                "delta": None,
                "status": "missing_operand",
            }
            continue
        delta = _numeric_delta(left_values[name], right_values[name])
        if delta is None:
            result[str(name)] = {
                "left": left_values[name],
                "right": right_values[name],
                "delta": None,
                "status": "non_numeric",
            }
        else:
            result[str(name)] = delta
    return result


def _slice_deltas(left: Any, right: Any) -> dict[str, Any]:
    left_slices = left if isinstance(left, Mapping) else {}
    right_slices = right if isinstance(right, Mapping) else {}
    return {
        str(slice_id): _mapping_deltas(
            left_slices.get(slice_id, {}), right_slices.get(slice_id, {}), metrics=True
        )
        for slice_id in sorted(set(left_slices) | set(right_slices))
    }


def compare_legacy_evidence_bundles(
    left: EvidenceBundle | Mapping[str, Any],
    right: EvidenceBundle | Mapping[str, Any],
) -> dict[str, Any]:
    """Compare compatible method evidence or return typed incompatibilities.

    Metric deltas are intentionally absent unless every comparison contract axis
    matches.  A malformed exact-rank claim is rejected before compatibility is
    considered.
    """

    raw_left = _raw_document(left)
    raw_right = _raw_document(right)
    validation_rejections: list[dict[str, Any]] = []
    validated: dict[str, dict[str, Any]] = {}
    for side, raw in (("left", raw_left), ("right", raw_right)):
        try:
            validated[side] = validate_evidence_bundle(raw).to_dict()
        except EvidenceBundleValidationError as error:
            validation_rejections.append(
                {
                    "code": "invalid_bundle",
                    "side": side,
                    "validation_code": error.code,
                    "detail": error.detail,
                }
            )
    left_hash = raw_left.get("content_sha256")
    right_hash = raw_right.get("content_sha256")
    base = {
        "schema": EVIDENCE_COMPARISON_SCHEMA,
        "schema_revision": EVIDENCE_COMPARISON_SCHEMA_REVISION,
        "left_bundle_sha256": left_hash,
        "right_bundle_sha256": right_hash,
    }
    if validation_rejections:
        return {
            **base,
            "status": "rejected",
            "contract_compatibility": {
                "status": "rejected",
                "reasons": sorted(
                    validation_rejections,
                    key=lambda row: (row["validation_code"], row["side"]),
                ),
            },
            "method_difference": None,
        }

    left_document = validated["left"]
    right_document = validated["right"]

    rank_rejections = sorted(
        _rank_rejections("left", left_document)
        + _rank_rejections("right", right_document),
        key=lambda row: (row["code"], row["side"]),
    )
    if rank_rejections:
        return {
            **base,
            "status": "rejected",
            "contract_compatibility": {
                "status": "rejected",
                "reasons": rank_rejections,
            },
            "method_difference": None,
        }

    left_contract = _compatibility_view(left_document)
    right_contract = _compatibility_view(right_document)
    reasons = []
    for field, code in _COMPATIBILITY_FIELDS:
        if left_contract[field] != right_contract[field]:
            reasons.append(
                {
                    "code": code,
                    "field": field,
                    "left": left_contract[field],
                    "right": right_contract[field],
                }
            )
    if reasons:
        return {
            **base,
            "status": "incompatible",
            "contract_compatibility": {
                "status": "incompatible",
                "reasons": reasons,
            },
            "method_difference": None,
        }

    left_card = left_document["result_card"]
    right_card = right_document["result_card"]
    return {
        **base,
        "status": "compatible",
        "contract_compatibility": {
            "status": "compatible",
            "reasons": [],
            "shared_contract": left_contract,
        },
        "method_difference": {
            "verification_level": "declared_metrics_not_recomputed",
            "boundary": "Contract compatibility is not independent metric verification or cohort equivalence.",
            "left_subject": left_document["subject"],
            "right_subject": right_document["subject"],
            "overall_metrics": _mapping_deltas(
                left_card.get("overall_metrics", {}),
                right_card.get("overall_metrics", {}),
                metrics=True,
            ),
            "slice_metrics": _slice_deltas(
                left_card.get("slice_metrics", {}),
                right_card.get("slice_metrics", {}),
            ),
            "failure_counts": _mapping_deltas(
                left_card.get("failure_counts", {}),
                right_card.get("failure_counts", {}),
            ),
            "compute": _mapping_deltas(
                left_card.get("compute", {}), right_card.get("compute", {})
            ),
        },
    }


def compare_evidence_bundles(left, right, *, left_objects=None, right_objects=None):
    """Require recomputed metrics and identical population/metric definitions."""
    from .recomputation import recompute_bundle
    result = compare_legacy_evidence_bundles(left, right)
    if result["status"] != "compatible":
        return result
    verified = []
    for side, bundle, objects in (("left", left, left_objects), ("right", right, right_objects)):
        try:
            verified.append(recompute_bundle(bundle, objects or {}))
        except EvidenceBundleValidationError as error:
            result.update(status="incompatible", contract_compatibility={"status": "incompatible", "reasons": [{"code": error.code, "side": side}]}, method_difference=None)
            return result
    a, b = [row["evaluation_protocol"] for row in verified]
    differences = [key for key in a if key not in {"content_sha256", "compute_environment_sha256"} and a[key] != b[key]]
    if differences:
        result.update(status="incompatible", contract_compatibility={"status": "incompatible", "reasons": [{"code": "evaluation_protocol_mismatch", "fields": sorted(differences)}]}, method_difference=None)
        return result
    result["method_difference"]["verification_level"] = "recomputed_diagnostics"
    result["method_difference"]["boundary"] = "Metrics recomputed on one protocol/population; native execution and training remain unverified."
    from sidinspector.contracts import with_content_sha256
    accuracy_protocol = {key: value for key, value in a.items() if key not in {"content_sha256", "compute_environment_sha256"}}
    result["contract_compatibility"]["shared_contract"]["accuracy_protocol_sha256"] = with_content_sha256(accuracy_protocol)["content_sha256"]
    if a["compute_environment_sha256"] is None or a["compute_environment_sha256"] != b["compute_environment_sha256"]:
        result["method_difference"]["compute"] = {"status": "unverified_measurement_conditions", "delta": None}
    return result


def validate_evidence_comparison(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the stable derived comparison document without its inputs."""

    fields = {
        "schema",
        "schema_revision",
        "left_bundle_sha256",
        "right_bundle_sha256",
        "status",
        "contract_compatibility",
        "method_difference",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise EvidenceBundleValidationError(
            "comparison_fields_mismatch", str(sorted(value) if isinstance(value, Mapping) else type(value).__name__)
        )
    if value.get("schema") != EVIDENCE_COMPARISON_SCHEMA:
        raise EvidenceBundleValidationError("schema_mismatch", str(value.get("schema")))
    if value.get("schema_revision") != EVIDENCE_COMPARISON_SCHEMA_REVISION:
        raise EvidenceBundleValidationError(
            "schema_revision_mismatch", str(value.get("schema_revision"))
        )
    for field in ("left_bundle_sha256", "right_bundle_sha256"):
        digest = value.get(field)
        if digest is not None and (
            not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise EvidenceBundleValidationError("invalid_sha256", field)
    status = value.get("status")
    if status not in {"compatible", "incompatible", "rejected"}:
        raise EvidenceBundleValidationError("invalid_comparison_status", str(status))
    compatibility = value.get("contract_compatibility")
    expected_fields = (
        {"status", "reasons", "shared_contract"}
        if status == "compatible"
        else {"status", "reasons"}
    )
    if not isinstance(compatibility, Mapping) or set(compatibility) != expected_fields:
        raise EvidenceBundleValidationError("comparison_contract_fields_mismatch", str(status))
    if compatibility.get("status") != status:
        raise EvidenceBundleValidationError("comparison_status_mismatch", str(status))
    reasons = compatibility.get("reasons")
    if not isinstance(reasons, list) or any(not isinstance(row, Mapping) for row in reasons):
        raise EvidenceBundleValidationError("invalid_comparison_reasons", str(status))
    difference = value.get("method_difference")
    if status == "compatible":
        if reasons or not isinstance(difference, Mapping):
            raise EvidenceBundleValidationError("compatible_comparison_mismatch", str(status))
    elif difference is not None:
        raise EvidenceBundleValidationError("incompatible_comparison_has_difference", str(status))
    return value


__all__ = [
    "EVIDENCE_COMPARISON_SCHEMA",
    "EVIDENCE_COMPARISON_SCHEMA_REVISION",
    "compare_evidence_bundles",
    "validate_evidence_comparison",
]
