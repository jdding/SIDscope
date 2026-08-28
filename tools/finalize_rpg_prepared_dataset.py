#!/usr/bin/env python3
"""Bind a prepared RPG dataset contract to completed training outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rpg_non_ar_bridge import (  # noqa: E402
    canonical_hash,
    sha256_file,
    validate_prepared_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dataset", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--training-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    prepared = json.loads(args.prepared_dataset.read_text(encoding="utf-8"))
    validate_prepared_dataset(prepared)
    completed = json.loads(json.dumps(prepared))
    completed["training"] = {
        "status": "complete",
        "model_seed": prepared["configuration"]["model_seed"],
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "training_manifest_sha256": sha256_file(args.training_manifest),
    }
    validate_prepared_dataset(completed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(completed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "schema": "sidscope.rpg_prepared_dataset_finalization.v1",
                "status": "pass",
                "output": str(args.output),
                "prepared_dataset_contract_sha256": canonical_hash(completed),
                "checkpoint_sha256": completed["training"]["checkpoint_sha256"],
                "training_manifest_sha256": completed["training"]["training_manifest_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
