"""Reusable positive and typed-negative fixture harness for adapter authors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sidinspector.contracts import validate_trace_envelope
from sidinspector.sdk.alpha import validate_adapter_capabilities
from sidinspector.trace import load_native_payload, validate_payload_binding


class FixtureHarnessError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class FixtureResult:
    case_id: str
    expected_status: str
    observed_status: str
    failure_code: str | None


def _json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise FixtureHarnessError("invalid_fixture", str(path))
    return value


def run_fixture_manifest(path: Path) -> tuple[FixtureResult, ...]:
    manifest = _json(path)
    if manifest.get("schema") != "sidscope.adapter_fixture_manifest.v1":
        raise FixtureHarnessError("fixture_manifest_schema_mismatch", str(path))
    root = path.parent
    results: list[FixtureResult] = []
    for case in manifest.get("cases", []):
        case_id = str(case["case_id"])
        expected_status = str(case["expected_status"])
        expected_failure = case.get("expected_failure")
        observed_status = "pass"
        failure_code = None
        try:
            kind = case["validator"]
            fixture_path = root / case["path"]
            if kind == "native_payload":
                load_native_payload(fixture_path)
            elif kind == "trace_envelope":
                validate_trace_envelope(_json(fixture_path))
            elif kind == "adapter_capabilities":
                validate_adapter_capabilities(_json(fixture_path))
            elif kind == "payload_binding":
                payload = load_native_payload(fixture_path)
                validate_payload_binding(
                    payload,
                    schema_id=str(case["binding"]["schema_id"]),
                    content_sha256=str(case["binding"]["content_sha256"]),
                )
            else:
                raise FixtureHarnessError("unknown_fixture_validator", str(kind))
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            observed_status = "fail"
            failure_code = getattr(exc, "code", "fixture_execution_error")
        if observed_status != expected_status or failure_code != expected_failure:
            raise FixtureHarnessError(
                "fixture_outcome_mismatch",
                f"{case_id}: expected={expected_status}/{expected_failure}, observed={observed_status}/{failure_code}",
            )
        results.append(FixtureResult(case_id, expected_status, observed_status, failure_code))
    if not results:
        raise FixtureHarnessError("empty_fixture_manifest", str(path))
    return tuple(results)
