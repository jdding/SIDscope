"""Public SIDScope submission checking and generated-index surface."""

from .checker import ValidatedSubmission, check_submission, validate_submission_package
from .contracts import (
    EVIDENCE_SUBMISSION_SCHEMA,
    SUBMISSION_CHECK_REPORT_SCHEMA,
    EvidenceSubmission,
    SubmissionCheckReport,
    SubmissionValidationError,
    build_evidence_submission,
    build_submission_check_report,
    load_evidence_submission,
    validate_evidence_submission,
    validate_submission_check_report,
)
from .indexes import (
    INDEX_AUTHORITY,
    RESULT_INDEX_SCHEMA,
    STATUS_INDEX_SCHEMA,
    canonical_index_bytes,
    generate_result_index,
    generate_status_index,
    generate_submission_indexes,
    legacy_status_parity,
)

__all__ = [
    "EVIDENCE_SUBMISSION_SCHEMA",
    "INDEX_AUTHORITY",
    "RESULT_INDEX_SCHEMA",
    "STATUS_INDEX_SCHEMA",
    "SUBMISSION_CHECK_REPORT_SCHEMA",
    "EvidenceSubmission",
    "SubmissionCheckReport",
    "SubmissionValidationError",
    "ValidatedSubmission",
    "build_evidence_submission",
    "build_submission_check_report",
    "canonical_index_bytes",
    "check_submission",
    "generate_result_index",
    "generate_status_index",
    "generate_submission_indexes",
    "legacy_status_parity",
    "load_evidence_submission",
    "validate_evidence_submission",
    "validate_submission_check_report",
    "validate_submission_package",
]
