"""Stable ``sidscope`` command facade over versioned core contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib import metadata
from pathlib import Path
from typing import Sequence

from sidinspector.contracts import SourceIdentityValidationError, load_source_identity


VALIDATION_REPORT_SCHEMA = "sidscope.contract_validation.v1"


def package_version() -> str:
    try:
        return metadata.version("sidinspector")
    except metadata.PackageNotFoundError:
        return "1.1.1.dev0+source"


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
    contract = commands.add_parser("contract", help="validate canonical contract artifacts")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    validate = contract_commands.add_parser("validate", help="validate one contract")
    validate.add_argument("--type", required=True, choices=["source-identity"])
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
    if args.command != "contract" or args.contract_command != "validate":
        raise AssertionError("unreachable argparse command")

    try:
        identity = load_source_identity(args.input)
        result: dict[str, object] = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "pass",
            "contract_type": args.type,
            "contract_schema": identity.schema,
            "schema_revision": identity.schema_revision,
            "source_id": identity.source_id,
            "content_sha256": identity.content_sha256,
            "input_file_sha256": _file_sha256(args.input),
            "failure": None,
        }
        exit_code = 0
    except SourceIdentityValidationError as exc:
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "fail",
            "contract_type": args.type,
            "failure": {"code": exc.code, "detail": exc.detail},
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
