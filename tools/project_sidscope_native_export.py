#!/usr/bin/env python3
"""Project permitted native RPG/PSID exports, preserving original rank slots.

Pure local data processing: no model imports, commands, keys, or caches. Missing
PSID labels stay unavailable. This projection is not a complete TraceEnvelope:
unobserved generation and compute fields must not be filled with false or zero.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from sidinspector.contracts import canonical_sha256, with_content_sha256
from sidinspector.contracts.json_io import loads_json, bounded_bytes
from sidinspector.contracts.report_contracts import _metric_rows
from sidinspector.evidence.bundle import scan_evidence_content
from tools.inspect_sidscope_native_export import NativeInspectionError
from tools.verify_rpg_trained_trace_bundle import verify as verify_rpg
from sidinspector.adapters.latte import validate_latte_psid_trained_trace_bundle


def fail(code, detail):
    raise NativeInspectionError(code, detail)


def _selection(value, native, digest):
    expected = {"format", "native_sha256", "checkpoint_sha256", "split_id", "target_universe_sha256", "rows"}
    if not isinstance(value, dict) or set(value) != expected or value["format"] != "sidscope.native_selection.v1":
        fail("invalid_native_selection", "explicit identity-bound selection required")
    scan_evidence_content(value)
    for key, wanted in {"native_sha256": digest,
        "checkpoint_sha256": native["evidence"]["checkpoint_sha256"],
        "split_id": native["evidence"]["split_id"],
        "target_universe_sha256": native["target_universe"]["sha256"]}.items():
        if value[key] != wanted:
            fail("native_selection_binding_mismatch", key)
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) != len(native["episodes"]):
        fail("native_selection_population_mismatch", "exact exported cohort required")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"episode_id", "target_normalized_item_id", "slice", "cluster_id"}:
            fail("invalid_native_selection_row", "normalized target, slice and nullable cluster ID required")
        if any(not isinstance(row[key], str) or not row[key] for key in ("episode_id", "slice")):
            fail("invalid_native_selection_row", "nonempty IDs required")
        if row["cluster_id"] is not None and (not isinstance(row["cluster_id"], str) or not row["cluster_id"]):
            fail("invalid_cluster_id", row["episode_id"])
        if type(row["target_normalized_item_id"]) is not int or row["target_normalized_item_id"] < 0:
            fail("invalid_native_target", row["episode_id"])
        if row["episode_id"] in by_id:
            fail("duplicate_native_selection_episode", row["episode_id"])
        by_id[row["episode_id"]] = row
    if set(by_id) != {ep["trace_id"] for ep in native["episodes"]}:
        fail("native_selection_population_mismatch", "episode identities differ")
    return by_id


def project_export(path: Path, *, selection: Path | None = None):
    path = Path(path)
    payload = bounded_bytes(path, max_bytes=None)
    native = loads_json(payload, max_bytes=None)
    if not isinstance(native, dict):
        fail("invalid_native_document", "object required")
    # Validation, projection and identity all use one byte snapshot.
    digest = hashlib.sha256(payload).hexdigest()
    try:
        if native.get("schema") == "sidscope.rpg_trained_trace_bundle.v1":
            verify_rpg(native)
        elif native.get("schema") == "sidscope.latte_psid_trained_trace_bundle.v2":
            validate_latte_psid_trained_trace_bundle(native)
        else:
            fail("unsupported_native_projection", str(native.get("schema")))
    except (ValueError, KeyError, TypeError) as error:
        if isinstance(error, NativeInspectionError):
            raise
        fail("native_verification_failed", str(error))
    rpg = native["method"] == "RPG"
    if not rpg and native["method"] != "PSID":
        fail("unsupported_native_projection", "only the approved RPG and PSID families")
    selection_bytes = bounded_bytes(Path(selection), max_bytes=None) if selection else None
    labels = _selection(loads_json(selection_bytes, max_bytes=None), native, digest) if selection_bytes is not None else {}
    universe = {r["normalized_item_id"] for r in native["target_universe"]["rows"]}
    complete_catalog = not rpg or native["target_universe"]["visibility"] == "external_complete"
    records, selected = [], []
    depths = set()
    for ep in native["episodes"]:
        label = labels.get(ep["trace_id"])
        if rpg:
            native_target = ep["target_normalized_item_id"]
            if label and label["target_normalized_item_id"] != native_target:
                fail("native_target_mismatch", ep["trace_id"])
            label = label or {"episode_id": ep["trace_id"], "target_normalized_item_id": native_target, "slice": "overall", "cluster_id": None}
            slots = [row["normalized_item_id"] for row in ep["ranked_items"]]
            cutoff = native["configuration"]["rank_cutoff"]
        else:
            slots = [row["normalized_item_id"] if row["valid"] else None for row in ep["evaluation_slots"]]
            cutoff = ep["evaluation_cutoff"]
            if label and label["slice"] != ep["gap_bucket"]:
                fail("native_slice_mismatch", ep["trace_id"])
        depths.add((cutoff, len(slots)))
        if label:
            selected.append(label)
            target = label["target_normalized_item_id"]
            if complete_catalog and target not in universe:
                fail("native_target_outside_catalog", ep["trace_id"])
            rank = next((i + 1 for i, item in enumerate(slots) if item == target), None)
        else:
            target, rank = None, None
        records.append({"episode_id": ep["trace_id"], "ranked_items": slots,
            "target_normalized_item_id": target, "rank": rank,
            "rank_state": ("exact" if rank else "right_censored") if label else "unavailable",
            "slice": label["slice"] if label else ep.get("gap_bucket", "overall"),
            "cluster_id": label["cluster_id"] if label else None,
            "invalid_slots": slots.count(None),
            "duplicate_slots": len([x for x in slots if x is not None]) - len({x for x in slots if x is not None})})
    if len(depths) != 1:
        fail("mixed_native_publication_depth", "one fixed cutoff/depth per comparison")
    cutoff, depth = next(iter(depths))
    protocol = {"dataset_split": native["evidence"]["split_id"],
        "split_sha256": native["evidence"]["interaction_sequences_sha256" if rpg else "split_sha256"],
        "target_universe_sha256": native["target_universe"]["sha256"],
        "selection_sha256": canonical_sha256(sorted(selected, key=lambda r: r["episode_id"])) if selected else None,
        "evaluation_cutoff": cutoff, "publication_depth": depth,
        "definition": "single-target macro Hit/NDCG.v1", "invalid_slots": "retain_rank_no_backfill",
        "duplicate_slots": "retain_rank_first_target_occurrence", "censoring": "right_at_publication_depth"}
    metrics = None
    if len(selected) == len(records):
        def metric(rows):
            hit, ndcg = _metric_rows([{"target": {"rank_state": r["rank_state"], "exact_rank": r["rank"]}} for r in rows], cutoff)
            return {"episodes": len(rows), "hit_at_cutoff": hit, "ndcg_at_cutoff": ndcg}
        groups = {}
        for row in records:
            groups.setdefault(row["slice"], []).append(row)
        metrics = {"overall": metric(records), "slices": {name: metric(rows) for name, rows in sorted(groups.items())}}
    return with_content_sha256({"format": "sidscope.native_rank_projection.v1",
        "status": "rank_diagnostics_recomputed" if metrics else "target_labels_unavailable",
        "native_sha256": digest, "selection_file_sha256": hashlib.sha256(selection_bytes).hexdigest() if selection_bytes is not None else None,
        "native_schema": native["schema"], "native_semantics": native["decode_state_kind"],
        "checkpoint_sha256": native["evidence"]["checkpoint_sha256"],
        "protocol": protocol, "records": records, "metrics": metrics,
        "catalog_scope": "complete_exported_catalog" if complete_catalog else "bounded_resolution_subset",
        "unverified": ["native_execution_authenticity", "training_reproducibility", "label_source_authenticity", "per_episode_generation_state", "per_episode_compute"],
        "unavailable": ["user_cluster_identity"] if any(r["cluster_id"] is None for r in records) else []})


def compare_exports(left, right, *, left_selection=None, right_selection=None):
    a = project_export(left, selection=left_selection)
    b = project_export(right, selection=right_selection)
    if a["metrics"] is None or b["metrics"] is None:
        fail("native_target_labels_required", "no target-free metric comparison")
    if a["protocol"] != b["protocol"]:
        fail("native_protocol_mismatch", "split/catalog/selection/cutoff/depth/policies must agree")
    return with_content_sha256({"format": "sidscope.native_rank_comparison.v1",
        "left_sha256": a["content_sha256"], "right_sha256": b["content_sha256"],
        "comparison_kind": "same_export_recomputation" if a["native_sha256"] == b["native_sha256"] else "same_protocol_exports",
        "protocol": a["protocol"], "verification_scope": "supplied_native_ranks_and_labels",
        "overall_delta": {key: b["metrics"]["overall"][key] - a["metrics"]["overall"][key] for key in ("hit_at_cutoff", "ndcg_at_cutoff")},
        "unverified": ["training_seed_robustness", "statistical_significance", "causal_attribution"]})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-fixtures", action="store_true", help="Dependency-free evidence-full packaged regression")
    args = parser.parse_args(argv)
    try:
        if args.check_fixtures:
            if args.input or args.selection or args.output:
                fail("invalid_projection_arguments", "fixture check takes no input/output")
            rpg = ROOT / "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json"
            psid = ROOT / "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json"
            if project_export(rpg)["metrics"]["overall"]["hit_at_cutoff"] != .2:
                fail("packaged_projection_regression", "RPG metric")
            if project_export(psid)["metrics"] is not None:
                fail("packaged_projection_regression", "target-free PSID")
            if compare_exports(rpg, rpg)["comparison_kind"] != "same_export_recomputation":
                fail("packaged_projection_regression", "self comparison boundary")
            try:
                compare_exports(psid, psid)
            except NativeInspectionError as error:
                if error.code != "native_target_labels_required":
                    raise
            else:
                fail("packaged_projection_regression", "missing-label comparison accepted")
            print(json.dumps({"status": "pass", "checks": 4, "scope": "supplied_native_exports_only"}))
            return 0
        if args.input is None or args.output is None:
            fail("invalid_projection_arguments", "input and output required")
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError(args.output)
        result = project_export(args.input, selection=args.selection)
        with args.output.open("x") as handle:
            json.dump(result, handle, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps({"status": result["status"], "content_sha256": result["content_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
