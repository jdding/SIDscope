"""Mapping-first joins and conditional D1--D5 over normalized local inputs.

Only explicit training interactions feed popularity/collaborative diagnostics.
No mapping is repaired and no missing catalog, split or target is inferred.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from sidscope.workflows import LocalInputBudget, audit, _budget, _rows, _item, _name, _fail, _report
from sidinspector.contracts import load_json


def _unique(rows, field, code):
    result = {}
    for row in rows:
        key = row[field]
        if key in result:
            _fail(code, str(key))
        result[key] = row
    return result


def preflight(mapping, *, dataset, catalog=None, splits=None, targets=None,
              interactions=None, budget=None):
    """Validate joins before invoking existing metrics; omitted inputs stay absent.

    catalog: item_id, optional category (uniform columns).
    splits: episode_id, split (train/valid/test), target_item_id, history_item_ids.
    targets: episode_id, split, target_item_id, sid (the expected target SID).
    interactions: normalized_user_id, item_id, split. Duplicate events count as
    repeated observations for popularity; D3's existing kernel deduplicates pairs.
    """
    policy = _budget(budget)
    _name(dataset)
    base = audit(mapping, budget=policy)
    mapped = {row["item_id"]: row for row in base["inputs"]["mapping"]}
    inputs = {"mapping": base["inputs"]["mapping"], "dataset": dataset}
    checks, unavailable = {}, []
    def member(item, where):
        _item(item)
        if item not in mapped:
            _fail("item_without_mapping", f"{where}: normalized item {item}")
    categories = False
    if catalog is not None:
        categories = isinstance(catalog, list) and bool(catalog) and isinstance(catalog[0], dict) and "category" in catalog[0]
        _rows(catalog, {"item_id", "category"} if categories else {"item_id"}, policy)
        for row in catalog:
            _item(row["item_id"])
            if categories:
                _name(row["category"])
        catalog_by_id = _unique(catalog, "item_id", "duplicate_catalog_item")
        if set(catalog_by_id) != set(mapped):
            _fail("catalog_mapping_mismatch", f"catalog_without_mapping={sorted(set(catalog_by_id)-set(mapped))[:10]}; mapping_without_catalog={sorted(set(mapped)-set(catalog_by_id))[:10]}")
        inputs["catalog"] = sorted(catalog, key=lambda row: row["item_id"])
        checks["catalog_mapping"] = {"status": "pass", "items": len(catalog)}
    else:
        unavailable.append("catalog_mapping: catalog not supplied")
    split_by_id = None
    if splits is not None:
        _rows(splits, {"episode_id", "split", "target_item_id", "history_item_ids"}, policy)
        for row in splits:
            _name(row["episode_id"])
            if not isinstance(row["split"], str) or row["split"] not in {"train", "valid", "test"}:
                _fail("invalid_split", row["episode_id"])
            member(row["target_item_id"], "split target")
            if not isinstance(row["history_item_ids"], list):
                _fail("invalid_history", row["episode_id"])
            for item in row["history_item_ids"]:
                member(item, "split history")
        split_by_id = _unique(splits, "episode_id", "duplicate_split_episode")
        inputs["splits"] = sorted(splits, key=lambda row: row["episode_id"])
        checks["split_mapping"] = {"status": "pass", "episodes": len(splits)}
    else:
        unavailable.append("split_mapping: splits not supplied")
    if targets is not None:
        _rows(targets, {"episode_id", "split", "target_item_id", "sid"}, policy)
        for row in targets:
            _name(row["episode_id"])
        _unique(targets, "episode_id", "duplicate_target_episode")
        for row in targets:
            _name(row["episode_id"])
            if not isinstance(row["split"], str) or row["split"] not in {"train", "valid", "test"}:
                _fail("invalid_split", row["episode_id"])
            member(row["target_item_id"], "selected target")
            if not isinstance(row["sid"], list) or any(type(code) is not int or code < 0 for code in row["sid"]) or row["sid"] != mapped[row["target_item_id"]]["sid"]:
                _fail("target_sid_mismatch", row["episode_id"])
            if split_by_id is not None:
                source = split_by_id.get(row["episode_id"])
                if source is None:
                    _fail("target_episode_out_of_split", row["episode_id"])
                if source["split"] != row["split"]:
                    _fail("target_split_mismatch", row["episode_id"])
                if source["target_item_id"] != row["target_item_id"]:
                    _fail("target_item_mismatch", row["episode_id"])
        inputs["targets"] = sorted(targets, key=lambda row: row["episode_id"])
        checks["target_sid"] = {"status": "pass", "selected_episodes": len(targets)}
        if split_by_id is not None:
            checks["target_split"] = {"status": "pass", "selection_policy": "explicit_subset"}
        else:
            unavailable.append("target_split: splits not supplied")
    else:
        unavailable.append("target_sid and target_split: targets not supplied")
    training = []
    if interactions is not None:
        _rows(interactions, {"normalized_user_id", "item_id", "split"}, policy)
        for row in interactions:
            _item(row["normalized_user_id"])
            member(row["item_id"], "interaction")
            if not isinstance(row["split"], str) or row["split"] not in {"train", "valid", "test"}:
                _fail("invalid_split", "interaction")
        inputs["interactions"] = sorted(interactions, key=lambda row: (row["split"], row["normalized_user_id"], row["item_id"]))
        training = [row for row in inputs["interactions"] if row["split"] == "train"]
        checks["interaction_mapping"] = {"status": "pass", "train_events": len(training), "excluded_nontrain_events": len(interactions)-len(training)}
    import pandas as pd
    from sidinspector.metrics import alignment, head_tail_capacity, collision
    frame = pd.DataFrame([{"method": "provided", "item_id": row["item_id"], "sid": ":".join(map(str, row["sid"])), **{f"sid_level_{i}": code for i, code in enumerate(row["sid"])}} for row in base["inputs"]["mapping"]])
    # Never call the legacy kernel with held-out-only data: its fallback uses all
    # rows when no training partition exists. This wrapper filters first.
    events = pd.DataFrame([{"user_id": row["normalized_user_id"], "item_id": row["item_id"], "split": "train"} for row in training], columns=["user_id", "item_id", "split"])
    metrics = dict(base["metrics"])
    if categories or training:
        metadata = pd.DataFrame(inputs.get("catalog", [{"item_id": item} for item in mapped]))
        aligned = alignment(frame, metadata, events)
        if not categories:
            aligned = aligned.drop(columns=["level0_category_purity_mean", "level0_non_singleton_buckets"])
        if not training or not aligned["collab_items"].any():
            for col in ("mean_collab_prefix_recall", "weighted_collab_prefix_recall", "collab_edges_same_prefix_rate"):
                aligned[col] = None
            unavailable.append("D3 collaborative alignment: no eligible training cooccurrence edges")
        metrics["D3_alignment"] = aligned.astype(object).where(aligned.notna(), None).to_dict("records")
    else:
        unavailable.append("D3_alignment: category metadata and training interactions not supplied")
    if not categories:
        unavailable.append("D3 category purity: category metadata not supplied")
    if training:
        metrics["D4_popularity"] = head_tail_capacity(frame, events).to_dict("records")
        metrics["D2_aliasing"] = collision(frame, events).to_dict("records")
    else:
        unavailable.append("D4 and weighted D2: no explicit training interactions")
    unavailable.extend(["codebook utilization fraction requires declared vocabulary capacity", "temporal leakage and source split authenticity are not established by declared split labels"])
    report = _report("mapping_preflight", inputs, {"definition": "sidscope.mapping.preflight.v1", "training_policy": "explicit_train_only", "alignment_top_k": 20, "alignment_max_pair_events": 2000000, "alignment_max_user_items": 200}, metrics, [], base["findings"], unavailable)
    # Checks are part of the deterministic evidence, not a side-channel status.
    from sidinspector.contracts import with_content_sha256
    return with_content_sha256({**report, "checks": checks})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSON preflight arguments; normalized IDs only")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--max-input-bytes", type=int, default=None)
    parser.add_argument("--max-parquet-bytes", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        budget = LocalInputBudget(args.max_rows, args.max_input_bytes, args.max_parquet_bytes)
        spec = load_json(args.input, max_bytes=budget.max_input_bytes)
        if not isinstance(spec, dict) or "budget" in spec:
            _fail("invalid_preflight_spec", "argument object required; budget is caller policy")
        if isinstance(spec.get("mapping"), str):
            spec["mapping"] = args.input.parent / spec["mapping"]
        result = preflight(**spec, budget=budget)
        with args.output.open("x") as handle:
            handle.write(json.dumps(result, sort_keys=True, allow_nan=False)+"\n")
    except (ValueError, TypeError, OSError, KeyError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps({"status": "pass", "content_sha256": result["content_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
