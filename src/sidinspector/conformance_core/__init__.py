"""Conformance-layer facade for canonical profile reports."""

from sidinspector.contracts import (
    CONFORMANCE_REPORT_SCHEMA,
    ReportContract,
    ReportContractValidationError,
    load_conformance_report,
    validate_conformance_report,
)

__all__ = [
    "CONFORMANCE_REPORT_SCHEMA",
    "ReportContract",
    "ReportContractValidationError",
    "load_conformance_report",
    "validate_conformance_report",
]
