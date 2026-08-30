#!/usr/bin/env python3
"""Build the deterministic legacy-to-canonical migration disposition matrix."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_sidscope_architecture_inventory import build_inventory


DEFAULT_OUTPUT = ROOT / "docs/reproducibility/sidscope_1_2_legacy_migration_matrix.json"

GENERATOR_VERIFIERS = {
    "dact_tiger": "tools/verify_dact_tiger_adapter.py",
    "latte_psid": "tools/verify_latte_psid_adapter.py",
    "rpg_kdd2025": "tools/verify_rpg_non_ar_bridge.py",
    "llada_rec": "tools/verify_llada_rec_adapter.py",
    "diffgrm_www2026": "tools/verify_diffgrm_adapter.py",
    "isd": "tools/verify_isd_adapter.py",
}


def build_matrix() -> dict[str, Any]:
    inventory = build_inventory()
    rows: list[dict[str, Any]] = []
    for route in inventory["routes"]["generator"]:
        route_id = route["route_id"]
        canonical = route_id == "rpg_kdd2025"
        rows.append(
            {
                "route_id": route_id,
                "route_kind": "generator",
                "legacy_authority": route["authority_path"],
                "legacy_verifier": GENERATOR_VERIFIERS[route_id],
                "legacy_status": route["status"],
                "shared_1_2_disposition": (
                    "canonical_end_to_end_fixture_parity"
                    if canonical
                    else "typed_canonical_pipeline_regeneration_required"
                ),
                "canonical_trace_required": True,
                "missing_canonical_surfaces": [] if canonical else ["canonical_1_2_pipeline"],
                "status_equivalence_policy": (
                    "canonical fixture and legacy verifier both pass; method semantics unchanged"
                    if canonical
                    else "legacy status remains authoritative; shared path must not infer a promotion"
                ),
            }
        )
    for route in inventory["routes"]["static_mapping"]:
        rows.append(
            {
                "route_id": route["route_id"],
                "route_kind": "static_mapping",
                "legacy_authority": route["authority_path"],
                "legacy_verifier": "tools/verify_adapter_conformance_assets.py",
                "legacy_status": route["status"],
                "shared_1_2_disposition": "typed_canonical_identity_regeneration_required",
                "canonical_trace_required": False,
                "missing_canonical_surfaces": ["canonical_identity_pipeline"],
                "status_equivalence_policy": "legacy C0-C5 status remains authoritative; runtime trace is not applicable",
            }
        )
    rows.sort(key=lambda row: (row["route_kind"], row["route_id"]))
    return {
        "schema": "sidscope.legacy_migration_matrix.v1",
        "status": "pass",
        "product_version": inventory["product_version"],
        "contract_registry_sha256": inventory["canonical_contract_registry"]["content_sha256"],
        "policy": {
            "historical_evidence_rewritten": False,
            "legacy_authority_retained": True,
            "typed_regeneration_is_not_conformance_failure": True,
            "promotion_from_incomplete_migration_allowed": False,
        },
        "route_count": len(rows),
        "routes": rows,
    }


def main() -> None:
    payload = json.dumps(build_matrix(), indent=2, sort_keys=True) + "\n"
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
