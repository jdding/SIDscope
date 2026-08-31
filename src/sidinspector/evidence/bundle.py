"""Immutable, content-addressed SIDScope EvidenceBundle v1 contract."""

from __future__ import annotations

import json
import math
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


EVIDENCE_BUNDLE_SCHEMA = "sidscope.evidence_bundle.v1"
EVIDENCE_BUNDLE_SCHEMA_REVISION = "1.0.0"
RANK_SEMANTICS = frozenset({"exact_with_censoring", "cutoff_only"})
ARTIFACT_AVAILABILITY = frozenset({"embedded_public", "hash_reference_only"})
REQUIRED_PROVENANCE_ROLES = (
    "source",
    "data",
    "sid",
    "run",
    "checkpoint",
    "trace",
    "diagnostics",
    "conformance",
)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")

_TOP_LEVEL_FIELDS = {
    "schema",
    "schema_revision",
    "bundle_id",
    "producer",
    "profile_binding",
    "subject",
    "compatibility",
    "artifacts",
    "provenance_edges",
    "result_card",
    "supersedes",
    "privacy",
    "content_sha256",
}
_PRIVACY_FIELDS = {
    "source_user_ids_exported",
    "source_item_ids_exported",
    "absolute_private_paths_exported",
    "checkpoint_payload_exported",
}
_FORBIDDEN_KEYS = {
    "source_user_id",
    "source_user_ids",
    "source_item_id",
    "source_item_ids",
    "raw_user_id",
    "raw_user_ids",
    "raw_item_id",
    "raw_item_ids",
    "user_id",
    "item_id",
    "checkpoint_payload",
    "checkpoint_bytes",
    "checkpoint_state",
    "model_state_dict",
    "credentials",
    "credential",
    "password",
    "passwd",
    "api_key",
    "access_key",
    "secret_key",
    "private_key",
    "authorization",
    "auth_token",
    "access_token",
    "refresh_token",
}
_PRIVATE_PATH_PATTERN = re.compile(
    r"(?:file://)?/(?:Users|home|root|Volumes|private|var/folders)/[^\s\"']+"
    r"|[A-Za-z]:\\Users\\[^\s\"']+"
)
_SECRET_TEXT_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"\b(?:password|passwd|api[_ -]?key|secret[_ -]?key|access[_ -]?token)"
        r"\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bauthorization\s*:\s*bearer\s+\S+", re.IGNORECASE),
    re.compile(
        r"\b(?:source_user_ids?|source_item_ids?|raw_user_ids?|raw_item_ids?|"
        r"checkpoint_payload|checkpoint_bytes)\b\s*[:=]",
        re.IGNORECASE,
    ),
)


