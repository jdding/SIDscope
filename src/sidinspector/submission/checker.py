"""Dataset-neutral, fail-closed checker for third-party evidence packages."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from sidinspector.contracts import canonical_json_bytes
from sidinspector.conformance_core import (
    DATASET_PROFILE_DESCRIPTOR_SCHEMA,
    PROFILE_CONFORMANCE_REPORT_SCHEMA,
    ProfileEngineError,
    validate_dataset_profile_descriptor,
    validate_profile_conformance_report,
)
from sidinspector.evidence import (
    EvidenceBundle,
    EvidenceBundleValidationError,
    scan_evidence_content,
    validate_evidence_bundle,
)

from .contracts import (
    ID_PATTERN,
    EvidenceSubmission,
    SubmissionCheckReport,
    SubmissionValidationError,
    build_submission_check_report,
    validate_evidence_submission,
)
from sidinspector.evidence import recompute_bundle


# Bounded public interchange, not a container for full training traces.
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_SUBMISSION_BYTES = 64 * 1024 * 1024
MAX_SUBMISSION_ARTIFACTS = 256
MAX_JSON_DEPTH = 64


@dataclass(frozen=True)
class ValidatedSubmission:
    submission: EvidenceSubmission
    descriptor: Mapping[str, Any]
    conformance_report: Mapping[str, Any]
    evidence_bundle: EvidenceBundle
    objects: Mapping[str, bytes] = field(default_factory=dict)


def _fail(code: str, detail: str) -> None:
    raise SubmissionValidationError(code, detail)


def _file_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_relative_file(root: Path, relative: str, location: str) -> Path:
    if "\\" in relative:
        _fail("noncanonical_submission_path", location)
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        _fail("submission_path_escape", location)
    if pure.as_posix() != relative:
        _fail("noncanonical_submission_path", location)
    root_resolved = root.resolve()
    candidate = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            _fail("submission_symlink_forbidden", location)
    if not candidate.is_file():
        _fail("missing_submission_file", f"{location}: {relative}")
    try:
        candidate.resolve().relative_to(root_resolved)
    except ValueError:
        _fail("submission_path_escape", location)
    return candidate


def _bounded_read(path: Path, location: str, *, remaining: int | None = None) -> bytes:
    if remaining is None:
        remaining = MAX_SUBMISSION_BYTES
    limit = min(MAX_ARTIFACT_BYTES, remaining)
    code = "submission_artifact_too_large" if limit == MAX_ARTIFACT_BYTES else "submission_total_too_large"
    try:
        if path.stat().st_size > limit:
            _fail(code, location)
        with path.open("rb") as handle:
            payload = handle.read(limit + 1)
    except OSError:
        _fail("submission_read_failed", location)
    if len(payload) > limit:
        _fail(code, location)
    return payload


def _check_json_depth(payload: bytes, location: str) -> None:
    # Lexical preflight runs before the recursive JSON decoder. Braces inside
    # strings, including escaped quotes, do not contribute to nesting depth.
    depth = 0
    quoted = escaped = False
    for byte in payload:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > MAX_JSON_DEPTH:
                _fail("submission_json_depth_exceeded", location)
        elif byte in (93, 125):
            depth -= 1


def _read_json_bytes(payload: bytes, location: str) -> Mapping[str, Any]:
    _check_json_depth(payload, location)
    try:
        value = json.loads(payload.decode("utf-8"))
    except RecursionError:
        _fail("submission_json_depth_exceeded", location)
    except (UnicodeError, ValueError):
        _fail("invalid_json_artifact", location)
    if not isinstance(value, Mapping):
        _fail("invalid_json_artifact", f"{location}: expected object")
    try:
        canonical = canonical_json_bytes(value) + b"\n"
    except (ValueError, UnicodeError):
        _fail("invalid_json_artifact", location)
    if payload != canonical:
        _fail("noncanonical_json_artifact", location)
    try:
        scan_evidence_content(value, location=location)
    except EvidenceBundleValidationError as error:
        _fail(error.code, error.detail)
    return value


def _scan_payload(payload: bytes, media_type: str, location: str) -> None:
    if "json" in media_type.casefold():
        _read_json_bytes(payload, location)
        return
    try:
        text = payload.decode("utf-8")
    except UnicodeError:
        return
    try:
        scan_evidence_content(text, location=location)
    except EvidenceBundleValidationError as error:
        _fail(error.code, error.detail)


def validate_submission_package(
    root: Path, *, manifest_path: str = "submission.json"
) -> ValidatedSubmission:
    """Validate structural bindings, not gate execution or independent admission."""

    root = Path(root)
    if not root.is_dir():
        _fail("submission_root_missing", "submission root is not a directory")
    manifest_file = _safe_relative_file(root, manifest_path, "manifest")
    manifest_payload = _bounded_read(manifest_file, "manifest")
    manifest_value = _read_json_bytes(manifest_payload, "submission")
    artifacts = manifest_value.get("artifacts")
    if isinstance(artifacts, list) and len(artifacts) > MAX_SUBMISSION_ARTIFACTS:
        _fail("submission_artifact_count_exceeded", "artifacts")
    submission = validate_evidence_submission(manifest_value)
    total_bytes = len(manifest_payload)

    loaded_bytes: dict[str, bytes] = {}
    documents_by_role: dict[str, Mapping[str, Any]] = {}
    rows_by_sha: dict[str, Mapping[str, Any]] = {}
    for row in submission.artifacts:
        relative = str(row["path"])
        path = _safe_relative_file(root, relative, f"artifact:{row['artifact_id']}")
        payload = _bounded_read(path, str(row["artifact_id"]), remaining=MAX_SUBMISSION_BYTES - total_bytes)
        total_bytes += len(payload)
        observed = _file_sha256(payload)
        if observed != row["sha256"]:
            _fail("artifact_hash_mismatch", str(row["artifact_id"]))
        loaded_bytes[str(row["artifact_id"])] = payload
        rows_by_sha[observed] = row
        if row["role"] != "evidence_object":
            documents_by_role[str(row["role"])] = _read_json_bytes(
                payload, f"artifact:{row['artifact_id']}"
            )

    try:
        descriptor_contract = validate_dataset_profile_descriptor(
            documents_by_role["dataset_profile_descriptor"]
        )
        report_contract = validate_profile_conformance_report(
            documents_by_role["profile_conformance_report"],
            descriptor=descriptor_contract,
        )
    except ProfileEngineError as error:
        _fail(error.code, error.detail)
    descriptor = descriptor_contract.to_dict()
    report = report_contract.to_dict()
    try:
        bundle = validate_evidence_bundle(documents_by_role["evidence_bundle"])
    except EvidenceBundleValidationError as error:
        _fail(error.code, error.detail)

    claims = submission.claims
    profile = report["profile_binding"]
    if (
        claims["profile_id"] != profile["profile_id"]
        or claims["profile_revision"] != profile["profile_revision"]
        or bundle.profile_binding["profile_id"] != profile["profile_id"]
        or bundle.profile_binding["profile_revision"] != profile["profile_revision"]
    ):
        _fail("profile_mismatch", str(profile))
    if bundle.profile_binding["conformance_report_sha256"] != report["content_sha256"]:
        _fail("conformance_binding_mismatch", "evidence_bundle.profile_binding")
    descriptor_binding = report["descriptor_binding"]
    if descriptor_binding["content_sha256"] != descriptor["content_sha256"]:
        _fail("descriptor_binding_mismatch", "conformance_report.descriptor_binding")

    compatibility = bundle.compatibility
    dataset_values = {
        claims["dataset_identity_sha256"],
        descriptor["dataset_identity_sha256"],
        compatibility["dataset_identity_sha256"],
    }
    target_values = {
        claims["target_universe_sha256"],
        descriptor["target_universe"]["content_sha256"],
        compatibility["target_universe_sha256"],
    }
    if len(dataset_values) != 1:
        _fail("dataset_binding_mismatch", str(sorted(dataset_values)))
    if len(target_values) != 1:
        _fail("target_universe_mismatch", str(sorted(target_values)))
    evaluation = descriptor["evaluation"]
    if not (
        claims["evaluation_cutoff"]
        == compatibility["evaluation_cutoff"]
        == evaluation["cutoff"]
        and claims["publication_depth"]
        == compatibility["publication_depth"]
        == evaluation["publication_depth"]
    ):
        _fail("evaluation_contract_mismatch", "cutoff/publication_depth")
    if claims["rank_semantics"] != compatibility["rank_semantics"]:
        _fail("rank_semantics_mismatch", str(claims["rank_semantics"]))
    bundle_ranks = bundle.result_card["rank_observations"]
    if list(claims["exact_ranks"]) != list(bundle_ranks["exact_ranks"]):
        _fail("exact_rank_claim_mismatch", "submission claims != EvidenceBundle")
    if any(rank > compatibility["publication_depth"] for rank in claims["exact_ranks"]):
        _fail("unsupported_exact_rank", "rank exceeds publication depth")

    expected_slices = {row["slice_id"] for row in evaluation["slices"]}
    observed_slices = {"overall", *bundle.result_card["slice_metrics"].keys()}
    missing_slices = sorted(expected_slices - observed_slices)
    if missing_slices:
        _fail("missing_result_slice", ",".join(missing_slices))
    if report["decision"]["status"] == "fail":
        _fail("conformance_not_passed", str(report["decision"]["status"]))

    required_object_hashes: set[str] = set()
    media_type_by_hash: dict[str, str] = {}
    size_by_hash: dict[str, int] = {}
    for artifact in bundle.artifacts:
        if artifact["role"] == "checkpoint" and artifact["availability"] == "embedded_public":
            _fail("checkpoint_payload_forbidden", str(artifact["artifact_id"]))
        if artifact["availability"] == "embedded_public":
            object_sha = str(artifact["object_sha256"])
            required_object_hashes.add(object_sha)
            media_type_by_hash[object_sha] = str(artifact["media_type"])
            size_by_hash[object_sha] = int(artifact["size_bytes"])
    supplied_object_hashes = {
        str(row["sha256"])
        for row in submission.artifacts
        if row["role"] == "evidence_object"
    }
    available_hashes = set(rows_by_sha)
    missing_objects = sorted(required_object_hashes - available_hashes)
    if missing_objects:
        _fail("missing_evidence_object", ",".join(missing_objects))
    unexpected_objects = sorted(supplied_object_hashes - required_object_hashes)
    if unexpected_objects:
        _fail("unexpected_evidence_object", ",".join(unexpected_objects))
    for digest in sorted(required_object_hashes):
        row = rows_by_sha[digest]
        payload = loaded_bytes[str(row["artifact_id"])]
        if len(payload) != size_by_hash[digest]:
            _fail("evidence_object_size_mismatch", digest)
        _scan_payload(payload, media_type_by_hash[digest], f"evidence_object:{digest}")

    return ValidatedSubmission(
        submission=submission,
        descriptor=json.loads(json.dumps(descriptor)),
        conformance_report=json.loads(json.dumps(report)),
        evidence_bundle=bundle,
        objects={digest: loaded_bytes[str(rows_by_sha[digest]["artifact_id"])] for digest in required_object_hashes},
    )


def _manifest_identity(root: Path, manifest_path: str) -> tuple[str, str | None]:
    try:
        path = _safe_relative_file(root, manifest_path, "manifest")
        payload = _bounded_read(path, "manifest")
    except (SubmissionValidationError, OSError):
        return "unresolved", None
    raw_sha = _file_sha256(payload)
    try:
        _check_json_depth(payload, "manifest")
        value = json.loads(payload.decode("utf-8"))
    except (SubmissionValidationError, UnicodeError, ValueError, RecursionError):
        return "unresolved", raw_sha
    submission_id = value.get("submission_id") if isinstance(value, Mapping) else None
    if not isinstance(submission_id, str) or ID_PATTERN.fullmatch(submission_id) is None:
        submission_id = "unresolved"
    return submission_id, raw_sha


def replay_submission_check(
    root: Path, *, manifest_path: str = "submission.json"
) -> SubmissionCheckReport:
    """Replay historical v1 structural checking; never use this as new admission."""

    try:
        validated = validate_submission_package(root, manifest_path=manifest_path)
    except SubmissionValidationError as error:
        submission_id, raw_sha = _manifest_identity(Path(root), manifest_path)
        return build_submission_check_report(
            submission_id=submission_id,
            submission_sha256=raw_sha,
            status="rejected",
            bindings=None,
            failures=[{"code": error.code, "detail": error.detail}],
        )
    bundle = validated.evidence_bundle
    report = validated.conformance_report
    return build_submission_check_report(
        submission_id=validated.submission.submission_id,
        submission_sha256=_file_sha256(
            canonical_json_bytes(validated.submission.to_dict()) + b"\n"
        ),
        status="accepted",
        bindings={
            "profile_id": bundle.profile_binding["profile_id"],
            "profile_revision": bundle.profile_binding["profile_revision"],
            "dataset_identity_sha256": bundle.compatibility["dataset_identity_sha256"],
            "target_universe_sha256": bundle.compatibility["target_universe_sha256"],
            "evidence_bundle_sha256": bundle.content_sha256,
            "conformance_report_sha256": report["content_sha256"],
            "status_label": report["decision"]["status_label"],
        },
        failures=[],
    )


def require_verified_admission(submission: ValidatedSubmission) -> dict[str, Any]:
    """Execute verification each time; no cached flag or caller label grants trust."""
    if not any(row["role"] == "evaluation_protocol" for row in submission.evidence_bundle.artifacts):
        _fail("independent_gate_verification_required", submission.submission.submission_id)
    try:
        return recompute_bundle(submission.evidence_bundle, submission.objects)
    except EvidenceBundleValidationError as error:
        _fail(error.code, error.detail)


def check_submission(
    root: Path, *, manifest_path: str = "submission.json"
) -> SubmissionCheckReport:
    """Admit only the diagnostic scope actually recomputed from bound inputs."""
    structural = replay_submission_check(root, manifest_path=manifest_path)
    if structural.status == "rejected":
        return structural
    try:
        verified = require_verified_admission(validate_submission_package(root, manifest_path=manifest_path))
    except SubmissionValidationError as error:
        return build_submission_check_report(
            submission_id=structural.submission_id, submission_sha256=structural.submission_sha256,
            status="rejected", bindings=None, failures=[{"code": error.code, "detail": error.detail}],
        )
    return build_submission_check_report(
        submission_id=structural.submission_id,
        submission_sha256=structural.submission_sha256,
        status="accepted",
        bindings={**structural.bindings, "status_label": verified["status_label"]},
        failures=[],
    )


__all__ = [
    "DATASET_PROFILE_DESCRIPTOR_SCHEMA",
    "PROFILE_CONFORMANCE_REPORT_SCHEMA",
    "ValidatedSubmission",
    "check_submission",
    "validate_submission_package",
]
