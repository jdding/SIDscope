#!/usr/bin/env python3
"""Verify public C0-C5 route reports and rerun the negative fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.conformance import run_conformance  # noqa: E402
from tools.verify_sidscope_source_inventory import (  # noqa: E402
    DEFAULT_COVERAGE,
    DEFAULT_INVENTORY,
    verify_inventory,
)


def main() -> None:
    failures: list[str] = []
    route_ids = [
        "resid_gaoq_video",
        "grid_p5_beauty",
        "card_p5_beauty",
        "diger_beauty",
        "resot_instruments",
        "letter_instruments",
        "lcrec_instruments",
    ]
    route_levels: dict[str, list[str]] = {}
    for route_id in route_ids:
        report = json.loads(
            (ROOT / f"docs/reproducibility/conformance/{route_id}_report.json").read_text(encoding="utf-8")
        )
        levels = [check["level"] for check in report.get("checks", [])]
        route_levels[route_id] = levels
        if report.get("status") != "pass" or report.get("failed_levels") != []:
            failures.append(f"frozen {route_id} report does not pass")
        if levels != ["C0", "C1", "C2", "C3", "C4", "C5"]:
            failures.append(f"frozen {route_id} report does not contain C0-C5 in order")
        c3 = next((check for check in report.get("checks", []) if check.get("level") == "C3"), {})
        smoke = c3.get("details", {}).get("metric_smoke_summary", [])
        if not smoke or int(smoke[0].get("d1_level_count", 0)) <= 0:
            failures.append(f"frozen {route_id} C3 report lacks executed D1 evidence")
        c4 = next((check for check in report.get("checks", []) if check.get("level") == "C4"), {})
        if set(c4.get("details", {}).get("input_sha256", {})) != {
            "sid_assignments",
            "item_metadata",
            "interactions",
        }:
            failures.append(f"frozen {route_id} C4 report lacks three input hashes")
        c1 = next((check for check in report.get("checks", []) if check.get("level") == "C1"), {})
        for table_name, table in c1.get("details", {}).get("tables", {}).items():
            if table.get("availability") != "summary_only_raw_not_redistributed":
                failures.append(f"frozen {route_id} C1 {table_name} lacks raw-free availability marker")
            if "path" in table:
                failures.append(f"frozen {route_id} C1 {table_name} exposes a private input path")

    fixture_manifest = ROOT / "examples/conformance_failure_fixture/manifest.json"
    observed_fixture = run_conformance(fixture_manifest, root=ROOT)
    frozen_fixture = json.loads(
        (ROOT / "examples/conformance_failure_fixture/conformance_report.json").read_text(encoding="utf-8")
    )
    if observed_fixture != frozen_fixture:
        failures.append("negative fixture report differs from a fresh run")
    if observed_fixture.get("failed_levels") != ["C1"]:
        failures.append("negative fixture must fail exactly C1")

    inventory = verify_inventory(DEFAULT_INVENTORY, DEFAULT_COVERAGE)
    if inventory["status"] != "pass":
        failures.extend(inventory["failures"])
    if failures:
        raise SystemExit("; ".join(failures))
    print(
        json.dumps(
            {
                "status": "pass",
                "conformant_routes": route_ids,
                "route_levels": route_levels,
                "fixture_failed_levels": ["C1"],
            }
        )
    )


if __name__ == "__main__":
    main()
