#!/usr/bin/env python3
"""Inspect a permitted real native export without training or invented labels.

This evidence-full consumer deliberately supports the existing RPG v1 and
PSID/Latte v2 native contracts. Outputs are deterministic, content-addressed
observations, not certification of historical execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.adapters.latte import validate_latte_psid_trained_trace_bundle
from sidinspector.contracts import canonical_json_bytes, with_content_sha256
from sidinspector.contracts.json_io import loads_json, bounded_bytes, JSONInputError
from tools.verify_rpg_trained_trace_bundle import verify as verify_rpg


class NativeInspectionError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(f"{code}: {detail}")


def inspect_export(path: Path, *, max_input_bytes: int | None = None) -> dict:
    try:
        payload = bounded_bytes(path, max_bytes=max_input_bytes)
        doc = loads_json(payload, max_bytes=max_input_bytes)
        if not isinstance(doc, dict):
            raise NativeInspectionError("invalid_native_document", "object required")
        if doc.get("schema") == "sidscope.rpg_trained_trace_bundle.v1":
            verification = verify_rpg(doc)
            k = doc["configuration"]["rank_cutoff"]
            ranks = [next((row["rank"] for row in ep["ranked_items"] if row["normalized_item_id"] == ep["target_normalized_item_id"]), None) for ep in doc["episodes"]]
            metrics = {"status": "recomputed_from_supplied_native_rows", "population_size": len(ranks), "evaluation_cutoff": k, "hit_at_cutoff": sum(r is not None and r <= k for r in ranks) / len(ranks), "ndcg_at_cutoff": sum(1 / math.log2(r + 1) if r is not None and r <= k else 0 for r in ranks) / len(ranks), "definition": "macro single-target Hit/NDCG; unpublished targets count as misses at the cutoff"}
            records = [{"trace_id": ep["trace_id"], "published_target_rank": r, "rank_state": "exact" if r is not None else "right_censored", "next_check": None if r is not None else "Inspect graph candidate coverage before attributing a rank failure."} for ep, r in zip(doc["episodes"], ranks)]
        elif doc.get("schema") == "sidscope.latte_psid_trained_trace_bundle.v2":
            verification = validate_latte_psid_trained_trace_bundle(doc)
            metrics = {"status": "not_verified", "reason": "target_labels_not_exported", "hit_at_cutoff": None, "ndcg_at_cutoff": None, "next_check": "Only compute target metrics after a permitted identity-matched selection is available; never substitute labels."}
            records = [{"trace_id": ep["trace_id"], "evaluation_slots": len(ep.get("evaluation_slots", [])), "invalid_slots": sum(not row["valid"] for row in ep.get("evaluation_slots", [])), "retry_performed": ep["retry_performed"]} for ep in doc["episodes"]]
        else:
            raise NativeInspectionError("unsupported_native_export", str(doc.get("schema")))
    except JSONInputError as error:
        code = "native_input_budget_exceeded" if error.code == "json_size_exceeded" else error.code
        raise NativeInspectionError(code, error.detail) from error
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        if isinstance(error, NativeInspectionError):
            raise
        raise NativeInspectionError(getattr(error, "code", "native_verification_failed"), str(error)) from error
    return with_content_sha256({"format": "sidscope.native_inspection.v1", "status": "pass", "input_sha256": hashlib.sha256(payload).hexdigest(), "native_schema": doc["schema"], "native_semantics": doc["decode_state_kind"], "verification_scope": "supplied_native_export_consistency", "native_verification": verification, "metrics": metrics, "records": records, "unverified_claims": ["native_execution_authenticity", "historical_training", "model_quality_generalization"], "retraining_performed": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-input-bytes", type=int, default=None, help="Optional local file budget; no default size cap.")
    args = parser.parse_args()
    try:
        result = inspect_export(args.input, max_input_bytes=args.max_input_bytes)
        with args.output.open("xb") as handle:
            handle.write(canonical_json_bytes(result) + b"\n")
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps({"status": "pass", "content_sha256": result["content_sha256"], "metrics": result["metrics"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
