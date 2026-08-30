"""Dataset-neutral, fail-closed checker for third-party evidence packages."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from sidinspector.contracts.hashing import canonical_json_bytes
from sidinspector.conformance_core import (
    DATASET_PROFILE_DESCRIPTOR_SCHEMA,
    PROFILE_CONFORMANCE_REPORT_SCHEMA,
    ProfileEngineError,
    validate_dataset_profile_descriptor,
    validate_profile_conformance_report,
)
from sidinspector.evidence.bundle import (
    EvidenceBundle,
    EvidenceBundleValidationError,
    scan_evidence_content,
    validate_evidence_bundle,
)

from .contracts import (
    EvidenceSubmission,
    SubmissionCheckReport,
    SubmissionValidationError,
    build_submission_check_report,
    validate_evidence_submission,
)


@dataclass(frozen=True)
class ValidatedSubmission:
    submission: EvidenceSubmission
    descriptor: Mapping[str, Any]
    conformance_report: Mapping[str, Any]
    evidence_bundle: EvidenceBundle


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


def _read_json_bytes(payload: bytes, location: str) -> Mapping[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        _fail("invalid_json_artifact", f"{location}: {error}")
    if not isinstance(value, Mapping):
        _fail("invalid_json_artifact", f"{location}: expected object")
    if payload != canonical_json_bytes(value) + b"\n":
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
    """Validate a complete package using only versioned public JSON contracts."""

    root = Path(root)
    if not root.is_dir():
        _fail("submission_root_missing", "submission root is not a directory")
    manifest_file = _safe_relative_file(root, manifest_path, "manifest")
    manifest_payload = manifest_file.read_bytes()
    manifest_value = _read_json_bytes(manifest_payload, "submission")
    submission = validate_evidence_submission(manifest_value)

    loaded_bytes: dict[str, bytes] = {}
    documents_by_role: dict[str, Mapping[str, Any]] = {}
    rows_by_sha: dict[str, Mapping[str, Any]] = {}
    for row in submission.artifacts:
        relative = str(row["path"])
        path = _safe_relative_file(root, relative, f"artifact:{row['artifact_id']}")
        payload = path.read_bytes()
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
    )


def _manifest_identity(root: Path, manifest_path: str) -> tuple[str, str | None]:
    try:
        path = _safe_relative_file(root, manifest_path, "manifest")
        payload = path.read_bytes()
    except (SubmissionValidationError, OSError):
        return "unresolved", None
    raw_sha = _file_sha256(payload)
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return "unresolved", raw_sha
    submission_id = value.get("submission_id") if isinstance(value, Mapping) else None
    if not isinstance(submission_id, str) or not submission_id:
        submission_id = "unresolved"
    return submission_id, raw_sha


def check_submission(
    root: Path, *, manifest_path: str = "submission.json"
) -> SubmissionCheckReport:
    """Return a deterministic accepted/rejected report for one package root."""

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


__all__ = [
    "DATASET_PROFILE_DESCRIPTOR_SCHEMA",
    "PROFILE_CONFORMANCE_REPORT_SCHEMA",
    "ValidatedSubmission",
    "check_submission",
    "validate_submission_package",
]
