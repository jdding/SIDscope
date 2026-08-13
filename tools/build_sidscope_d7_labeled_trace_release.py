#!/usr/bin/env python3
"""Build the deidentified SIDScope D7 labeled-trace release."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/reproducibility/d7_labeled_trace_rows.csv.gz"
DEFAULT_METADATA = ROOT / "docs/reproducibility/d7_labeled_trace_release.json"

SOURCES = (
    (
        "grid_p5_fold0",
        ROOT / "experiments/v1_evidence_chain/gate20_d7_failure_rich_trace/remote_runs/20260808T113802Z/grid_primary_fold0/g20_labeled_beam_traces.csv",
    ),
    (
        "grid_p5_fold1",
        ROOT / "experiments/v1_evidence_chain/gate20_d7_failure_rich_trace/remote_runs/20260808T113802Z/grid_primary_fold1/g20_labeled_beam_traces.csv",
    ),
    (
        "diger_fold0",
        ROOT / "experiments/v1_evidence_chain/gate20_d7_failure_rich_trace/remote_runs/20260808T113802Z/diger_followup/g20_labeled_beam_traces.csv",
    ),
    (
        "dact_tiger_constrained",
        ROOT / "experiments/v1_evidence_chain/gate21_tiger_d7_robustness/remote_runs/20260809T030241Z/primary/g21_constrained_labels.csv",
    ),
    (
        "dact_tiger_unconstrained",
        ROOT / "experiments/v1_evidence_chain/gate21_tiger_d7_robustness/remote_runs/20260809T030241Z/primary/g21_unconstrained_labels.csv",
    ),
)

RELEASE_FIELDS = (
    "case_id",
    "trace_key",
    "rank",
    "decoding_mode",
    "primary_failure",
    "failure_flags",
    "failure_family",
    "resolved_item_count",
    "target_path_survived",
    "target_item_uniquely_hit",
    "target_missed",
    "generated_length",
    "terminated_early",
    "has_valid_prefix",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_row(case_id: str, trace_key: str, row: dict[str, str]) -> dict[str, str]:
    generated_length = row.get("generated_length") or row.get("path_prefix_len") or ""
    resolved_count = row.get("resolved_item_count_exporter") or ""
    return {
        "case_id": case_id,
        "trace_key": trace_key,
        "rank": row.get("rank", ""),
        "decoding_mode": row.get("decoding_mode", ""),
        "primary_failure": row.get("primary_failure", ""),
        "failure_flags": row.get("failure_flags", ""),
        "failure_family": row.get("failure_family", ""),
        "resolved_item_count": resolved_count,
        "target_path_survived": row.get("target_path_survived", ""),
        "target_item_uniquely_hit": row.get("target_item_uniquely_hit", ""),
        "target_missed": row.get("target_missed", ""),
        "generated_length": generated_length,
        "terminated_early": row.get("terminated_early", ""),
        "has_valid_prefix": row.get("has_valid_prefix", ""),
    }


def build(output: Path, metadata_path: Path) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    case_summaries: dict[str, object] = {}

    with output.open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as gzip_handle:
            with io.TextIOWrapper(gzip_handle, encoding="utf-8", newline="") as text_handle:
                writer = csv.DictWriter(text_handle, fieldnames=RELEASE_FIELDS, lineterminator="\n")
                writer.writeheader()
                for case_id, source in SOURCES:
                    if not source.is_file():
                        raise FileNotFoundError(source)
                    trace_keys: dict[str, str] = {}
                    primary_failures: Counter[str] = Counter()
                    failure_families: Counter[str] = Counter()
                    rows = 0
                    with source.open("r", encoding="utf-8", newline="") as source_handle:
                        reader = csv.DictReader(source_handle)
                        for row in reader:
                            trace_id = row.get("trace_id", "")
                            if trace_id not in trace_keys:
                                trace_keys[trace_id] = f"t{len(trace_keys) + 1:04d}"
                            released = normalized_row(case_id, trace_keys[trace_id], row)
                            writer.writerow(released)
                            primary_failures[released["primary_failure"]] += 1
                            failure_families[released["failure_family"]] += 1
                            rows += 1
                    case_summaries[case_id] = {
                        "source_path": str(source.relative_to(ROOT)),
                        "source_sha256": sha256(source),
                        "rows": rows,
                        "traces": len(trace_keys),
                        "primary_failure_counts": dict(sorted(primary_failures.items())),
                        "failure_family_counts": dict(sorted(failure_families.items())),
                    }

    metadata = {
        "schema": "sidscope.d7_labeled_trace_release.v1",
        "status": "pass",
        "release_path": str(output.relative_to(ROOT)),
        "release_sha256": sha256(output),
        "release_fields": list(RELEASE_FIELDS),
        "rows": sum(int(summary["rows"]) for summary in case_summaries.values()),
        "cases": case_summaries,
        "deidentification": {
            "retained": "case, within-case trace key, beam rank, D7 labels, and path/item outcomes",
            "removed": "user IDs, target/item IDs, SID paths, resolved item IDs, scores, and checkpoints",
            "trace_key": "deterministic within-case ordinal; not reversible to the source trace ID",
        },
        "boundary": "Inspects complete label distributions and within-trace rank patterns without redistributing upstream identities, mappings, raw paths, or model scores.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    args = parser.parse_args()
    metadata = build(args.output.resolve(), args.metadata.resolve())
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
