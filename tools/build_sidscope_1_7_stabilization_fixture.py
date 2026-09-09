#!/usr/bin/env python3
"""Build the deterministic SIDScope 1.7 public-surface stabilization record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import sidscope
from sidinspector.cli import build_parser
from sidinspector.schemas.result_contracts import CLI_RESULT_SCHEMA_IDS
from sidinspector.contracts import (
    CONTRACT_PRODUCER_VERSION,
    EVALUATION_PRODUCER_VERSION,
    EVIDENCE_PRODUCER_VERSION,
    canonical_json_bytes,
    with_content_sha256,
)
from sidinspector.schemas.catalog import load_public_schema_catalog
from sidinspector.sdk import ADAPTER_SDK_VERSION, PLUGIN_API_VERSION


PRODUCT_VERSION = "1.7.0.dev0"
DEFAULT_OUTPUT = ROOT / "docs/reproducibility/sidscope_1_7_public_surface.json"


def _cli_leaf_paths() -> list[str]:
    paths: list[str] = []

    def visit(parser: argparse.ArgumentParser, prefix: tuple[str, ...]) -> None:
        subparsers = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if not subparsers:
            paths.append(" ".join(prefix))
            return
        if len(subparsers) != 1:
            raise ValueError(f"ambiguous CLI parser at {' '.join(prefix)}")
        for name, child in sorted(subparsers[0].choices.items()):
            visit(child, (*prefix, name))

    visit(build_parser(), ())
    return paths


def build_stabilization_record() -> dict[str, Any]:
    catalog = load_public_schema_catalog()
    return {
        "schema": "sidscope.public_surface_stabilization.v1",
        "schema_revision": "1.0.0",
        "product_version": PRODUCT_VERSION,
        "scope": "contract_and_public_surface_stabilization",
        "public_schema_catalog": {
            "schema_count": len(catalog),
            "resources": sorted(set(item.schema_resource for item in catalog)),
            "entries": [item.to_dict() for item in catalog],
            "validation_order": [
                "json_schema_draft_2020_12",
                "python_semantic",
            ],
        },
        "cli": {
            "leaf_commands": _cli_leaf_paths(),
            "result_schema_ids": list(CLI_RESULT_SCHEMA_IDS),
            "result_envelope_resource": "cli_result.v1.schema.json",
        },
        "python_facade": {
            "module": "sidscope",
            "symbols": list(sidscope.__all__),
            "historical_namespace": "sidinspector",
        },
        "adapter_sdk": {
            "version": ADAPTER_SDK_VERSION,
            "plugin_api_version": PLUGIN_API_VERSION,
            "supported_capability_api_levels": ["0.2.0", "1.0.0"],
            "current_descriptor_interval": ">=1.0.0,<2.0.0",
        },
        "opt_in_workflows": {
            "sidscope.workflows": ["audit", "compare", "evaluate"],
            "sidscope.mapping_check": ["preflight"],
            "sidscope.pipeline": ["run"],
            "sidscope.regression": ["compare_runs"],
            "sidscope.diagnostic_review": ["write_review"],
            "sidscope.refresh": ["bind_evaluation", "compare_snapshots", "write_report"],
        },
        "candidate_exclusions": ["hosted_service", "method_training", "N09_notebook_api", "N10_static_review_bundle"],
        "producer_versions": {
            "contract": CONTRACT_PRODUCER_VERSION,
            "evaluation": EVALUATION_PRODUCER_VERSION,
            "evidence": EVIDENCE_PRODUCER_VERSION,
            "policy": "semantic producer versions do not follow packaging-only releases",
        },
        "compatibility_delta": {
            "additive_cli_commands": ["schema list", "schema validate"],
            "additive_python_module": "sidscope",
            "removed_cli_commands": [],
            "removed_historical_symbols": [],
            "artifact_bytes_rewritten": False,
            "adapter_sdk_stabilized": "1.0.0",
            "additive_opt_in_modules": ["sidscope.diagnostic_review", "sidscope.mapping_check", "sidscope.pipeline", "sidscope.refresh", "sidscope.regression", "sidscope.workflows"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = canonical_json_bytes(with_content_sha256(build_stabilization_record())) + b"\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps({"status": "pass", "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
