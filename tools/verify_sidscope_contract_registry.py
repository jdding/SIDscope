#!/usr/bin/env python3
"""Verify the canonical contract registry and every declared fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import (
    load_contract_registry,
    load_dataset_identity,
    load_prepared_dataset,
    load_registered_contract,
    load_sid_space_identity,
    validate_prepared_dataset_bindings,
)


REPORT_SCHEMA = "sidscope.contract_registry_verification.v1"


def verify_contract_registry() -> dict[str, object]:
    registry = load_contract_registry(repository_root=ROOT)
    positive_count = 0
    negative_count = 0
    for descriptor in registry.contracts:
        load_registered_contract(descriptor.contract_type, ROOT / descriptor.canonical_fixture)
        positive_count += 1
        for fixture in descriptor.negative_fixtures:
            try:
                load_registered_contract(descriptor.contract_type, ROOT / fixture.path)
            except ValueError as exc:
                observed = getattr(exc, "code", None)
                if observed != fixture.expected_failure:
                    raise ValueError(
                        f"{fixture.path}: expected {fixture.expected_failure}, observed {observed}"
                    ) from exc
            else:
                raise ValueError(f"negative fixture unexpectedly passed: {fixture.path}")
            negative_count += 1
    fixture = ROOT / "examples" / "prepared_dataset_fixture"
    validate_prepared_dataset_bindings(
        load_prepared_dataset(fixture / "prepared_dataset.json"),
        load_dataset_identity(fixture / "dataset_identity.json"),
        load_sid_space_identity(fixture / "sid_space_identity.json"),
    )
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass",
        "registry_id": registry.registry_id,
        "registry_content_sha256": registry.content_sha256,
        "contract_count": len(registry.contracts),
        "positive_fixture_count": positive_count,
        "negative_fixture_count": negative_count,
        "dependency_binding_count": 2,
        "schema_ids": [item.schema_id for item in registry.contracts],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path, default=None)
    args = parser.parse_args()
    result = verify_contract_registry()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
