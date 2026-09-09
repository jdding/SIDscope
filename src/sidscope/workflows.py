"""Small public mapping/checkpoint workflows over existing SIDScope kernels.

Inputs contain normalized item IDs only. No checkpoint, raw user data, internal
contract editing or manual hash construction is required.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from sidinspector.contracts import canonical_sha256, with_content_sha256, load_json, bounded_bytes


class WorkflowError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def _fail(code, detail):
    raise WorkflowError(code, detail)


@dataclass(frozen=True)
class LocalInputBudget:
    """Optional local resource policy, not part of diagnostic identity.

    None means no application-imposed cap; machine memory still bounds this
    in-memory evaluator. Byte budgets apply to file intake, rows to each table.
    This policy is never consumed from input JSON or passed to submission intake.
    """
    max_rows: int | None = None
    max_input_bytes: int | None = None
    max_parquet_bytes: int | None = None

    def __post_init__(self):
        for name in ("max_rows", "max_input_bytes", "max_parquet_bytes"):
            limit = getattr(self, name)
            if limit is not None and (type(limit) is not int or limit < 1):
                _fail("invalid_workflow_budget", f"{name} must be a positive integer or None")


def _budget(value):
    if value is None:
        return LocalInputBudget()
    if not isinstance(value, LocalInputBudget):
        _fail("invalid_workflow_budget", "LocalInputBudget required")
    return value


def _row_budget(count, budget):
    if budget.max_rows is not None and count > budget.max_rows:
        _fail("workflow_row_budget", f"rows={count}; configured maximum={budget.max_rows}")


def _rows(value, fields, budget):
    if not isinstance(value, list) or not value:
        _fail("workflow_rows_required", "expected a nonempty list of rows")
    _row_budget(len(value), budget)
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != fields:
            _fail("workflow_fields", f"row={index}; expected={sorted(fields)}")


def _item(value):
    if type(value) is not int or value < 0:
        _fail("normalized_item_required", "nonnegative integer required")
    return value


def _name(value):
    if not isinstance(value, str) or not value or len(value) > 128 or any(c in value for c in ("/", "\\", "\n", "\r")):
        _fail("invalid_workflow_identity", "short non-path identifier required")
    return value


def _report(kind, inputs, protocol, metrics, records, findings, unavailable):
    inputs = json.loads(json.dumps(inputs, allow_nan=False))
    return with_content_sha256({"format": "sidscope.workflow_report.v1", "kind": kind,
        "inputs": inputs, "input_sha256": canonical_sha256(inputs), "protocol": protocol,
        "metrics": metrics, "records": records, "findings": findings, "unavailable": unavailable,
        "verification_scope": "recomputed_from_supplied_inputs",
        "unverified_claims": ["historical_training", "native_execution_authenticity", "causal_model_quality"]})


def audit(mapping: list[dict] | str | Path, *, budget: LocalInputBudget | None = None) -> dict:
    """Compute existing D1/D2/D5 without altering SID assignments."""
    budget = _budget(budget)
    if isinstance(mapping, (str, Path)):
        mapping = _mapping_file(Path(mapping), budget)
    _rows(mapping, {"item_id", "sid"}, budget)
    width, seen = None, set()
    for row in mapping:
        item = _item(row["item_id"])
        if item in seen:
            _fail("duplicate_mapping_item", f"item={item}")
        seen.add(item)
        codes = row["sid"]
        if not isinstance(codes, list) or not codes:
            _fail("invalid_sid_width", "expected a nonempty token list")
        for code in codes:
            _item(code)
        width = len(codes) if width is None else width
        if len(codes) != width:
            _fail("inconsistent_sid_width", f"item={item}")
    import pandas as pd
    from sidinspector.metrics import utilization, collision, deployment_cost
    ordered = sorted(mapping, key=lambda row: row["item_id"])
    frame = pd.DataFrame([{ "method": "provided", "item_id": row["item_id"], "sid": ":".join(map(str, row["sid"])), **{f"sid_level_{i}": token for i, token in enumerate(row["sid"])} } for row in ordered])
    events = pd.DataFrame({"item_id": pd.Series(dtype="int64")})
    metrics = {"D1_utilization": utilization(frame).to_dict("records"), "D2_aliasing": collision(frame, events).drop(columns=["mean_popularity_full_collision_items", "mean_popularity_prefix_collision_items"]).to_dict("records"), "D5_structure": deployment_cost(frame).to_dict("records")}
    groups = {}
    for row in ordered:
        groups.setdefault(tuple(row["sid"]), []).append(row["item_id"])
    findings = [{"code": "sid_collision", "severity": "observation", "normalized_items": items, "next_check": "Inspect the upstream collision/resolution policy; do not automatically rewrite SIDs."} for items in groups.values() if len(items) > 1]
    return _report("audit", {"mapping": ordered}, {"definition": "sidscope.mapping.D1-D2-D5.v1"}, metrics, [], findings, ["D3 requires semantic neighbors or interactions", "D4 and popularity-weighted collision require training interactions", "codebook utilization fraction requires declared vocabulary capacity"])


def evaluate(predictions: list[dict], targets: list[dict], *, dataset: str, cutoff: int = 10, budget: LocalInputBudget | None = None) -> dict:
    """Diagnose published ranked item slots with exact cohort/slice binding.

    Null slots remain in place, never backfilled. No canonical target flags are
    accepted from callers. Training and native generation are not certified.
    """
    budget = _budget(budget)
    _rows(predictions, {"episode_id", "ranked_items"}, budget)
    _rows(targets, {"episode_id", "target_item_id", "slice"}, budget)
    _name(dataset)
    if type(cutoff) is not int or cutoff < 1:
        _fail("invalid_evaluation_cutoff", "expected a positive integer")
    labels, predicted = {}, {}
    for row in targets:
        ep = _name(row["episode_id"])
        if ep in labels:
            _fail("duplicate_target_episode", ep)
        _item(row["target_item_id"])
        _name(row["slice"])
        labels[ep] = row
    records = []
    for row in predictions:
        ep = _name(row["episode_id"])
        if ep in predicted:
            _fail("duplicate_prediction_episode", ep)
        slots = row["ranked_items"]
        if not isinstance(slots, list) or len(slots) < cutoff:
            _fail("insufficient_publication_depth", ep)
        items = [_item(item) for item in slots if item is not None]
        if len(set(items)) != len(items):
            _fail("duplicate_ranked_item", ep)
        predicted[ep] = row
    if set(labels) != set(predicted):
        _fail("evaluation_population_mismatch", "prediction and target episode sets differ")
    from sidinspector.contracts.report_contracts import _metric_rows
    for ep in sorted(labels):
        slots, label = predicted[ep]["ranked_items"], labels[ep]
        rank = next((i + 1 for i, item in enumerate(slots) if item == label["target_item_id"]), None)
        records.append({"episode_id": ep, "slice": label["slice"], "rank": rank, "rank_state": "exact" if rank else "right_censored", "publication_depth": len(slots), "invalid_slots": slots.count(None), "hit": rank is not None and rank <= cutoff})
    def metrics(rows):
        hit, ndcg = _metric_rows([{"target": {"exact_rank": row["rank"], "rank_state": row["rank_state"]}} for row in rows], cutoff)
        return {"episodes": len(rows), "hit_at_cutoff": hit, "ndcg_at_cutoff": ndcg, "success": sum(row["hit"] for row in rows), "miss": sum(not row["hit"] for row in rows)}
    target_rows = [labels[key] for key in sorted(labels)]
    protocol = {"dataset": dataset, "selection_sha256": canonical_sha256(target_rows), "cutoff": cutoff, "definition": "single-target macro Hit/NDCG.v1", "invalid_slots": "retain_rank_no_backfill", "censoring": "unpublished_target_is_miss_at_cutoff", "slice_definition": "explicit_target_labels.slice.v1"}
    grouped = {}
    for row in records:
        grouped.setdefault(row["slice"], []).append(row)
    results = {"overall": metrics(records), "slices": {name: metrics(grouped[name]) for name in sorted(grouped)}}
    findings = [{"code": "target_not_in_published_topk", "severity": "observation", "episode_id": row["episode_id"], "slice": row["slice"], "next_check": "Inspect candidate coverage and native resolution before attributing this miss to the checkpoint."} for row in records if not row["hit"]]
    return _report("evaluate", {"predictions": [predicted[key] for key in sorted(predicted)], "targets": target_rows, "dataset": dataset, "cutoff": cutoff}, protocol, results, records, findings, ["catalog reachability and native generation/resolution are not established by ranked item slots", "compute costs and training provenance are not supplied"])


def compare(left: dict, right: dict, *, budget: LocalInputBudget | None = None) -> dict:
    """Recompute both reports before comparing the identical protocol/cohort."""
    budget = _budget(budget)
    for report in (left, right):
        if not isinstance(report, dict) or report.get("kind") != "evaluate":
            _fail("evaluation_report_required", "compare accepts evaluate reports")
        try:
            rebuilt = evaluate(**report["inputs"], budget=budget)
        except (KeyError, TypeError) as error:
            _fail("invalid_workflow_report", type(error).__name__)
        if rebuilt != report:
            _fail("workflow_report_recomputation_mismatch", "report differs from supplied inputs")
    if left["protocol"] != right["protocol"]:
        _fail("evaluation_protocol_mismatch", "dataset/selection/cutoff/definitions must match")
    def delta(a, b):
        return {key: b[key] - a[key] for key in ("hit_at_cutoff", "ndcg_at_cutoff")}
    return with_content_sha256({"format": "sidscope.workflow_comparison.v1", "status": "qualified", "left_sha256": left["content_sha256"], "right_sha256": right["content_sha256"], "protocol": left["protocol"], "overall_delta": delta(left["metrics"]["overall"], right["metrics"]["overall"]), "slice_deltas": {name: delta(left["metrics"]["slices"][name], right["metrics"]["slices"][name]) for name in left["metrics"]["slices"]}, "regressed_episodes": [a["episode_id"] for a, b in zip(left["records"], right["records"]) if a["hit"] and not b["hit"]], "verification_scope": "recomputed_ranked_item_diagnostics_on_identical_observed_cohort", "unavailable": ["full dataset/catalog identity", "matched experimental controls", "statistical significance", "causal attribution", "compute comparison"]})


def _mapping_file(path, budget):
    if path.suffix.lower() == ".json":
        return load_json(path, max_bytes=budget.max_input_bytes)
    import csv
    import io
    from contextlib import ExitStack
    if path.suffix.lower() == ".csv":
        with ExitStack() as stack:
            stream = (stack.enter_context(path.open(encoding="utf-8", newline=""))
                      if budget.max_input_bytes is None else io.StringIO(bounded_bytes(path, max_bytes=budget.max_input_bytes).decode("utf-8")))
            reader = csv.DictReader(stream)
            columns, rows = reader.fieldnames, []
            for row in reader:
                _row_budget(len(rows) + 1, budget)
                if set(row) != set(columns) or any(value is None for value in row.values()):
                    _fail("invalid_mapping_columns", "CSV row does not match its header")
                rows.append(row)
    elif path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq
        import pyarrow.types as types
        source = path if budget.max_input_bytes is None else io.BytesIO(bounded_bytes(path, max_bytes=budget.max_input_bytes))
        with pq.ParquetFile(source) as file:
            _row_budget(file.metadata.num_rows, budget)
            expanded = sum(file.metadata.row_group(i).total_byte_size for i in range(file.metadata.num_row_groups))
            if budget.max_parquet_bytes is not None and expanded > budget.max_parquet_bytes:
                _fail("workflow_parquet_budget", f"metadata bytes={expanded}; configured maximum={budget.max_parquet_bytes}")
            if not all(types.is_integer(field.type) for field in file.schema_arrow):
                _fail("invalid_mapping_columns", "parquet mapping columns must be integer typed")
            table = file.read()
            columns, rows = table.column_names, table.to_pylist()
    else:
        _fail("unsupported_mapping_format", "use JSON, CSV or Parquet")
    if not columns or len(columns) != len(set(columns)):
        _fail("invalid_mapping_columns", "missing or duplicate columns")
    levels = [f"sid_level_{i}" for i in range(len(columns)-1)]
    if set(columns) != {"item_id", *levels} or not levels:
        _fail("invalid_mapping_columns", "expected item_id and contiguous sid_level_0..N")
    def integer(value):
        if type(value) is int:
            return _item(value)
        if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
            _fail("normalized_item_required", "CSV values must be nonnegative integers")
        return int(value)
    return [{"item_id": integer(row["item_id"]), "sid": [integer(row[col]) for col in levels]} for row in rows]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("audit", "evaluate", "compare"))
    parser.add_argument("--input", type=Path, required=True, help="JSON mapping list, evaluation arguments, or {left,right} reports")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row cap per input table; no default cap.")
    parser.add_argument("--max-input-bytes", type=int, default=None, help="Optional source-file byte cap; no default cap.")
    parser.add_argument("--max-parquet-bytes", type=int, default=None, help="Optional metadata-reported Parquet expansion cap.")
    args = parser.parse_args(argv)
    try:
        budget = LocalInputBudget(args.max_rows, args.max_input_bytes, args.max_parquet_bytes)
        if args.operation == "audit":
            result = audit(args.input, budget=budget)
        else:
            value = load_json(args.input, max_bytes=budget.max_input_bytes)
            if not isinstance(value, dict) or "budget" in value:
                _fail("workflow_fields", "Input must be an argument object without resource-policy fields")
            result = {"evaluate": evaluate, "compare": compare}[args.operation](**value, budget=budget)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, sort_keys=True, allow_nan=False) + "\n")
    except (ValueError, TypeError, OSError, KeyError) as error:
        print(json.dumps({"status": "fail", "failure": {"code": getattr(error, "code", type(error).__name__), "detail": str(error)}}))
        return 2
    print(json.dumps({"status": "pass", "content_sha256": result["content_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
