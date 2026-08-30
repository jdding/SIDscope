#!/usr/bin/env python3
"""Verify complete route coverage and fail-closed 1.2 migration dispositions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_sidscope_1_2_legacy_migration_matrix import DEFAULT_OUTPUT, ROOT, build_matrix


def main() -> None:
    observed = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    expected = build_matrix()
    if observed != expected:
        raise ValueError("legacy migration matrix drift; rebuild it")
    if observed["route_count"] != len(observed["routes"]):
        raise ValueError("route count mismatch")
    if len({row["route_id"] for row in observed["routes"]}) != observed["route_count"]:
        raise ValueError("duplicate route identity")
    for row in observed["routes"]:
        for field in ("legacy_authority", "legacy_verifier"):
            if not (ROOT / row[field]).is_file():
                raise FileNotFoundError(row[field])
        if row["shared_1_2_disposition"].startswith("typed_") and not row["missing_canonical_surfaces"]:
            raise ValueError(f"{row['route_id']} has an untyped migration gap")
    canonical = [
        row["route_id"]
        for row in observed["routes"]
        if row["shared_1_2_disposition"] == "canonical_end_to_end_fixture_parity"
    ]
    if canonical != ["rpg_kdd2025"]:
        raise ValueError(f"unexpected canonical parity claims: {canonical}")
    print(
        json.dumps(
            {
                "schema": "sidscope.legacy_migration_matrix_verification.v1",
                "status": "pass",
                "route_count": observed["route_count"],
                "generator_route_count": sum(row["route_kind"] == "generator" for row in observed["routes"]),
                "static_mapping_route_count": sum(row["route_kind"] == "static_mapping" for row in observed["routes"]),
                "canonical_end_to_end_routes": canonical,
                "typed_regeneration_routes": observed["route_count"] - len(canonical),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
