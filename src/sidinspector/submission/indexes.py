"""Deterministic status/result views derived from accepted submissions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sidinspector.contracts.hashing import canonical_json_bytes, with_content_sha256

from .checker import ValidatedSubmission
from .contracts import SubmissionValidationError


STATUS_INDEX_SCHEMA = "sidscope.adapter_status_index.v1"
RESULT_INDEX_SCHEMA = "sidscope.adapter_result_index.v1"
LEGACY_PARITY_SCHEMA = "sidscope.legacy_status_parity.v1"
INDEX_SCHEMA_REVISION = "1.0.0"
INDEX_AUTHORITY = "profile_conformance_reports"


def _fail(code: str, detail: str) -> None:
    raise SubmissionValidationError(code, detail)


def _active_submissions(
    submissions: Sequence[ValidatedSubmission],
) -> list[ValidatedSubmission]:
    by_hash: dict[str, ValidatedSubmission] = {}
    for submission in submissions:
        digest = submission.evidence_bundle.content_sha256
        if digest in by_hash:
            _fail("duplicate_submission_bundle", digest)
        by_hash[digest] = submission
    superseded = {
        digest
        for submission in submissions
        for digest in submission.evidence_bundle.supersedes
    }
    active = [
        submission
        for digest, submission in by_hash.items()
        if digest not in superseded
    ]
    return sorted(
        active,
        key=lambda item: (
            str(item.evidence_bundle.subject["adapter_id"]),
            str(item.evidence_bundle.compatibility["dataset_identity_sha256"]),
            str(item.evidence_bundle.profile_binding["profile_id"]),
            str(item.evidence_bundle.profile_binding["profile_revision"]),
            item.evidence_bundle.content_sha256,
        ),
    )


def _identity_row(submission: ValidatedSubmission) -> dict[str, Any]:
    bundle = submission.evidence_bundle
    report = submission.conformance_report
    return {
        "adapter_id": bundle.subject["adapter_id"],
        "method_family": bundle.subject["method_family"],
        "profile_id": bundle.profile_binding["profile_id"],
        "profile_revision": bundle.profile_binding["profile_revision"],
        "dataset_identity_sha256": bundle.compatibility["dataset_identity_sha256"],
        "target_universe_sha256": bundle.compatibility["target_universe_sha256"],
        "evidence_bundle_sha256": bundle.content_sha256,
        "conformance_report_sha256": report["content_sha256"],
    }


def generate_status_index(
    submissions: Sequence[ValidatedSubmission],
) -> dict[str, Any]:
    """Generate the active status view solely from conformance decisions."""

    entries = []
    for submission in _active_submissions(submissions):
        decision = submission.conformance_report["decision"]
        entries.append(
            {
                **_identity_row(submission),
                "decision_status": decision["status"],
                "status_label": decision["status_label"],
            }
        )
    return with_content_sha256(
        {
            "schema": STATUS_INDEX_SCHEMA,
            "schema_revision": INDEX_SCHEMA_REVISION,
            "authority": INDEX_AUTHORITY,
            "entries": entries,
        }
    )


def generate_result_index(
    submissions: Sequence[ValidatedSubmission],
) -> dict[str, Any]:
    """Generate active result cards without reinterpreting bundle metrics."""

    entries = []
    for submission in _active_submissions(submissions):
        entries.append(
            {
                **_identity_row(submission),
                "result_card": submission.evidence_bundle.to_dict()["result_card"],
            }
        )
    return with_content_sha256(
        {
            "schema": RESULT_INDEX_SCHEMA,
            "schema_revision": INDEX_SCHEMA_REVISION,
            "authority": "evidence_bundles",
            "entries": entries,
        }
    )


def generate_submission_indexes(
    submissions: Sequence[ValidatedSubmission],
) -> tuple[dict[str, Any], dict[str, Any]]:
    return generate_status_index(submissions), generate_result_index(submissions)


def canonical_index_bytes(index: Mapping[str, Any]) -> bytes:
    """Serialize a generated index without paths, timestamps, or host state."""

    return canonical_json_bytes(index) + b"\n"


def legacy_status_parity(
    generated_status_index: Mapping[str, Any],
    legacy_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare a read-only legacy view; it never participates in generation.

    Legacy input is intentionally projected to only ``adapter_id`` and
    ``status_label``. Paths, comments, and historical mutable metadata cannot
    enter the generated authority.
    """

    if generated_status_index.get("schema") != STATUS_INDEX_SCHEMA:
        _fail("status_index_schema_mismatch", str(generated_status_index.get("schema")))
    generated_entries = generated_status_index.get("entries")
    if not isinstance(generated_entries, Sequence) or isinstance(
        generated_entries, (str, bytes, bytearray)
    ):
        _fail("invalid_status_index", "entries")
    generated: dict[str, str] = {}
    for index, row in enumerate(generated_entries):
        if not isinstance(row, Mapping):
            _fail("invalid_status_entry", str(index))
        adapter_id = row.get("adapter_id")
        label = row.get("status_label")
        if not isinstance(adapter_id, str) or not isinstance(label, str):
            _fail("invalid_status_entry", str(index))
        if adapter_id in generated:
            _fail("ambiguous_legacy_adapter", adapter_id)
        generated[adapter_id] = label
    legacy: dict[str, str] = {}
    for index, row in enumerate(legacy_rows):
        if not isinstance(row, Mapping):
            _fail("invalid_legacy_row", str(index))
        adapter_id = row.get("adapter_id")
        label = row.get("status_label", row.get("status"))
        if not isinstance(adapter_id, str) or not adapter_id:
            _fail("invalid_legacy_row", f"{index}.adapter_id")
        if not isinstance(label, str) or not label:
            _fail("invalid_legacy_row", f"{index}.status_label")
        if adapter_id in legacy:
            _fail("duplicate_legacy_adapter", adapter_id)
        legacy[adapter_id] = label
    adapter_ids = sorted(set(generated) | set(legacy))
    differences = [
        {
            "adapter_id": adapter_id,
            "generated_status_label": generated.get(adapter_id),
            "legacy_status_label": legacy.get(adapter_id),
        }
        for adapter_id in adapter_ids
        if generated.get(adapter_id) != legacy.get(adapter_id)
    ]
    return with_content_sha256(
        {
            "schema": LEGACY_PARITY_SCHEMA,
            "schema_revision": INDEX_SCHEMA_REVISION,
            "authority": INDEX_AUTHORITY,
            "status": "pass" if not differences else "mismatch",
            "generated_rows": [
                {"adapter_id": adapter_id, "status_label": generated[adapter_id]}
                for adapter_id in sorted(generated)
            ],
            "legacy_rows": [
                {"adapter_id": adapter_id, "status_label": legacy[adapter_id]}
                for adapter_id in sorted(legacy)
            ],
            "differences": differences,
        }
    )


__all__ = [
    "INDEX_AUTHORITY",
    "LEGACY_PARITY_SCHEMA",
    "RESULT_INDEX_SCHEMA",
    "STATUS_INDEX_SCHEMA",
    "canonical_index_bytes",
    "generate_result_index",
    "generate_status_index",
    "generate_submission_indexes",
    "legacy_status_parity",
]
