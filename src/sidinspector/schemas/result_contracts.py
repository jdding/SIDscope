"""Machine-readable and semantic contracts for public CLI JSON results."""

from __future__ import annotations

from typing import Any, Mapping


CLI_RESULT_SCHEMA_IDS = (
    "sidscope.adapter_plugin_listing.v1",
    "sidscope.adapter_plugin_preflight.v1",
    "sidscope.adapter_preflight.v1",
    "sidscope.composed_conformance_profile.v1",
    "sidscope.conformance_profile_catalog_listing.v1",
    "sidscope.conformance_profile_listing.v1",
    "sidscope.contract_registry_entry.v1",
    "sidscope.contract_registry_listing.v1",
    "sidscope.contract_validation.v1",
    "sidscope.evidence_bundle_validation.v1",
    "sidscope.evidence_registry_entry.v1",
    "sidscope.evidence_registry_listing.v1",
    "sidscope.evidence_registry_operation.v1",
    "sidscope.native_payload_validation.v1",
    "sidscope.profile_conformance_validation.v1",
    "sidscope.public_schema_catalog_listing.v1",
    "sidscope.public_schema_validation.v1",
    "sidscope.submission_index_export.v1",
    "sidscope.trace_payload_registry_listing.v1",
)


class CLIResultValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: str, detail: str) -> None:
    raise CLIResultValidationError(code, detail)


def validate_cli_result(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Fail closed on the stable envelope shared by every public CLI result."""

    if not isinstance(value, Mapping):
        _fail("invalid_type", "CLI result must be an object")
    schema = value.get("schema")
    if schema not in CLI_RESULT_SCHEMA_IDS:
        _fail("unknown_cli_result_schema", str(schema))
    status = value.get("status")
    if status not in {"pass", "fail"}:
        _fail("invalid_status", str(status))
    if "failure" not in value:
        _fail("missing_failure_field", "failure must be explicit")
    failure = value.get("failure")
    if status == "pass":
        if failure is not None:
            _fail("pass_with_failure", "passing result must set failure to null")
        return value
    if not isinstance(failure, Mapping) or set(failure) != {"code", "detail"}:
        _fail("invalid_failure", "failed result needs exactly code and detail")
    for field in ("code", "detail"):
        if not isinstance(failure.get(field), str) or not failure[field].strip():
            _fail("invalid_failure", f"failure.{field} must be a non-empty string")
    return value
