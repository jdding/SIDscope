"""Public JSON contracts for portable SIDScope evidence submissions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sidinspector.contracts import (
    SHA256_PATTERN,
    verify_content_sha256,
    with_content_sha256,
)


EVIDENCE_SUBMISSION_SCHEMA = "sidscope.evidence_submission.v1"
SUBMISSION_CHECK_REPORT_SCHEMA = "sidscope.submission_check_report.v1"
SUBMISSION_SCHEMA_REVISION = "1.0.0"
SUBMISSION_ARTIFACT_ROLES = frozenset(
    {
        "dataset_profile_descriptor",
        "profile_conformance_report",
        "evidence_bundle",
        "evidence_object",
    }
)
REQUIRED_SUBMISSION_ROLES = (
    "dataset_profile_descriptor",
    "profile_conformance_report",
    "evidence_bundle",
)
RANK_SEMANTICS = frozenset({"exact_with_censoring", "cutoff_only"})
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class SubmissionValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class EvidenceSubmission:
    submission_id: str
    producer: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...]
    claims: Mapping[str, Any]
    content_sha256: str

    @property
    def schema(self) -> str:
        return EVIDENCE_SUBMISSION_SCHEMA

    @property
    def schema_revision(self) -> str:
        return SUBMISSION_SCHEMA_REVISION

    def to_dict(self) -> dict[str, Any]:
        return json.loads(
            json.dumps(
                {
                    "schema": self.schema,
                    "schema_revision": self.schema_revision,
                    "submission_id": self.submission_id,
                    "producer": self.producer,
                    "artifacts": self.artifacts,
                    "claims": self.claims,
                    "content_sha256": self.content_sha256,
                },
                allow_nan=False,
            )
        )


@dataclass(frozen=True)
class SubmissionCheckReport:
    submission_id: str
    submission_sha256: str | None
    status: str
    bindings: Mapping[str, Any] | None
    failures: tuple[Mapping[str, str], ...]
    content_sha256: str

    @property
    def schema(self) -> str:
        return SUBMISSION_CHECK_REPORT_SCHEMA

    @property
    def schema_revision(self) -> str:
        return SUBMISSION_SCHEMA_REVISION

    def to_dict(self) -> dict[str, Any]:
        return json.loads(
            json.dumps(
                {
                    "schema": self.schema,
                    "schema_revision": self.schema_revision,
                    "submission_id": self.submission_id,
                    "submission_sha256": self.submission_sha256,
                    "status": self.status,
                    "bindings": self.bindings,
                    "failures": self.failures,
                    "content_sha256": self.content_sha256,
                },
                allow_nan=False,
            )
        )


def _fail(code: str, detail: str) -> None:
    raise SubmissionValidationError(code, detail)


def _exact(value: Any, fields: set[str], location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("invalid_fields", location)
    return value


def _text(value: Any, field: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be non-empty text")
    if identifier and ID_PATTERN.fullmatch(value) is None:
        _fail("invalid_identifier", field)
    return value


def _sha(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def _count(value: Any, field: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_count", field)
    return value


def validate_evidence_submission(value: Mapping[str, Any]) -> EvidenceSubmission:
    fields = {
        "schema",
        "schema_revision",
        "submission_id",
        "producer",
        "artifacts",
        "claims",
        "content_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("contract_fields_mismatch", EVIDENCE_SUBMISSION_SCHEMA)
    if value.get("schema") != EVIDENCE_SUBMISSION_SCHEMA:
        _fail("schema_mismatch", str(value.get("schema")))
    if value.get("schema_revision") != SUBMISSION_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    submission_id = _text(value.get("submission_id"), "submission_id", identifier=True)
    producer = _exact(value.get("producer"), {"name", "version"}, "producer")
    _text(producer.get("name"), "producer.name")
    _text(producer.get("version"), "producer.version")

    artifacts_raw = value.get("artifacts")
    if not isinstance(artifacts_raw, Sequence) or isinstance(
        artifacts_raw, (str, bytes, bytearray)
    ) or not artifacts_raw:
        _fail("invalid_artifacts", "artifacts")
    artifacts: list[Mapping[str, Any]] = []
    artifact_ids: list[str] = []
    artifact_paths: list[str] = []
    artifact_hashes: list[str] = []
    role_counts = {role: 0 for role in REQUIRED_SUBMISSION_ROLES}
    for index, raw in enumerate(artifacts_raw):
        row = _exact(
            raw,
            {"artifact_id", "role", "path", "sha256"},
            f"artifacts[{index}]",
        )
        artifact_id = _text(
            row.get("artifact_id"), f"artifacts[{index}].artifact_id", identifier=True
        )
        role = _text(row.get("role"), f"artifacts[{index}].role")
        if role not in SUBMISSION_ARTIFACT_ROLES:
            _fail("unknown_artifact_role", role)
        path = _text(row.get("path"), f"artifacts[{index}].path")
        digest = _sha(row.get("sha256"), f"artifacts[{index}].sha256") or ""
        artifact_ids.append(artifact_id)
        artifact_paths.append(path)
        artifact_hashes.append(digest)
        if role in role_counts:
            role_counts[role] += 1
        artifacts.append(dict(row))
    if artifact_ids != sorted(artifact_ids):
        _fail("noncanonical_artifact_order", "artifacts must be sorted by artifact_id")
    if len(set(artifact_ids)) != len(artifact_ids):
        _fail("duplicate_artifact", "artifact_id")
    if len(set(artifact_paths)) != len(artifact_paths):
        _fail("duplicate_artifact", "path")
    if len(set(artifact_hashes)) != len(artifact_hashes):
        _fail("duplicate_artifact", "sha256")
    invalid_counts = {role: count for role, count in role_counts.items() if count != 1}
    if invalid_counts:
        _fail("incomplete_submission", str(invalid_counts))

    claims = _exact(
        value.get("claims"),
        {
            "profile_id",
            "profile_revision",
            "dataset_identity_sha256",
            "target_universe_sha256",
            "evaluation_cutoff",
            "publication_depth",
            "rank_semantics",
            "exact_ranks",
        },
        "claims",
    )
    _text(claims.get("profile_id"), "claims.profile_id")
    _text(claims.get("profile_revision"), "claims.profile_revision")
    _sha(claims.get("dataset_identity_sha256"), "claims.dataset_identity_sha256")
    _sha(claims.get("target_universe_sha256"), "claims.target_universe_sha256")
    cutoff = _count(claims.get("evaluation_cutoff"), "claims.evaluation_cutoff", positive=True)
    depth = _count(claims.get("publication_depth"), "claims.publication_depth", positive=True)
    if depth < cutoff:
        _fail("invalid_evaluation_depth", f"{cutoff}>{depth}")
    rank_semantics = claims.get("rank_semantics")
    if rank_semantics not in RANK_SEMANTICS:
        _fail("unsupported_rank_semantics", str(rank_semantics))
    ranks = claims.get("exact_ranks")
    if not isinstance(ranks, Sequence) or isinstance(ranks, (str, bytes, bytearray)):
        _fail("invalid_exact_ranks", "claims.exact_ranks")
    for index, rank in enumerate(ranks):
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= depth:
            _fail("unsupported_exact_rank", f"claims.exact_ranks[{index}]={rank}")
    if rank_semantics == "cutoff_only" and ranks:
        _fail("unsupported_exact_rank", "cutoff_only submission")

    content_sha256 = _sha(value.get("content_sha256"), "content_sha256") or ""
    try:
        valid_hash = verify_content_sha256(value)
    except (TypeError, ValueError):
        _fail("noncanonical_json", EVIDENCE_SUBMISSION_SCHEMA)
    if not valid_hash:
        _fail("content_hash_mismatch", EVIDENCE_SUBMISSION_SCHEMA)
    return EvidenceSubmission(
        submission_id=submission_id,
        producer=dict(producer),
        artifacts=tuple(artifacts),
        claims=json.loads(json.dumps(claims, allow_nan=False)),
        content_sha256=content_sha256,
    )


def build_evidence_submission(
    *,
    submission_id: str,
    producer: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    claims: Mapping[str, Any],
) -> EvidenceSubmission:
    document = with_content_sha256(
        {
            "schema": EVIDENCE_SUBMISSION_SCHEMA,
            "schema_revision": SUBMISSION_SCHEMA_REVISION,
            "submission_id": submission_id,
            "producer": dict(producer),
            "artifacts": sorted(
                (dict(row) for row in artifacts), key=lambda row: str(row.get("artifact_id", ""))
            ),
            "claims": dict(claims),
        }
    )
    return validate_evidence_submission(document)


def load_evidence_submission(path: Path) -> EvidenceSubmission:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _fail("submission_load_failed", f"{path}: {error}")
    if not isinstance(value, Mapping):
        _fail("invalid_type", str(path))
    return validate_evidence_submission(value)


def build_submission_check_report(
    *,
    submission_id: str,
    submission_sha256: str | None,
    status: str,
    bindings: Mapping[str, Any] | None,
    failures: Sequence[Mapping[str, str]],
) -> SubmissionCheckReport:
    document = with_content_sha256(
        {
            "schema": SUBMISSION_CHECK_REPORT_SCHEMA,
            "schema_revision": SUBMISSION_SCHEMA_REVISION,
            "submission_id": submission_id,
            "submission_sha256": submission_sha256,
            "status": status,
            "bindings": dict(bindings) if bindings is not None else None,
            "failures": sorted(
                (dict(row) for row in failures),
                key=lambda row: (str(row.get("code", "")), str(row.get("detail", ""))),
            ),
        }
    )
    return validate_submission_check_report(document)


def validate_submission_check_report(value: Mapping[str, Any]) -> SubmissionCheckReport:
    fields = {
        "schema",
        "schema_revision",
        "submission_id",
        "submission_sha256",
        "status",
        "bindings",
        "failures",
        "content_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("contract_fields_mismatch", SUBMISSION_CHECK_REPORT_SCHEMA)
    if value.get("schema") != SUBMISSION_CHECK_REPORT_SCHEMA:
        _fail("schema_mismatch", str(value.get("schema")))
    if value.get("schema_revision") != SUBMISSION_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    submission_id = _text(value.get("submission_id"), "submission_id", identifier=True)
    submission_sha = _sha(value.get("submission_sha256"), "submission_sha256", nullable=True)
    status = value.get("status")
    if status not in {"accepted", "rejected"}:
        _fail("unsupported_check_status", str(status))
    bindings_raw = value.get("bindings")
    bindings: Mapping[str, Any] | None = None
    if bindings_raw is not None:
        bindings = _exact(
            bindings_raw,
            {
                "profile_id",
                "profile_revision",
                "dataset_identity_sha256",
                "target_universe_sha256",
                "evidence_bundle_sha256",
                "conformance_report_sha256",
                "status_label",
            },
            "bindings",
        )
        _text(bindings.get("profile_id"), "bindings.profile_id")
        _text(bindings.get("profile_revision"), "bindings.profile_revision")
        for field in (
            "dataset_identity_sha256",
            "target_universe_sha256",
            "evidence_bundle_sha256",
            "conformance_report_sha256",
        ):
            _sha(bindings.get(field), f"bindings.{field}")
        _text(bindings.get("status_label"), "bindings.status_label")
    failures_raw = value.get("failures")
    if not isinstance(failures_raw, Sequence) or isinstance(
        failures_raw, (str, bytes, bytearray)
    ):
        _fail("invalid_failures", "failures")
    failures: list[Mapping[str, str]] = []
    failure_keys: list[tuple[str, str]] = []
    for index, raw in enumerate(failures_raw):
        row = _exact(raw, {"code", "detail"}, f"failures[{index}]")
        code = _text(row.get("code"), f"failures[{index}].code")
        detail = _text(row.get("detail"), f"failures[{index}].detail")
        failure_keys.append((code, detail))
        failures.append({"code": code, "detail": detail})
    if failure_keys != sorted(set(failure_keys)):
        _fail("noncanonical_failures", "failures")
    if status == "accepted" and (bindings is None or failures):
        _fail("check_status_mismatch", "accepted")
    if status == "rejected" and (bindings is not None or not failures):
        _fail("check_status_mismatch", "rejected")
    content_sha = _sha(value.get("content_sha256"), "content_sha256") or ""
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", SUBMISSION_CHECK_REPORT_SCHEMA)
    return SubmissionCheckReport(
        submission_id=submission_id,
        submission_sha256=submission_sha,
        status=status,
        bindings=dict(bindings) if bindings is not None else None,
        failures=tuple(failures),
        content_sha256=content_sha,
    )


__all__ = [
    "EVIDENCE_SUBMISSION_SCHEMA",
    "SUBMISSION_ARTIFACT_ROLES",
    "SUBMISSION_CHECK_REPORT_SCHEMA",
    "SUBMISSION_SCHEMA_REVISION",
    "EvidenceSubmission",
    "SubmissionCheckReport",
    "SubmissionValidationError",
    "build_evidence_submission",
    "build_submission_check_report",
    "load_evidence_submission",
    "validate_evidence_submission",
    "validate_submission_check_report",
]