class EvidenceBundleValidationError(ValueError):
    """A stable, typed EvidenceBundle admission or storage failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class EvidenceBundle:
    schema: str
    schema_revision: str
    bundle_id: str
    producer: Mapping[str, Any]
    profile_binding: Mapping[str, Any]
    subject: Mapping[str, Any]
    compatibility: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...]
    provenance_edges: tuple[Mapping[str, Any], ...]
    result_card: Mapping[str, Any]
    supersedes: tuple[str, ...]
    privacy: Mapping[str, bool]
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        """Return a deep JSON copy suitable for canonical serialization."""

        return json.loads(
            json.dumps(
                {
                    "schema": self.schema,
                    "schema_revision": self.schema_revision,
                    "bundle_id": self.bundle_id,
                    "producer": self.producer,
                    "profile_binding": self.profile_binding,
                    "subject": self.subject,
                    "compatibility": self.compatibility,
                    "artifacts": self.artifacts,
                    "provenance_edges": self.provenance_edges,
                    "result_card": self.result_card,
                    "supersedes": self.supersedes,
                    "privacy": self.privacy,
                    "content_sha256": self.content_sha256,
                },
                allow_nan=False,
            )
        )


def _fail(code: str, detail: str) -> None:
    raise EvidenceBundleValidationError(code, detail)


def _exact_object(value: Any, fields: set[str], location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("invalid_fields", location)
    return value


def _text(value: Any, field: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be non-empty text")
    if identifier and ID_PATTERN.fullmatch(value) is None:
        _fail("invalid_identifier", field)
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("invalid_count", field)
    return value


def _finite_number(value: Any, field: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("invalid_number", field)
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        _fail("invalid_number", field)
    return result


def scan_evidence_content(value: Any, *, location: str = "$") -> None:
    """Reject identifying fields, private paths, and credential-like material.

    The four mandatory privacy declarations are intentionally permitted only at
    the exact top-level privacy location. Their values are independently
    required to be ``False`` by :func:`validate_evidence_bundle`.
    """

    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                _fail("forbidden_content", f"non-text key at {location}")
            key = raw_key.casefold()
            child_location = f"{location}.{raw_key}"
            privacy_declaration = (
                (location == "$.privacy" or location.endswith(".privacy"))
                and raw_key in _PRIVACY_FIELDS
            )
            if privacy_declaration and child is not False:
                _fail("privacy_boundary_violation", child_location)
            if (key in _FORBIDDEN_KEYS or raw_key in _PRIVACY_FIELDS) and not privacy_declaration:
                _fail("forbidden_field", child_location)
            scan_evidence_content(child, location=child_location)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            scan_evidence_content(child, location=f"{location}[{index}]")
        return
    if isinstance(value, str):
        if _PRIVATE_PATH_PATTERN.search(value):
            _fail("private_path_exposure", location)
        if any(pattern.search(value) for pattern in _SECRET_TEXT_PATTERNS):
            _fail("credential_exposure", location)


def _validate_metric_map(value: Any, field: str, *, nonempty: bool = False) -> None:
    if not isinstance(value, Mapping) or (nonempty and not value):
        _fail("invalid_metrics", field)
    for key, metric in value.items():
        _text(key, f"{field}.key")
        _finite_number(metric, f"{field}.{key}")


def _validate_result_card(value: Any, compatibility: Mapping[str, Any]) -> Mapping[str, Any]:
    result = _exact_object(
        value,
        {
            "overall_metrics",
            "slice_metrics",
            "failure_counts",
            "compute",
            "rank_observations",
        },
        "result_card",
    )
    _validate_metric_map(result.get("overall_metrics"), "result_card.overall_metrics", nonempty=True)
    slices = result.get("slice_metrics")
    if not isinstance(slices, Mapping):
        _fail("invalid_metrics", "result_card.slice_metrics")
    for slice_id, metrics in slices.items():
        _text(slice_id, "result_card.slice_metrics key")
        _validate_metric_map(metrics, f"result_card.slice_metrics.{slice_id}", nonempty=True)
    failures = result.get("failure_counts")
    if not isinstance(failures, Mapping):
        _fail("invalid_failure_counts", "result_card.failure_counts")
    for failure, count in failures.items():
        _text(failure, "result_card.failure_counts key")
        _count(count, f"result_card.failure_counts.{failure}")
    compute = result.get("compute")
    if not isinstance(compute, Mapping):
        _fail("invalid_compute", "result_card.compute")
    for measure, number in compute.items():
        _text(measure, "result_card.compute key")
        _finite_number(number, f"result_card.compute.{measure}", nonnegative=True)
    ranks = _exact_object(
        result.get("rank_observations"),
        {"exact_count", "censored_count", "exact_ranks"},
        "result_card.rank_observations",
    )
    exact_count = _count(ranks.get("exact_count"), "result_card.rank_observations.exact_count")
    censored_count = _count(
        ranks.get("censored_count"), "result_card.rank_observations.censored_count"
    )
    if exact_count + censored_count < 1:
        _fail("empty_rank_observations", "result_card.rank_observations")
    exact_ranks = ranks.get("exact_ranks")
    if not isinstance(exact_ranks, Sequence) or isinstance(
        exact_ranks, (str, bytes, bytearray)
    ):
        _fail("invalid_exact_ranks", "result_card.rank_observations.exact_ranks")
    if len(exact_ranks) != exact_count:
        _fail("exact_rank_count_mismatch", f"{len(exact_ranks)} != {exact_count}")
    publication_depth = compatibility["publication_depth"]
    for index, rank in enumerate(exact_ranks):
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= publication_depth:
            _fail(
                "unsupported_exact_rank_claim",
                f"result_card.rank_observations.exact_ranks[{index}]={rank}",
            )
    rank_semantics = compatibility["rank_semantics"]
    cutoff = compatibility["evaluation_cutoff"]
    depth = compatibility["publication_depth"]
    if rank_semantics == "cutoff_only" and depth != cutoff:
        _fail("rank_semantics_mismatch", "cutoff_only requires publication_depth == evaluation_cutoff")
    if rank_semantics == "cutoff_only" and (exact_count != 0 or exact_ranks):
        _fail("unsupported_exact_rank_claim", "cutoff_only cannot publish exact ranks")
    return result


def _validate_provenance(
    artifacts: Sequence[Mapping[str, Any]], edges: Any
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(edges, Sequence) or isinstance(edges, (str, bytes, bytearray)):
        _fail("invalid_provenance_edges", "provenance_edges")
    artifact_ids = {row["artifact_id"] for row in artifacts}
    roles_by_id = {row["artifact_id"]: row["role"] for row in artifacts}
    graph: dict[str, set[str]] = {artifact_id: set() for artifact_id in artifact_ids}
    edge_rows: list[Mapping[str, Any]] = []
    edge_keys: list[tuple[str, str, str]] = []
    role_links: set[tuple[str, str]] = set()
    for index, raw in enumerate(edges):
        row = _exact_object(
            raw,
            {"from_artifact", "to_artifact", "relation"},
            f"provenance_edges[{index}]",
        )
        source = _text(row.get("from_artifact"), f"provenance_edges[{index}].from_artifact")
        target = _text(row.get("to_artifact"), f"provenance_edges[{index}].to_artifact")
        relation = _text(row.get("relation"), f"provenance_edges[{index}].relation")
        if source not in artifact_ids or target not in artifact_ids:
            _fail("unknown_provenance_artifact", f"{source}->{target}")
        key = (source, target, relation)
        edge_keys.append(key)
        graph[source].add(target)
        role_links.add((roles_by_id[source], roles_by_id[target]))
        edge_rows.append(dict(row))
    if edge_keys != sorted(set(edge_keys)):
        _fail("noncanonical_provenance_edges", "provenance_edges must be unique and sorted")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            _fail("provenance_cycle", node)
        if node in visited:
            return
        visiting.add(node)
        for target in sorted(graph[node]):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for artifact_id in sorted(graph):
        visit(artifact_id)

    present_roles = set(roles_by_id.values())
    missing = [role for role in REQUIRED_PROVENANCE_ROLES if role not in present_roles]
    if missing:
        _fail("missing_provenance_role", ",".join(missing))
    missing_links = [
        f"{source}->{target}"
        for source, target in zip(REQUIRED_PROVENANCE_ROLES, REQUIRED_PROVENANCE_ROLES[1:])
        if (source, target) not in role_links
    ]
    if missing_links:
        _fail("disconnected_provenance_chain", ",".join(missing_links))
    return tuple(edge_rows)


def validate_evidence_bundle(value: Mapping[str, Any]) -> EvidenceBundle:
    """Validate a complete EvidenceBundle v1 without consulting external state."""

    if not isinstance(value, Mapping) or set(value) != _TOP_LEVEL_FIELDS:
        _fail("contract_fields_mismatch", EVIDENCE_BUNDLE_SCHEMA)
    if value.get("schema") != EVIDENCE_BUNDLE_SCHEMA:
        _fail("schema_mismatch", str(value.get("schema")))
    if value.get("schema_revision") != EVIDENCE_BUNDLE_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    bundle_id = _text(value.get("bundle_id"), "bundle_id", identifier=True)

    producer = _exact_object(value.get("producer"), {"name", "version"}, "producer")
    _text(producer.get("name"), "producer.name")
    _text(producer.get("version"), "producer.version")

    profile = _exact_object(
        value.get("profile_binding"),
        {"profile_id", "profile_revision", "conformance_report_sha256"},
        "profile_binding",
    )
    _text(profile.get("profile_id"), "profile_binding.profile_id")
    _text(profile.get("profile_revision"), "profile_binding.profile_revision")
    _sha(profile.get("conformance_report_sha256"), "profile_binding.conformance_report_sha256")

    subject = _exact_object(
        value.get("subject"), {"adapter_id", "method_family"}, "subject"
    )
    _text(subject.get("adapter_id"), "subject.adapter_id", identifier=True)
    _text(subject.get("method_family"), "subject.method_family", identifier=True)

    compatibility = _exact_object(
        value.get("compatibility"),
        {
            "dataset_identity_sha256",
            "target_universe_sha256",
            "evaluation_cutoff",
            "publication_depth",
            "rank_semantics",
        },
        "compatibility",
    )
    _sha(compatibility.get("dataset_identity_sha256"), "compatibility.dataset_identity_sha256")
    _sha(compatibility.get("target_universe_sha256"), "compatibility.target_universe_sha256")
    cutoff = _count(compatibility.get("evaluation_cutoff"), "compatibility.evaluation_cutoff")
    depth = _count(compatibility.get("publication_depth"), "compatibility.publication_depth")
    if cutoff < 1 or depth < cutoff:
        _fail("invalid_evaluation_depth", f"cutoff={cutoff}, publication_depth={depth}")
    rank_semantics = compatibility.get("rank_semantics")
    if rank_semantics not in RANK_SEMANTICS:
        _fail("unsupported_rank_semantics", str(rank_semantics))

    artifacts_raw = value.get("artifacts")
    if not isinstance(artifacts_raw, Sequence) or isinstance(
        artifacts_raw, (str, bytes, bytearray)
    ) or not artifacts_raw:
        _fail("invalid_artifacts", "artifacts")
    artifacts: list[Mapping[str, Any]] = []
    artifact_ids: list[str] = []
    for index, raw in enumerate(artifacts_raw):
        row = _exact_object(
            raw,
            {
                "artifact_id",
                "role",
                "schema_id",
                "schema_revision",
                "content_sha256",
                "object_sha256",
                "size_bytes",
                "media_type",
                "availability",
            },
            f"artifacts[{index}]",
        )
        artifact_id = _text(row.get("artifact_id"), f"artifacts[{index}].artifact_id", identifier=True)
        artifact_ids.append(artifact_id)
        _text(row.get("role"), f"artifacts[{index}].role", identifier=True)
        _text(row.get("schema_id"), f"artifacts[{index}].schema_id")
        _text(row.get("schema_revision"), f"artifacts[{index}].schema_revision")
        _sha(row.get("content_sha256"), f"artifacts[{index}].content_sha256")
        _sha(row.get("object_sha256"), f"artifacts[{index}].object_sha256")
        _count(row.get("size_bytes"), f"artifacts[{index}].size_bytes")
        _text(row.get("media_type"), f"artifacts[{index}].media_type")
        if row.get("availability") not in ARTIFACT_AVAILABILITY:
            _fail("unsupported_artifact_availability", f"artifacts[{index}].availability")
        artifacts.append(dict(row))
    if artifact_ids != sorted(set(artifact_ids)):
        _fail("noncanonical_artifacts", "artifact_id values must be unique and sorted")
    conformance_hashes = {
        row["content_sha256"] for row in artifacts if row["role"] == "conformance"
    }
    if profile["conformance_report_sha256"] not in conformance_hashes:
        _fail(
            "conformance_profile_binding_mismatch",
            "profile_binding.conformance_report_sha256 is not a conformance artifact",
        )

    provenance_edges = _validate_provenance(artifacts, value.get("provenance_edges"))
    result_card = _validate_result_card(value.get("result_card"), compatibility)

    supersedes_raw = value.get("supersedes")
    if not isinstance(supersedes_raw, Sequence) or isinstance(
        supersedes_raw, (str, bytes, bytearray)
    ):
        _fail("invalid_supersedes", "supersedes")
    supersedes = tuple(_sha(item, f"supersedes[{index}]") for index, item in enumerate(supersedes_raw))
    if list(supersedes) != sorted(set(supersedes)):
        _fail("noncanonical_supersedes", "supersedes must be unique and sorted")

    privacy = _exact_object(value.get("privacy"), _PRIVACY_FIELDS, "privacy")
    if any(not isinstance(flag, bool) for flag in privacy.values()) or any(privacy.values()):
        _fail("privacy_boundary_violation", str(dict(privacy)))

    content_sha256 = _sha(value.get("content_sha256"), "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", "content_sha256 does not bind canonical JSON v1")
    if content_sha256 in supersedes:
        _fail("self_supersession", content_sha256)
    scan_evidence_content(value)

    return EvidenceBundle(
        schema=EVIDENCE_BUNDLE_SCHEMA,
        schema_revision=EVIDENCE_BUNDLE_SCHEMA_REVISION,
        bundle_id=bundle_id,
        producer=dict(producer),
        profile_binding=dict(profile),
        subject=dict(subject),
        compatibility=dict(compatibility),
        artifacts=tuple(artifacts),
        provenance_edges=provenance_edges,
        result_card=dict(result_card),
        supersedes=supersedes,
        privacy={key: bool(value) for key, value in privacy.items()},
        content_sha256=content_sha256,
    )


def load_evidence_bundle(path: Path) -> EvidenceBundle:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail("bundle_load_failed", f"{path}: {exc}")
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain a JSON object")
    return validate_evidence_bundle(value)


def build_evidence_bundle(
    *,
    bundle_id: str,
    producer: Mapping[str, Any],
    profile_binding: Mapping[str, Any],
    subject: Mapping[str, Any],
    compatibility: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    provenance_edges: Sequence[Mapping[str, Any]],
    result_card: Mapping[str, Any],
    supersedes: Sequence[str] = (),
    privacy: Mapping[str, bool] | None = None,
) -> EvidenceBundle:
    """Build, canonically order, hash, and validate an EvidenceBundle v1."""

    document = with_content_sha256(
        {
            "schema": EVIDENCE_BUNDLE_SCHEMA,
            "schema_revision": EVIDENCE_BUNDLE_SCHEMA_REVISION,
            "bundle_id": bundle_id,
            "producer": dict(producer),
            "profile_binding": dict(profile_binding),
            "subject": dict(subject),
            "compatibility": dict(compatibility),
            "artifacts": sorted(
                (dict(row) for row in artifacts), key=lambda row: row.get("artifact_id", "")
            ),
            "provenance_edges": sorted(
                (dict(row) for row in provenance_edges),
                key=lambda row: (
                    row.get("from_artifact", ""),
                    row.get("to_artifact", ""),
                    row.get("relation", ""),
                ),
            ),
            "result_card": dict(result_card),
            "supersedes": sorted(supersedes),
            "privacy": dict(
                privacy
                if privacy is not None
                else {
                    "source_user_ids_exported": False,
                    "source_item_ids_exported": False,
                    "absolute_private_paths_exported": False,
                    "checkpoint_payload_exported": False,
                }
            ),
        }
    )
    return validate_evidence_bundle(document)


__all__ = [
    "ARTIFACT_AVAILABILITY",
    "EVIDENCE_BUNDLE_SCHEMA",
    "EVIDENCE_BUNDLE_SCHEMA_REVISION",
    "EvidenceBundle",
    "EvidenceBundleValidationError",
    "REQUIRED_PROVENANCE_ROLES",
    "build_evidence_bundle",
    "load_evidence_bundle",
    "scan_evidence_content",
    "validate_evidence_bundle",
]
