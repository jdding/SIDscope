"""Stable ``sidscope`` command facade over versioned core contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib import metadata
from pathlib import Path
from typing import Sequence

from sidinspector.contracts import (
    ContractRegistryError,
    DatasetIdentityValidationError,
    SourceIdentityValidationError,
    load_contract_registry,
    load_registered_contract,
)


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
    return parser


def _write_result(result: dict[str, object], result_json: Path | None) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if result_json is not None:
        result_json.parent.mkdir(parents=True, exist_ok=True)
        result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
