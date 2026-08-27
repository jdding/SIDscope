#!/usr/bin/env python3
"""Run a bounded smoke over pure ISD functions in an external source file."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


EXPECTED_UNIFIED_SHA256 = "c4f7a2593ce819171c368be1af5a5a3e8cfc7821831d6eb0f42f2cc94af66421"
EXPECTED_PROVIDER_SHA256 = "055b263e5f7fd9e4b35aea30ec9297b09e36363924f0907bcdf97b6392439586"
SNAPSHOT_ID = "ISD-CF7C"
SELECTED_FUNCTIONS = {
    "support_maps",
    "_native_top_indices",
    "_select_owner",
    "final_rrf",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pure_functions(path: Path) -> dict[str, Any]:
    """Load only four dependency-light functions without importing the project."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in SELECTED_FUNCTIONS
    ]
    observed = {node.name for node in nodes}
    if observed != SELECTED_FUNCTIONS:
        raise RuntimeError(
            f"official source missing expected functions: {sorted(SELECTED_FUNCTIONS - observed)}"
        )
    future = ast.ImportFrom(
        module="__future__",
        names=[ast.alias(name="annotations")],
        level=0,
    )
    module = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    namespace: dict[str, Any] = {
        "np": np,
        "POSITIONS": (1, 2, 3),
        "BEAM_WIDTH": 2,
        "RRF_CONSTANT": 60,
    }
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


def run(unified_source: Path, provider_source: Path) -> dict[str, Any]:
    unified_hash = sha256(unified_source)
    provider_hash = sha256(provider_source)
    if unified_hash != EXPECTED_UNIFIED_SHA256:
        raise RuntimeError("unified ISD source hash differs from audited snapshot")
    if provider_hash != EXPECTED_PROVIDER_SHA256:
        raise RuntimeError("SASRec-ISD provider source hash differs from audited snapshot")
    namespace = load_pure_functions(unified_source)

    internal_sids = np.asarray(
        [
            [1, 5, 9],
            [1, 6, 10],
            [2, 7, 11],
            [2, 8, 12],
        ],
        dtype=np.int64,
    )
    supports = namespace["support_maps"](
        [np.asarray([2, 0, 1], dtype=np.int64)], internal_sids
    )[0]
    selected = namespace["_select_owner"](
        [(tuple(), 0.0, None)],
        np.asarray([[-0.10, -0.20, -0.30]], dtype=np.float64),
        np.asarray([1, 2, 3], dtype=np.int64),
        supports[1],
    )
    final = namespace["final_rrf"](
        [(0, -0.20), (2, -0.24), (3, -0.30)],
        [2, 0, 1],
    )
    support_rows = {
        str(depth): [
            {"prefix_tokens": list(prefix), "best_supporting_item_rank": rank}
            for prefix, rank in sorted(values.items())
        ]
        for depth, values in supports.items()
    }
    outputs = {
        "support_maps": support_rows,
        "selected_prefixes": [list(entry[0]) for entry in selected],
        "selected_native_scores": [entry[1] for entry in selected],
        "selected_support_ranks": [entry[2] for entry in selected],
        "final_ranked_item_indices": final,
    }
    expected = {
        "depth_1_supports": [
            {"prefix_tokens": [1], "best_supporting_item_rank": 2},
            {"prefix_tokens": [2], "best_supporting_item_rank": 1},
        ],
        "selected_prefixes": [[1], [2]],
        "selected_support_ranks": [2, 1],
        "final_ranked_item_indices": [0, 2, 3],
    }
    passed = (
        support_rows["1"] == expected["depth_1_supports"]
        and outputs["selected_prefixes"] == expected["selected_prefixes"]
        and outputs["selected_support_ranks"] == expected["selected_support_ranks"]
        and outputs["final_ranked_item_indices"] == expected["final_ranked_item_indices"]
    )
    return {
        "schema": "sidscope.isd_official_source_smoke.v1",
        "status": "pass" if passed else "fail",
        "source_snapshot_id": SNAPSHOT_ID,
        "source_revision": None,
        "source_sha256": {
            "eval_sid_route_unified_tiger_liger_v1.py": unified_hash,
            "eval_sid_route_sasrec_isd_v1.py": provider_hash,
        },
        "runtime": "CPU NumPy; selected pure functions loaded by AST from external source",
        "inputs": {
            "internal_sids": internal_sids.tolist(),
            "provider_shortlist_item_indices": [2, 0, 1],
            "rrf_constant": 60,
            "beam_width": 2,
        },
        "outputs": outputs,
        "expected": expected,
        "boundary": (
            "Exact official support-map, prefix-selection, and final-RRF functions only; "
            "no model, checkpoint, data, or full evaluator execution. The anonymous "
            "snapshot exposes no Git revision or root code license."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unified-source", type=Path, required=True)
    parser.add_argument("--provider-source", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(args.unified_source, args.provider_source)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
