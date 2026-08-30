"""Stable ``sidscope`` command facade over versioned core contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

from sidinspector.contracts import (
    ContractRegistryError,
    DatasetIdentityValidationError,
    PreparedDatasetValidationError,
    ReportContractValidationError,
    RuntimeContractValidationError,
    SIDSpaceIdentityValidationError,
    SourceIdentityValidationError,
    load_contract_registry,
    load_episode_selection,
    load_registered_contract,
)
from sidinspector.conformance_core import load_conformance_report
from sidinspector.evaluation import diagnostic_report_document, validate_diagnostic_report
from sidinspector.evidence import build_evidence_index
from sidinspector.sdk import AdapterSDKError, load_adapter_capabilities
from sidinspector.trace import load_trace_envelope


VALIDATION_REPORT_SCHEMA = "sidscope.contract_validation.v1"
REGISTRY_LISTING_SCHEMA = "sidscope.contract_registry_listing.v1"
REGISTRY_ENTRY_SCHEMA = "sidscope.contract_registry_entry.v1"


def package_version() -> str:
    try:
        return metadata.version("sidinspector")
    except metadata.PackageNotFoundError:
        return "1.2.0.dev0+source"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sidscope")
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    commands = parser.add_subparsers(dest="command", required=True)

    adapter = commands.add_parser("adapter", help="inspect adapter SDK declarations")
    adapter_commands = adapter.add_subparsers(dest="adapter_command", required=True)
    preflight = adapter_commands.add_parser("preflight", help="validate capabilities")
    preflight.add_argument("--descriptor", required=True, type=Path)
    preflight.add_argument("--result-json", type=Path, default=None)

    contract = commands.add_parser("contract", help="inspect and validate canonical contracts")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    listing = contract_commands.add_parser("list", help="list registered contracts")
    listing.add_argument("--result-json", type=Path, default=None)
    show = contract_commands.add_parser("show", help="show one registered contract")
    show.add_argument("--type", required=True)
    show.add_argument("--result-json", type=Path, default=None)
    validate = contract_commands.add_parser("validate", help="validate one contract")
    validate.add_argument("--type", required=True)
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--result-json", type=Path, default=None)

    trace = commands.add_parser("trace", help="validate a canonical trace envelope")
    trace_commands = trace.add_subparsers(dest="trace_command", required=True)
    trace_validate = trace_commands.add_parser("validate")
    trace_validate.add_argument("--input", required=True, type=Path)
    trace_validate.add_argument("--result-json", type=Path, default=None)

    evaluate = commands.add_parser("evaluate", help="derive a canonical diagnostic report")
    evaluate.add_argument("--trace", required=True, type=Path)
    evaluate.add_argument("--selection", required=True, type=Path)
    evaluate.add_argument("--evaluation-cutoff", type=int, default=10)
    evaluate.add_argument("--publication-depth", type=int, default=100)
    evaluate.add_argument("--output", required=True, type=Path)

    verify = commands.add_parser("verify", help="validate a canonical conformance report")
    verify.add_argument("--report", required=True, type=Path)
    verify.add_argument("--result-json", type=Path, default=None)

    evidence = commands.add_parser("evidence", help="build canonical evidence indexes")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)
    package = evidence_commands.add_parser("package", help="package artifact dependencies")
    package.add_argument("--artifact", action="append", required=True, type=Path)
    package.add_argument("--index-id", required=True)
    package.add_argument("--output", required=True, type=Path)
    return parser


def _write_result(result: dict[str, object], result_json: Path | None) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if result_json is not None:
        result_json.parent.mkdir(parents=True, exist_ok=True)
        result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


def _failure_result(command: str, exc: Exception) -> dict[str, object]:
    return {
        "schema": VALIDATION_REPORT_SCHEMA,
        "status": "fail",
        "command": command,
        "failure": {
            "code": getattr(exc, "code", "input_error"),
            "detail": getattr(exc, "detail", f"{type(exc).__name__}: {exc}"),
        },
    }


def _write_artifact(document: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _adapter_preflight(args: argparse.Namespace) -> int:
    try:
        capabilities = load_adapter_capabilities(args.descriptor)
        result = {
            "schema": "sidscope.adapter_preflight.v1",
            "status": "pass",
            "adapter_id": capabilities.adapter_id,
            "sdk_version": "0.1.0",
            "method_family": capabilities.method_family,
            "contract_types": list(capabilities.contract_types),
            "failure": None,
        }
        code = 0
    except (AdapterSDKError, ContractRegistryError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("adapter preflight", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _trace_validate(args: argparse.Namespace) -> int:
    try:
        trace = load_trace_envelope(args.input)
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "pass",
            "contract_type": "trace-envelope",
            "trace_envelope_id": trace.artifact_id,
            "content_sha256": trace.content_sha256,
            "input_file_sha256": _file_sha256(args.input),
            "failure": None,
        }
        code = 0
    except (RuntimeContractValidationError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("trace validate", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _evaluate(args: argparse.Namespace) -> int:
    try:
        trace = load_trace_envelope(args.trace)
        selection = load_episode_selection(args.selection)
        if trace.to_dict()["episode_selection_binding"]["content_sha256"] != selection.content_sha256:
            raise RuntimeContractValidationError(
                "trace_selection_binding_mismatch", selection.content_sha256
            )
        selected = [row["episode_id"] for row in selection.to_dict()["rows"]]
        observed = [row["episode_id"] for row in trace.to_dict()["observations"]]
        if selected != observed:
            raise RuntimeContractValidationError("trace_selection_episode_mismatch", str(observed))
        document = diagnostic_report_document(
            trace,
            selection,
            evaluation_cutoff=args.evaluation_cutoff,
            publication_depth=args.publication_depth,
        )
        validate_diagnostic_report(document)
        _write_artifact(document, args.output)
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0
    except (
        RuntimeContractValidationError,
        ReportContractValidationError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        _write_result(_failure_result("evaluate", exc), None)
        return 2


def _verify(args: argparse.Namespace) -> int:
    try:
        report = load_conformance_report(args.report)
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "pass",
            "contract_type": "conformance-report",
            "conformance_report_id": report.artifact_id,
            "content_sha256": report.content_sha256,
            "input_file_sha256": _file_sha256(args.report),
            "failure": None,
        }
        code = 0
    except (ReportContractValidationError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("verify", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _evidence_package(args: argparse.Namespace) -> int:
    try:
        document = build_evidence_index(args.artifact, index_id=args.index_id)
        _write_artifact(document, args.output)
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0
    except (
        ContractRegistryError,
        DatasetIdentityValidationError,
        PreparedDatasetValidationError,
        ReportContractValidationError,
        RuntimeContractValidationError,
        SIDSpaceIdentityValidationError,
        SourceIdentityValidationError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        _write_result(_failure_result("evidence package", exc), None)
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "adapter":
        return _adapter_preflight(args)
    if args.command == "trace":
        return _trace_validate(args)
    if args.command == "evaluate":
        return _evaluate(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "evidence":
        return _evidence_package(args)
    if args.command != "contract":
        raise AssertionError("unreachable argparse command")

    try:
        registry = load_contract_registry()
        if args.contract_command == "list":
            result = {
                "schema": REGISTRY_LISTING_SCHEMA,
                "status": "pass",
                "registry_id": registry.registry_id,
                "registry_schema": registry.schema,
                "registry_content_sha256": registry.content_sha256,
                "contract_count": len(registry.contracts),
                "contracts": [
                    {
                        "contract_type": item.contract_type,
                        "schema_id": item.schema_id,
                        "schema_revision": item.schema_revision,
                        "owner": item.owner,
                    }
                    for item in registry.contracts
                ],
                "failure": None,
            }
            _write_result(result, args.result_json)
            return 0
        if args.contract_command == "show":
            descriptor = registry.by_type(args.type)
            result = {
                "schema": REGISTRY_ENTRY_SCHEMA,
                "status": "pass",
                "registry_id": registry.registry_id,
                "contract": descriptor.to_dict(),
                "failure": None,
            }
            _write_result(result, args.result_json)
            return 0
        if args.contract_command != "validate":
            raise AssertionError("unreachable argparse command")
    except ContractRegistryError as exc:
        result = {
            "schema": REGISTRY_ENTRY_SCHEMA,
            "status": "fail",
            "contract_type": getattr(args, "type", None),
            "failure": {"code": exc.code, "detail": exc.detail},
        }
        _write_result(result, getattr(args, "result_json", None))
        return 2

    try:
        descriptor, artifact = load_registered_contract(args.type, args.input)
        artifact_dict = artifact.to_dict()
        result: dict[str, object] = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "pass",
            "contract_type": args.type,
            "contract_schema": artifact.schema,
            "schema_revision": artifact.schema_revision,
            descriptor.result_id_field: artifact_dict[descriptor.result_id_field],
            "content_sha256": artifact.content_sha256,
            "input_file_sha256": _file_sha256(args.input),
            "failure": None,
        }
        exit_code = 0
    except (
        ContractRegistryError,
        DatasetIdentityValidationError,
        PreparedDatasetValidationError,
        ReportContractValidationError,
        RuntimeContractValidationError,
        SIDSpaceIdentityValidationError,
        SourceIdentityValidationError,
    ) as exc:
        code = getattr(exc, "code", "contract_validation_error")
        detail = getattr(exc, "detail", str(exc))
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "fail",
            "contract_type": args.type,
            "failure": {"code": code, "detail": detail},
        }
        exit_code = 2
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "fail",
            "contract_type": args.type,
            "failure": {"code": "input_error", "detail": f"{type(exc).__name__}: {exc}"},
        }
        exit_code = 2

    _write_result(result, args.result_json)
    return exit_code
