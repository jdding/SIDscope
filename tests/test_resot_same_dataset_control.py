from __future__ import annotations

import pandas as pd

from pathlib import Path

from tools.build_resot_same_dataset_control import build_category_prefix_control, build_result


def test_category_prefix_control_removes_common_root_and_is_unique() -> None:
    metadata = pd.DataFrame(
        {
            "item_id": [3, 1, 2, 4],
            "category": [
                "Root,Strings,Guitar,Acoustic",
                "Root,Microphones,Dynamic",
                "Root,Microphones,Condenser",
                "Root,Strings,Guitar,Electric",
            ],
        }
    )

    control, removed = build_category_prefix_control(metadata)

    assert removed == ["Root"]
    assert control["sid"].nunique() == len(metadata)
    microphones = control[control["item_id"].isin([1, 2])]
    strings = control[control["item_id"].isin([3, 4])]
    assert microphones["sid_level_0"].nunique() == 1
    assert strings["sid_level_0"].nunique() == 1
    assert microphones["sid_level_0"].iloc[0] != strings["sid_level_0"].iloc[0]


def test_frozen_resot_control_reports_all_prefix_depths() -> None:
    root = Path(__file__).resolve().parents[1]
    result = build_result(root / "experiments/v1_evidence_chain/gate17_resot_intake/normalized_text")
    assert [row["prefix_depth"] for row in result["source_artifact"]["d3_by_depth"]] == [1, 2, 3, 4]
    assert [row["prefix_depth"] for row in result["category_prefix_control"]["d3_by_depth"]] == [1, 2, 3, 4]
