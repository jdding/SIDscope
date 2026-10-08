#!/usr/bin/env python3
"""Verify SIDScope 1.7 contract and public-surface stabilization."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import sidscope
import importlib
from sidinspector.sdk import ADAPTER_SDK_VERSION, PLUGIN_API_VERSION
from build_sidscope_1_7_stabilization_fixture import (
    DEFAULT_OUTPUT,
    PRODUCT_VERSION,
    build_stabilization_record,
)
from sidinspector.schemas.result_contracts import (
    CLI_RESULT_SCHEMA_IDS,
    CLIResultValidationError,
    validate_cli_result,
)
from sidinspector.contracts import canonical_json_bytes, verify_content_sha256, with_content_sha256
from sidinspector.schemas.catalog import (
    PublicSchemaValidationError,
    load_public_schema_catalog,
    validate_public_document,
)
from verify_sidscope_release_metadata import verify_release_metadata


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain an object")
    return value


def verify() -> dict[str, Any]:
    record = _read_json(DEFAULT_OUTPUT)
    expected = with_content_sha256(build_stabilization_record())
    if not verify_content_sha256(record):
        raise AssertionError("1.7 stabilization record content hash mismatch")
    if canonical_json_bytes(record) != canonical_json_bytes(expected):
        raise AssertionError("1.7 stabilization record is stale")

    metadata = verify_release_metadata()
    # Metadata verifies the current runtime version; the 1.7 surface record is
    # an immutable compatibility baseline, not the current package version.

    catalog = load_public_schema_catalog()
    canonical = _read_json(
        ROOT / "examples/dataset_identity_fixture/dataset_identity.json"
    )
    validate_public_document(canonical)

    masked = _read_json(
        ROOT / "examples/native_trace_payload_fixtures/masked_diffusion.json"
    )
    invalid = copy.deepcopy(masked)
    del invalid["episodes"][0]["steps"][0]["selected_positions"]
    try:
        validate_public_document(with_content_sha256(invalid))
    except PublicSchemaValidationError as error:
        if error.code != "invalid_fields":
            raise AssertionError(error.code) from error
    else:
        raise AssertionError("semantic-invalid masked payload passed")

    for schema_id in CLI_RESULT_SCHEMA_IDS:
        validate_cli_result({"schema": schema_id, "status": "pass", "failure": None})
    try:
        validate_cli_result(
            {
                "schema": CLI_RESULT_SCHEMA_IDS[0],
                "status": "pass",
                "failure": {"code": "unexpected", "detail": "must reject"},
            }
        )
    except CLIResultValidationError as error:
        if error.code != "pass_with_failure":
            raise AssertionError(error.code) from error
    else:
        raise AssertionError("pass-with-failure CLI result passed")

    if tuple(record["python_facade"]["symbols"]) != tuple(sidscope.__all__):
        raise AssertionError("curated sidscope facade changed")
    if record["adapter_sdk"] != {
        "version": ADAPTER_SDK_VERSION,
        "plugin_api_version": PLUGIN_API_VERSION,
        "supported_capability_api_levels": ["0.2.0", "1.0.0"],
        "current_descriptor_interval": ">=1.0.0,<2.0.0",
    }:
        raise AssertionError("stable Adapter SDK candidate surface changed")
    for module_name, names in record["opt_in_workflows"].items():
        module = importlib.import_module(module_name)
        for name in names:
            if not callable(getattr(module, name, None)):
                raise AssertionError(f"missing opt-in workflow: {module_name}.{name}")
    return {
        "schema": "sidscope.1_7_stabilization_verification.v1",
        "status": "pass",
        "product_version": PRODUCT_VERSION,
        "gpu_required": False,
        "schema_count": len(catalog),
        "schema_resource_count": len(set(item.schema_resource for item in catalog)),
        "cli_result_schema_count": len(CLI_RESULT_SCHEMA_IDS),
        "python_facade_symbol_count": len(sidscope.__all__),
        "typed_negative_count": 2,
        "validation_layers": ["json_schema_draft_2020_12", "python_semantic"],
    }


def main() -> None:
    print(json.dumps(verify(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
