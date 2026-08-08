#!/usr/bin/env python3
"""Verify deterministic ReSOT walkthrough outputs from public compact inputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_resot_resource_walkthrough import build_walkthrough, render_markdown  # noqa: E402


def main() -> None:
    payload = build_walkthrough(ROOT)
    expected_json = json.loads((ROOT / "docs/reproducibility/resot_resource_walkthrough.json").read_text())
    expected_md = (ROOT / "docs/RESOT_RESOURCE_WALKTHROUGH.md").read_text(encoding="utf-8")
    failures: list[str] = []
    if payload != expected_json:
        failures.append("JSON walkthrough differs from deterministic rebuild")
    if render_markdown(payload) != expected_md:
        failures.append("Markdown walkthrough differs from deterministic rebuild")
    if failures:
        raise SystemExit("; ".join(failures))
    print(json.dumps({"status": "pass", "route_id": payload["route_id"], "stages": len(payload["stages"])}))


if __name__ == "__main__":
    main()
