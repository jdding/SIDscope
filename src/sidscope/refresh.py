"""Bounded SID refresh lifecycle diagnostics over caller-supplied snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sidinspector.contracts import canonical_sha256, load_json, with_content_sha256
from sidinspector.evidence import scan_evidence_content
from sidscope.regression import checked_report
from sidscope.workflows import LocalInputBudget, WorkflowError, _budget, _item, _name, _row_budget, compare, evaluate


def _fail(code: str, detail: str) -> None:
    raise WorkflowError(code, detail)


def _snapshot(value: Any, budget: LocalInputBudget | None = None) -> tuple[dict, dict[int, int]]:
    budget = _budget(budget)
    fields = {"dataset", "item_namespace", "sid_namespace", "semantics", "mapping"}
    if not isinstance(value, dict) or set(value) != fields:
        _fail("refresh_snapshot_fields", f"expected={sorted(fields)}")
    for field in ("dataset", "item_namespace", "sid_namespace"):
        _name(value[field])
    semantics = value["semantics"]
    if semantics not in {"ordered_prefix", "parallel_positions", "unordered_set"}:
        _fail("unsupported_sid_semantics", str(semantics))
    mapping = value["mapping"]
    if not isinstance(mapping, list):
        _fail("refresh_mapping_required", "mapping must be a list")
    _row_budget(len(mapping), budget)
    rows, pointers, seen, width = [], {}, set(), None
    for index, row in enumerate(mapping):
        if not isinstance(row, dict) or set(row) != {"item_id", "sid"}:
            _fail("refresh_mapping_fields", f"row={index}")
        item = _item(row["item_id"])
        if item in seen:
            _fail("duplicate_mapping_item", f"item={item}")
        seen.add(item)
        sid = row["sid"]
        if not isinstance(sid, list) or not sid:
            _fail("invalid_sid_width", f"row={index}")
        tokens = [_item(token) for token in sid]
        if semantics == "unordered_set" and len(tokens) != len(set(tokens)):
            _fail("duplicate_unordered_sid_token", f"row={index}")
        if semantics in {"ordered_prefix", "parallel_positions"}:
            width = len(tokens) if width is None else width
            if len(tokens) != width:
                _fail("inconsistent_sid_width", f"item={item}")
        rows.append({"item_id": item, "sid": tokens})
        pointers[item] = index
    normalized = {key: value[key] for key in ("dataset", "item_namespace", "sid_namespace", "semantics")}
    normalized["mapping"] = sorted(rows, key=lambda row: row["item_id"])
    return normalized, pointers


def _key(row: dict, semantics: str, depth: int | None = None) -> tuple[int, ...]:
    tokens = row["sid"] if depth is None else row["sid"][:depth]
    return tuple(sorted(tokens)) if semantics == "unordered_set" else tuple(tokens)


def _partitions(old: dict[int, dict], new: dict[int, dict], common: list[int], semantics: str, depth: int | None) -> tuple[dict, set[int]]:
    old_keys = {item: _key(old[item], semantics, depth) for item in common}
    new_keys = {item: _key(new[item], semantics, depth) for item in common}
    old_sizes, new_sizes = Counter(old_keys.values()), Counter(new_keys.values())
    intersections = Counter((old_keys[item], new_keys[item]) for item in common)
    affected = {item for item in common if not (
        old_sizes[old_keys[item]] == new_sizes[new_keys[item]] == intersections[(old_keys[item], new_keys[item])]
    )}
    old_to_new, new_to_old = defaultdict(set), defaultdict(set)
    for item in common:
        old_to_new[old_keys[item]].add(new_keys[item])
        new_to_old[new_keys[item]].add(old_keys[item])
    return {
        "depth": depth,
        "scope": "full_code" if depth is None else "prefix",
        "common_items": len(common),
        "affected_items": len(affected),
        "stable_items": len(common) - len(affected),
        "split_groups": sum(len(values) > 1 for values in old_to_new.values()),
        "merge_groups": sum(len(values) > 1 for values in new_to_old.values()),
        "affected_rate_common": len(affected) / len(common) if common else None,
    }, affected


def _raw_churn(old_snapshot: dict, new_snapshot: dict, common: list[int]) -> dict:
    if not common:
        return {"status": "unavailable", "reason": "no_common_items", "levels": []}
    old_rows = {row["item_id"]: row for row in old_snapshot["mapping"]}
    new_rows = {row["item_id"]: row for row in new_snapshot["mapping"]}
    if old_snapshot["semantics"] == "ordered_prefix":
        import pandas as pd
        from sidinspector.churn import compute_churn
        def frame(snapshot: dict) -> Any:
            return pd.DataFrame([{"item_id": row["item_id"], **{
                f"sid_level_{index}": token for index, token in enumerate(row["sid"])
            }} for row in snapshot["mapping"]])
        levels = compute_churn(frame(old_snapshot), frame(new_snapshot)).to_dict("records")
        for row in levels:
            if row["common_items"] == 0:
                row["churn_rate_common"] = None
        return {"status": "computed_with_d6", "levels": levels}
    literal = sum(tuple(old_rows[item]["sid"]) != tuple(new_rows[item]["sid"]) for item in common)
    if old_snapshot["semantics"] == "parallel_positions":
        return {"status": "computed_parallel_full_code", "levels": [{
            "scope": "full_code", "common_items": len(common), "literal_changed_items": literal,
            "literal_churn_rate_common": literal / len(common)}]}
    membership = sum(set(old_rows[item]["sid"]) != set(new_rows[item]["sid"]) for item in common)
    return {"status": "computed_unordered_full_set", "levels": [{
        "scope": "full_code", "common_items": len(common),
        "literal_changed_items": literal, "membership_changed_items": membership,
        "representation_only_items": literal - membership,
        "literal_churn_rate_common": literal / len(common),
        "membership_churn_rate_common": membership / len(common),
    }]}


def _relabel_classification(old_snapshot: dict, new_snapshot: dict, common: list[int], affected: set[int]) -> dict:
    old = {row["item_id"]: row for row in old_snapshot["mapping"]}
    new = {row["item_id"]: row for row in new_snapshot["mapping"]}
    old_widths = sorted({len(row["sid"]) for row in old.values()})
    new_widths = sorted({len(row["sid"]) for row in new.values()})
    literal_changed = sum(tuple(old[item]["sid"]) != tuple(new[item]["sid"]) for item in common)
    namespace_changed = old_snapshot["sid_namespace"] != new_snapshot["sid_namespace"]
    if not common:
        label, bijective = "unavailable_no_common_items", None
    elif old_snapshot["semantics"] == "unordered_set":
        membership_changed = sum(set(old[item]["sid"]) != set(new[item]["sid"]) for item in common)
        label = "structural_change" if affected else "representation_only" if literal_changed else "unchanged"
        if not affected and membership_changed:
            label = "membership_preserved_not_proven_relabel"
        bijective = None
    elif old_widths != new_widths:
        label, bijective = "width_changed", None
    else:
        bijective = True
        for position in range(old_widths[0]):
            forward, reverse = defaultdict(set), defaultdict(set)
            for item in common:
                a, b = old[item]["sid"][position], new[item]["sid"][position]
                forward[a].add(b); reverse[b].add(a)
            bijective &= all(len(values) == 1 for values in forward.values()) and all(len(values) == 1 for values in reverse.values())
        if affected:
            label = "structural_change"
        elif literal_changed == 0 and not namespace_changed:
            label = "unchanged"
        elif bijective:
            label = "consistent_with_namespace_relabel_on_common_items"
        else:
            label = "membership_preserved_not_proven_relabel"
    return {"classification": label, "namespace_changed": namespace_changed,
        "old_widths": old_widths, "new_widths": new_widths,
        "literal_changed_items": literal_changed,
        "positionwise_bijection_on_common_items": bijective,
        "limits": "Classification does not prove author intent, geometry, unseen-item equivalence or upstream execution."}


def bind_evaluation(snapshot: dict, report: dict, *, budget: LocalInputBudget | None = None) -> dict:
    normalized, _ = _snapshot(snapshot, budget)
    checked_report(report)
    if report["protocol"]["dataset"] != normalized["dataset"]:
        _fail("refresh_evaluation_dataset_mismatch", "evaluation and snapshot datasets differ")
    catalog = {row["item_id"] for row in normalized["mapping"]}
    inputs = report["inputs"]
    observed = {row["target_item_id"] for row in inputs["targets"]}
    observed.update(item for row in inputs["predictions"] for item in row["ranked_items"] if item is not None)
    missing = sorted(observed - catalog)
    if missing:
        _fail("refresh_evaluation_catalog_mismatch", f"items={missing[:5]}; count={len(missing)}")
    return with_content_sha256({"format": "sidscope.sid_refresh_evaluation_binding.v1",
        "snapshot_sha256": canonical_sha256(normalized), "evaluation": report,
        "binding_scope": "caller_declared_mapping_for_recomputed_ranked_evaluation",
        "unverified_claims": ["upstream_execution_used_this_mapping", "historical_training", "causal_refresh_effect"]})


def _bound_evaluation(snapshot: dict, binding: Any, budget: LocalInputBudget | None) -> dict:
    if not isinstance(binding, dict) or binding.get("format") != "sidscope.sid_refresh_evaluation_binding.v1":
        _fail("invalid_refresh_evaluation_binding", "binding format required")
    try:
        rebuilt = bind_evaluation(snapshot, binding["evaluation"], budget=budget)
    except KeyError as error:
        _fail("invalid_refresh_evaluation_binding", str(error))
    if rebuilt != binding:
        _fail("refresh_evaluation_binding_mismatch", "binding differs from recomputed snapshot/report identity")
    return binding["evaluation"]


def _downstream(old_snapshot: dict, new_snapshot: dict, downstream: Any, categories: dict[str, set[int]], budget: LocalInputBudget | None) -> dict:
    if not isinstance(downstream, dict) or set(downstream) != {"old", "new"}:
        _fail("invalid_refresh_downstream", "expected old and new bindings")
    old_report = _bound_evaluation(old_snapshot, downstream["old"], budget)
    new_report = _bound_evaluation(new_snapshot, downstream["new"], budget)
    if [row["publication_depth"] for row in old_report["records"]] != [row["publication_depth"] for row in new_report["records"]]:
        _fail("evaluation_protocol_mismatch", "refresh comparison requires identical publication depths")
    overall = compare(old_report, new_report, budget=budget)
    target_by_episode = {row["episode_id"]: row["target_item_id"] for row in old_report["inputs"]["targets"]}
    groups = {}
    for label, items in categories.items():
        episodes = {episode for episode, target in target_by_episode.items() if target in items}
        if not episodes:
            groups[label] = {"status": "unavailable", "reason": "no_targets_in_category"}
            continue
        def rebuild(report: dict) -> dict:
            inputs = report["inputs"]
            return evaluate([row for row in inputs["predictions"] if row["episode_id"] in episodes],
                [row for row in inputs["targets"] if row["episode_id"] in episodes],
                dataset=inputs["dataset"], cutoff=inputs["cutoff"], budget=budget)
        delta = compare(rebuild(old_report), rebuild(new_report), budget=budget)
        groups[label] = {"status": "computed", "targets": len(episodes),
            "overall_delta": delta["overall_delta"], "slice_deltas": delta["slice_deltas"]}
    return {"status": "computed", "overall_delta": overall["overall_delta"],
        "slice_deltas": overall["slice_deltas"], "target_lifecycle_groups": groups,
        "interpretation": "Observed association on caller-bound evidence; not a causal refresh or upstream execution claim."}


def compare_snapshots(old: dict, new: dict, *, downstream: dict | None = None,
                      max_examples: int = 20, budget: LocalInputBudget | None = None) -> dict:
    if type(max_examples) is not int or max_examples < 1:
        _fail("invalid_example_budget", "positive integer required")
    old_snapshot, old_pointers = _snapshot(old, budget)
    new_snapshot, new_pointers = _snapshot(new, budget)
    for field in ("dataset", "item_namespace", "semantics"):
        if old_snapshot[field] != new_snapshot[field]:
            _fail(f"refresh_{field}_mismatch", "snapshots cannot be implicitly aligned")
    old_sha, new_sha = canonical_sha256(old_snapshot), canonical_sha256(new_snapshot)
    old_rows = {row["item_id"]: row for row in old_snapshot["mapping"]}
    new_rows = {row["item_id"]: row for row in new_snapshot["mapping"]}
    old_items, new_items = set(old_rows), set(new_rows)
    common, added, removed = sorted(old_items & new_items), sorted(new_items - old_items), sorted(old_items - new_items)
    semantics = old_snapshot["semantics"]
    depths = []
    if semantics == "ordered_prefix" and old_rows and new_rows:
        depths = list(range(1, min(len(next(iter(old_rows.values()))["sid"]), len(next(iter(new_rows.values()))["sid"])) + 1))
    structural, affected_by_scope = [], {}
    for depth in [*depths, None]:
        row, affected = _partitions(old_rows, new_rows, common, semantics, depth)
        structural.append(row); affected_by_scope["full_code" if depth is None else f"prefix_{depth}"] = affected
    full_affected = affected_by_scope["full_code"]
    raw_changed = {item for item in common if tuple(old_rows[item]["sid"]) != tuple(new_rows[item]["sid"])}
    categories = {"structural_change": full_affected, "raw_changed_structure_stable": raw_changed - full_affected,
        "stable": set(common) - raw_changed - full_affected}
    def examples(kind: str, items: list[int], pointers: dict[int, int], salt: str) -> list[dict]:
        return [{"item_alias": hashlib.sha256(f"{old_sha}:{new_sha}:{salt}:{item}".encode()).hexdigest()[:20],
            "source_pointer": f"/{kind}/mapping/{pointers[item]}"} for item in items[:max_examples]]
    example_rows = {
        "added": examples("new", added, new_pointers, "added"),
        "removed": examples("old", removed, old_pointers, "removed"),
        "structural_change": [{
            "item_alias": hashlib.sha256(f"{old_sha}:{new_sha}:structural:{item}".encode()).hexdigest()[:20],
            "old_pointer": f"/old/mapping/{old_pointers[item]}", "new_pointer": f"/new/mapping/{new_pointers[item]}"
        } for item in sorted(full_affected)[:max_examples]],
    }
    result = {"format": "sidscope.sid_refresh_report.v1", "status": "computed",
        "identity": {"dataset": old_snapshot["dataset"], "item_namespace": old_snapshot["item_namespace"],
            "old_sid_namespace": old_snapshot["sid_namespace"], "new_sid_namespace": new_snapshot["sid_namespace"], "semantics": semantics},
        "old_snapshot_sha256": old_sha, "new_snapshot_sha256": new_sha,
        "population": {"old_items": len(old_items), "new_items": len(new_items), "common_items": len(common),
            "added_items": len(added), "removed_items": len(removed)},
        "raw_churn": _raw_churn(old_snapshot, new_snapshot, common),
        "structural_change": structural,
        "classification": _relabel_classification(old_snapshot, new_snapshot, common, full_affected),
        "examples": example_rows, "max_examples_per_category": max_examples,
        "omitted_examples": {"added": max(0, len(added)-len(example_rows["added"])),
            "removed": max(0, len(removed)-len(example_rows["removed"])),
            "structural_change": max(0, len(full_affected)-len(example_rows["structural_change"]))},
        "downstream": None,
        "verification_scope": "recomputed_from_supplied_sid_snapshots",
        "limitations": ["Snapshot identities are caller declarations, not authenticated dataset or training facts.",
            "Token relabel consistency is not proof of intent, geometry or equivalence on unseen items.",
            "Added and removed items are excluded from common-item structural denominators.",
            "No SID is aligned, repaired or rewritten by this report."]}
    if downstream is not None:
        result["downstream"] = _downstream(old_snapshot, new_snapshot, downstream, categories, budget)
    result = with_content_sha256(result)
    scan_evidence_content(result)
    return result


def render_markdown(report: dict) -> str:
    population, classification = report["population"], report["classification"]
    lines = ["# SIDScope SID refresh lifecycle report", "",
        f"- Classification: `{classification['classification']}`",
        f"- Common items: {population['common_items']}", f"- Added items: {population['added_items']}",
        f"- Removed items: {population['removed_items']}",
        f"- Old snapshot: `{report['old_snapshot_sha256']}`", f"- New snapshot: `{report['new_snapshot_sha256']}`", "",
        "## Structural observations", "", "| Scope | Depth | Affected | Split groups | Merge groups |", "| --- | ---: | ---: | ---: | ---: |"]
    for row in report["structural_change"]:
        lines.append(f"| {row['scope']} | {row['depth'] if row['depth'] is not None else '—'} | {row['affected_items']} | {row['split_groups']} | {row['merge_groups']} |")
    lines += ["", "The report recomputes supplied snapshots. It does not authenticate training, infer causality or rewrite SIDs.", ""]
    return "\n".join(lines)


def write_report(output: str | Path, old: dict, new: dict, **kwargs: Any) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    report = compare_snapshots(old, new, **kwargs)
    markdown = render_markdown(report)
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    (output / "report.md").write_text(markdown, encoding="utf-8")
    receipt = with_content_sha256({"format": "sidscope.sid_refresh_completion.v1", "status": "pass",
        "report_sha256": report["content_sha256"], "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest()})
    (output / "complete.json").write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--old", type=Path, required=True); compare_parser.add_argument("--new", type=Path, required=True)
    compare_parser.add_argument("--downstream", type=Path); compare_parser.add_argument("--output", type=Path, required=True)
    compare_parser.add_argument("--max-examples", type=int, default=20)
    bind_parser = sub.add_parser("bind")
    bind_parser.add_argument("--snapshot", type=Path, required=True); bind_parser.add_argument("--evaluation", type=Path, required=True)
    bind_parser.add_argument("--output", type=Path, required=True)
    for child in (compare_parser, bind_parser):
        child.add_argument("--max-rows", type=int); child.add_argument("--max-input-bytes", type=int)
    args = parser.parse_args(argv)
    try:
        budget = LocalInputBudget(max_rows=args.max_rows, max_input_bytes=args.max_input_bytes)
        if args.operation == "bind":
            result = bind_evaluation(load_json(args.snapshot, max_bytes=args.max_input_bytes),
                load_json(args.evaluation, max_bytes=args.max_input_bytes), budget=budget)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(result, sort_keys=True, allow_nan=False) + "\n")
        else:
            downstream = load_json(args.downstream, max_bytes=args.max_input_bytes) if args.downstream else None
            result = write_report(args.output, load_json(args.old, max_bytes=args.max_input_bytes),
                load_json(args.new, max_bytes=args.max_input_bytes), downstream=downstream,
                max_examples=args.max_examples, budget=budget)
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)})); return 2
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
