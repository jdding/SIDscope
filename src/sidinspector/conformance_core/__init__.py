"""Conformance-layer facade for canonical profile reports."""

from sidinspector.contracts import (
    CONFORMANCE_REPORT_SCHEMA,
    ReportContract,
    ReportContractValidationError,
    load_conformance_report,
    validate_conformance_report,
)
from .profiles import (
    ComposedProfile,
    ConformanceProfile,
    GateDefinition,
    ProfileCompositionError,
    compose_profiles,
    composed_profile_document,
    load_profile_registry,
)

__all__ = [
    "CONFORMANCE_REPORT_SCHEMA",
    "ReportContract",
    "ReportContractValidationError",
    "load_conformance_report",
    "validate_conformance_report",
    "ComposedProfile",
    "ConformanceProfile",
    "GateDefinition",
    "ProfileCompositionError",
    "compose_profiles",
    "composed_profile_document",
    "load_profile_registry",
]
