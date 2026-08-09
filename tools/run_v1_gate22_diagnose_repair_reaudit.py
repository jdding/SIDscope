#!/usr/bin/env python3
"""Run the CPU mapping half of G22 on released DACT 0.6/0.7 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

for import_root in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from sidinspector.adapters.dact import normalize_dact_codes  # noqa: E402
from sidinspector.churn import compute_churn  # noqa: E402
from sidinspector.metrics import validate_inputs  # noqa: E402
from sidinspector.preflight import build_metric_smoke_summary  # noqa: E402
from tools.run_v1_gate20_d7_trained_beam import json_safe, sha256  # noqa: E402


CONTRACT_ID = "G22_DACT_DIAGNOSE_REPAIR_REAUDIT"
DEFAULT_DACT_ROOT = PROJECT_ROOT / "experiments/v1_evidence_chain/upstreams/DACT"
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments/v1_evidence_chain/gate22_diagnose_repair_reaudit/mapping_audit"


def reconstruct_interactions(paths: dict[str, Path], dataset: str = "Tools") -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for split, path in paths.items():
        frame = pd.read_parquet(path)
        required = {"user", "history", "target"}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{path} missing released columns: {missing}")
        for row in frame.itertuples(index=False):
            user = str(row.user)
            sequence = [int(item) for item in list(row.history)] + [int(row.target)]
            for order, item in enumerate(sequence):
                rows.append(
                    {
                        "dataset": dataset,
                        "user_id": user,
                        "item_id": item,
                        "timestamp": order,
                        "split": split,
                    }
                )
    interactions = pd.DataFrame(rows)
    return interactions.drop_duplicates(["dataset", "user_id", "item_id", "split"]).reset_index(drop=True)


def compact_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"expected one metric profile row, got {len(rows)}")
    return rows[0]


def coverage_row(
    sid: pd.DataFrame, metadata: pd.DataFrame, interactions: pd.DataFrame, *, allow_partial: bool
) -> dict[str, Any]:
    frame = validate_inputs(sid, metadata, interactions, allow_partial_coverage=allow_partial)
    if len(frame) != 1:
        raise ValueError(f"expected one coverage row, got {len(frame)}")
    return json_safe(frame.iloc[0].to_dict())


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.dact_root.resolve()
    old_codes = args.old_codes.resolve()
    new_codes = args.new_codes.resolve()
    split_paths = {
        "train": args.train.resolve(),
        "validation": args.validation.resolve(),
        "test": args.test.resolve(),
    }
    for path in (old_codes, new_codes, *split_paths.values()):
        if not path.exists():
            raise FileNotFoundError(path)

    old_sid = normalize_dact_codes(old_codes, method="DACT 0.6 CF", dataset="Tools")
    new_sid = normalize_dact_codes(new_codes, method="DACT 0.7 repaired", dataset="Tools")
    catalog_size = max(int(old_sid["item_id"].max()), int(new_sid["item_id"].max()))
    metadata = pd.DataFrame({"dataset": "Tools", "item_id": np.arange(1, catalog_size + 1, dtype=int)})
    interactions = reconstruct_interactions(split_paths)

    old_coverage = coverage_row(old_sid, metadata, interactions, allow_partial=True)
    new_coverage = coverage_row(new_sid, metadata, interactions, allow_partial=False)
    old_profile = compact_profile(
        build_metric_smoke_summary(
            old_sid,
            metadata,
            interactions,
            top_k=args.d3_top_k,
            max_pair_events=args.d3_max_pair_events,
            max_user_items=args.d3_max_user_items,
        )
    )
    new_profile = compact_profile(
        build_metric_smoke_summary(
            new_sid,
            metadata,
            interactions,
            top_k=args.d3_top_k,
            max_pair_events=args.d3_max_pair_events,
            max_user_items=args.d3_max_user_items,
        )
    )
    churn = compute_churn(old_sid, new_sid)
    full_depth = int(churn["prefix_depth"].max())
    full_churn = churn[churn["prefix_depth"] == full_depth].iloc[0]
    diagnosis = {
        "old_catalog_without_sid": int(old_coverage["metadata_without_sid"]),
        "old_interaction_items_without_sid": int(old_coverage["interaction_without_sid"]),
        "repair_catalog_without_sid": int(new_coverage["metadata_without_sid"]),
        "repair_interaction_items_without_sid": int(new_coverage["interaction_without_sid"]),
        "common_items": int(full_churn["common_items"]),
        "new_items": int(full_churn["new_only_items"]),
        "full_code_changed_common_items": int(full_churn["changed_items"]),
        "full_code_churn_rate_common": float(full_churn["churn_rate_common"]),
        "old_full_collision_rate": float(old_profile["full_collision_rate"]),
        "repair_full_collision_rate": float(new_profile["full_collision_rate"]),
        "old_d3_depth1": float(old_profile["d3_depth1_weighted_collab_recall"]),
        "repair_d3_depth1": float(new_profile["d3_depth1_weighted_collab_recall"]),
    }
    passed = bool(
        diagnosis["old_catalog_without_sid"] == 275
        and diagnosis["repair_catalog_without_sid"] == 0
        and diagnosis["common_items"] == 9610
        and diagnosis["new_items"] == 275
        and diagnosis["full_code_changed_common_items"] == 2271
        and len(old_sid) == 9610
        and len(new_sid) == 9885
    )
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    old_sid.to_parquet(output / "old_sid_assignments.parquet", index=False)
    new_sid.to_parquet(output / "repaired_sid_assignments.parquet", index=False)
    metadata.to_parquet(output / "item_metadata.parquet", index=False)
    interactions.to_parquet(output / "period_0.7_interactions.parquet", index=False)
    churn.to_csv(output / "d6_refresh_churn.csv", index=False)
    pd.DataFrame([{"stage": "diagnose", **old_profile}, {"stage": "repair_reaudit", **new_profile}]).to_csv(
        output / "d1_d5_before_after.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "stage": "diagnose",
                "artifact": "DACT Tools 0.6 CF",
                "decision": "do_not_handoff_unchanged",
                "evidence": (
                    f"{diagnosis['old_catalog_without_sid']} catalog items lack addresses under period 0.7"
                ),
            },
            {
                "stage": "repair",
                "artifact": "DACT Tools 0.7 repaired",
                "decision": "reaudit_then_adapt_generator",
                "evidence": (
                    f"coverage restored; {diagnosis['full_code_changed_common_items']} common-item addresses changed"
                ),
            },
        ]
    ).to_csv(output / "decision_walkthrough.csv", index=False)

    result = {
        "schema": "sidinspector.g22.mapping_reaudit.v1",
        "contract": CONTRACT_ID,
        "status": "PASS_G22_MAPPING_REAUDIT" if passed else "FAIL_G22_MAPPING_REAUDIT",
        "source": {
            "dact_root": str(root),
            "old_codes_sha256": sha256(old_codes),
            "new_codes_sha256": sha256(new_codes),
            "split_sha256": {name: sha256(path) for name, path in split_paths.items()},
        },
        "protocol": {
            "target_period": "0.7",
            "old_mapping": "0.6_cf",
            "repair_mapping": "0.7_dact",
            "partial_coverage_allowed_only_for_diagnosis": True,
            "d3_top_k": args.d3_top_k,
            "d3_max_pair_events": args.d3_max_pair_events,
            "d3_max_user_items": args.d3_max_user_items,
            "interaction_rows": len(interactions),
        },
        "coverage": {"diagnose": old_coverage, "repair_reaudit": new_coverage},
        "diagnosis": diagnosis,
        "profiles": {"diagnose": old_profile, "repair_reaudit": new_profile},
        "evidence_boundary": (
            "This CPU case audits a released external repair and its migration cost. "
            "Downstream generator handoff remains a separate G22 GPU gate."
        ),
    }
    (output / "g22_mapping_reaudit_result.json").write_text(
        json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8"
    )
    if not passed:
        raise RuntimeError(f"{CONTRACT_ID} failed")
    print(json.dumps(json_safe(result), indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dact-root", type=Path, default=DEFAULT_DACT_ROOT)
    parser.add_argument("--old-codes", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/Tools_0.6_cf.npy")
    parser.add_argument("--new-codes", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/Tools_0.7_dact.npy")
    parser.add_argument("--train", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/train_0.7.parquet")
    parser.add_argument("--validation", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/valid_0.7.parquet")
    parser.add_argument("--test", type=Path, default=DEFAULT_DACT_ROOT / "data/Tools/test_0.7.parquet")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--d3-top-k", type=int, default=5)
    parser.add_argument("--d3-max-pair-events", type=int, default=10_000)
    parser.add_argument("--d3-max-user-items", type=int, default=50)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
