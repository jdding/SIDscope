#!/usr/bin/env python3
"""Deterministically build the canonical Sprint 2 fixtures from the RPG bridge."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import from_rpg_prepared_dataset, with_content_sha256


SOURCE = ROOT / "examples" / "rpg_non_ar_bridge_fixture" / "prepared_dataset.json"
OUTPUT = ROOT / "examples" / "prepared_dataset_fixture"


def build_documents() -> dict[str, dict[str, object]]:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    migration = from_rpg_prepared_dataset(source)
    documents = {
        "dataset_identity.json": migration.dataset_identity.to_dict(),
        "sid_space_identity.json": migration.sid_space_identity.to_dict(),
        "prepared_dataset.json": migration.prepared_dataset.to_dict(),
    }
    sid_negative = json.loads(json.dumps(documents["sid_space_identity.json"]))
    sid_negative["vocabulary"]["position_offsets"] = [1, 3]
    documents["expected_failure_overlapping_position_vocabulary.json"] = (
        with_content_sha256(sid_negative)
    )
    prepared_negative = json.loads(json.dumps(documents["prepared_dataset.json"]))
    prepared_negative["normalization"]["source_item_ids_exported"] = True
    documents["expected_failure_source_item_ids_exported.json"] = (
        with_content_sha256(prepared_negative)
    )
    return documents


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    documents = build_documents()
    for name, document in documents.items():
        (OUTPUT / name).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"status": "pass", "files": sorted(documents)}, indent=2))


if __name__ == "__main__":
    main()
