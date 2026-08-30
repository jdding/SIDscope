#!/usr/bin/env python3
"""Verify Sprint 2 identities, bindings, migration parity, and typed rejection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import (
    PreparedDatasetValidationError,
    from_rpg_prepared_dataset,
    load_dataset_identity,
    load_prepared_dataset,
    load_sid_space_identity,
    require_regeneration_for_legacy_prepared,
    validate_prepared_dataset_bindings,
)


FIXTURE = ROOT / "examples" / "prepared_dataset_fixture"


def verify_sprint2_contracts() -> dict[str, object]:
    dataset = load_dataset_identity(FIXTURE / "dataset_identity.json")
    sid_space = load_sid_space_identity(FIXTURE / "sid_space_identity.json")
    prepared = load_prepared_dataset(FIXTURE / "prepared_dataset.json")
    validate_prepared_dataset_bindings(prepared, dataset, sid_space)

    legacy = json.loads(
        (ROOT / "examples/rpg_non_ar_bridge_fixture/prepared_dataset.json").read_text(
            encoding="utf-8"
        )
    )
    migrated = from_rpg_prepared_dataset(legacy)
    expected = (dataset.to_dict(), sid_space.to_dict(), prepared.to_dict())
    observed = (
        migrated.dataset_identity.to_dict(),
        migrated.sid_space_identity.to_dict(),
        migrated.prepared_dataset.to_dict(),
    )
    if observed != expected:
        raise ValueError("RPG prepared-data migration drift")

    regeneration_required: list[str] = []
    for rel_path in (
        "examples/diffgrm_masked_diffusion_fixture/prepared_dataset.json",
        "examples/llada_rec_trained_trace_fixture/prepared_dataset.json",
    ):
        value = json.loads((ROOT / rel_path).read_text(encoding="utf-8"))
        try:
            require_regeneration_for_legacy_prepared(value)
        except PreparedDatasetValidationError as exc:
            if exc.code != "legacy_prepared_regeneration_required":
                raise
            regeneration_required.append(str(value["schema"]))
        else:
            raise ValueError(f"legacy prepared artifact unexpectedly accepted: {rel_path}")

    return {
        "schema": "sidscope.sprint2_contract_verification.v1",
        "status": "pass",
        "dataset_identity_sha256": dataset.content_sha256,
        "sid_space_identity_sha256": sid_space.content_sha256,
        "prepared_dataset_sha256": prepared.content_sha256,
        "rpg_migration_parity": True,
        "legacy_regeneration_required": regeneration_required,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path, default=None)
    args = parser.parse_args()
    result = verify_sprint2_contracts()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
