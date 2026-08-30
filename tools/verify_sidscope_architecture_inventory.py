#!/usr/bin/env python3
"""Fail closed when the checked-in SIDScope architecture inventory drifts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.build_sidscope_architecture_inventory import DEFAULT_OUTPUT, ROOT, build_inventory


REPORT_SCHEMA = "sidscope.architecture_inventory_verification.v1"


def verify_inventory(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = build_inventory()
    if observed != expected:
        observed_ids = {row["schema_id"] for row in observed.get("schemas", [])}
        expected_ids = {row["schema_id"] for row in expected["schemas"]}
        raise ValueError(
            "architecture inventory drift: "
            f"missing={sorted(expected_ids - observed_ids)}, "
            f"stale={sorted(observed_ids - expected_ids)}; rebuild the inventory"
        )

    for record in observed["schemas"]:
        if not record["owner"] or not record["declaration_paths"]:
            raise ValueError(f"unowned or undeclared schema: {record['schema_id']}")
        for rel_path in record["declaration_paths"]:
            if not (ROOT / rel_path).is_file():
                raise FileNotFoundError(rel_path)
    for profile in observed["profiles"]:
        for key in ("authority", "verifier"):
            if not (ROOT / profile[key]).exists():
                raise FileNotFoundError(profile[key])

    routes = observed["routes"]
    registry = observed["canonical_contract_registry"]
    if registry["contract_count"] != len(registry["contracts"]):
        raise ValueError("canonical contract registry count mismatch")
    if registry["contract_count"] < 4:
        raise ValueError("canonical contract registry missing Sprint 2 contracts")
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass",
        "inventory_schema": observed["schema"],
        "schema_count": observed["schema_count"],
        "profile_count": len(observed["profiles"]),
        "generator_route_count": len(routes["generator"]),
        "static_mapping_route_count": len(routes["static_mapping"]),
        "canonical_evidence_edge_count": len(observed["canonical_evidence_edges"]),
        "canonical_contract_count": registry["contract_count"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_inventory(args.inventory)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
