"""Observation-layer facade for canonical trace envelopes."""

from sidinspector.contracts import (
    TRACE_ENVELOPE_SCHEMA,
    RuntimeContract,
    RuntimeContractValidationError,
    load_trace_envelope,
    validate_trace_envelope,
)
from .native_payloads import (
    FAMILY_SCHEMAS,
    NativePayload,
    NativePayloadDescriptor,
    NativePayloadValidationError,
    load_native_payload,
    load_native_payload_registry,
    validate_native_payload,
    validate_payload_binding,
)

__all__ = [
    "TRACE_ENVELOPE_SCHEMA",
    "RuntimeContract",
    "RuntimeContractValidationError",
    "load_trace_envelope",
    "validate_trace_envelope",
    "FAMILY_SCHEMAS",
    "NativePayload",
    "NativePayloadDescriptor",
    "NativePayloadValidationError",
    "load_native_payload",
    "load_native_payload_registry",
    "validate_native_payload",
    "validate_payload_binding",
]
