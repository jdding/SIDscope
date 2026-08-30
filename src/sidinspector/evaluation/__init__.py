"""Evaluation-layer facade for deterministic diagnostic derivation."""

from sidinspector.contracts import (
    ReportContract,
    ReportContractValidationError,
    diagnostic_report_document,
    validate_diagnostic_report,
    validate_report_bindings,
)

__all__ = [
    "ReportContract",
    "ReportContractValidationError",
    "diagnostic_report_document",
    "validate_diagnostic_report",
    "validate_report_bindings",
]
