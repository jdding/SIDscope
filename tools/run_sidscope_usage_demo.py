#!/usr/bin/env python3
"""Run the SIDScope G14 resource-usage demonstration.

The demo is intentionally bounded: it uses only compact release snapshots and
shows how a reviewer or researcher can turn artifact diagnostics into a
triage decision. It is not a downstream recommendation-quality experiment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "experiments" / "v1_evidence_chain" / "gate14_usage_demo"
DEFAULT_RESULT_JSON = DEFAULT_OUTPUT_DIR / "GATE14_RESULT.json"
DEFAULT_DECISION_CSV = ROOT / "docs" / "reproducibility" / "g14_usage_demo_decisions.csv"
DEFAULT_SUMMARY_JSON = ROOT / "docs" / "reproducibility" / "g14_usage_demo_summary.json"
DEFAULT_WALKTHROUGH_MD = ROOT / "docs" / "SIDSCOPE_USAGE_DEMO.md"


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def load_sources() -> dict[str, pd.DataFrame]:
    return {
        "table1": pd.read_csv(require_file(ROOT / "docs" / "reproducibility" / "table1_evidence_catalog.csv")),
        "table2": pd.read_csv(require_file(ROOT / "docs" / "reproducibility" / "table2_musical_diagnostic.csv")),
        "official": pd.read_csv(
            require_file(ROOT / "docs" / "reproducibility" / "official_adapter_metrics_snapshot.csv")
        ),
        "extensions": pd.read_csv(require_file(ROOT / "docs" / "reproducibility" / "extension_checks_snapshot.csv")),
    }


def classify_row(row: pd.Series) -> dict[str, str]:
    artifact = str(row["artifact"])
    group = str(row.get("group", ""))
    d2 = float(row["d2_aliasing_rate"])
    d3 = float(row["d3_l1_weighted"])
    tail_unique = float(row["d4_tail_unique_ratio"])
    items = int(row["items"])
    unique_sids = int(row["unique_sids"])
    unique_ratio = unique_sids / max(items, 1)

    risk_flags: list[str] = []
    if d2 >= 0.90:
        risk_flags.append("severe_full_code_aliasing")
    elif d2 >= 0.50:
        risk_flags.append("high_full_code_aliasing")
    elif d2 >= 0.10:
        risk_flags.append("moderate_full_code_aliasing")
    if unique_ratio < 0.50:
        risk_flags.append("low_addressability")
    if tail_unique < 0.80:
        risk_flags.append("tail_addressability_loss")
    if d3 < 0.08:
        risk_flags.append("weak_prefix_exposure_proxy")
    elif d3 >= 0.10:
        risk_flags.append("usable_prefix_exposure_proxy")

    if "Hash-collide" in artifact or d2 >= 0.90 or unique_ratio < 0.50:
        decision = "stress_only_exclude_from_named_coverage"
        question = "Should this artifact be used as a named method row?"
        answer = "No. Keep as a stress/control row and do not train expensive generators on it."
    elif group == "Controls":
        decision = "diagnostic_control_not_method_coverage"
        question = "Should this control row be promoted as method coverage?"
        answer = "No. Use it to interpret diagnostic behavior, not as a named artifact candidate."
    elif d2 >= 0.50 or tail_unique < 0.80:
        decision = "repair_or_replace_before_training"
        question = "Should this artifact enter downstream training as-is?"
        answer = "No. Addressability/collision risk is too high; repair or replace before training."
    elif d2 <= 0.05 and d3 >= 0.10 and tail_unique >= 0.98:
        decision = "candidate_for_training_or_comparison"
        question = "Is this a reasonable artifact to promote to training/comparison?"
        answer = "Yes, with normal provenance checks and task-specific validation."
    elif d2 <= 0.15 and unique_ratio >= 0.85:
        decision = "intake_pass_monitor_exposure"
        question = "Can this artifact be kept in the matrix?"
        answer = "Yes, but monitor candidate-exposure and refresh-specific diagnostics."
    else:
        decision = "manual_review_before_claim"
        question = "Can this artifact support a paper-facing claim without inspection?"
        answer = "Not yet. Inspect provenance, exposure, and addressability before promotion."

    return {
        "decision": decision,
        "question_answered": question,
        "walkthrough_answer": answer,
        "risk_flags": ";".join(risk_flags) if risk_flags else "none",
    }


def build_decision_table(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    table2 = sources["table2"].copy()
    table2["artifact_source"] = "paper_diagnostic_profile"
    table2["release_boundary"] = "tracked_snapshot_raw_artifacts_not_shipped"

    official = sources["official"].copy()
    official = official.rename(
        columns={
            "adapter": "artifact",
            "d3_l1_weighted": "d3_l1_weighted",
            "d5_active_prefix_counts": "d5_active_prefix_counts",
        }
    )
    official["group"] = "Official upstream adapters"
    official["seeds"] = 1
    official["artifact_source"] = "official_adapter_metrics_snapshot"
    official["release_boundary"] = official["release_status"]

    common = [
        "artifact",
        "group",
        "items",
        "seeds",
        "unique_sids",
        "d2_aliasing_rate",
        "d3_l1_weighted",
        "d4_tail_unique_ratio",
        "d5_active_prefix_counts",
        "source_evidence",
        "artifact_source",
        "release_boundary",
    ]
    combined = pd.concat([table2[common], official[common]], ignore_index=True)

    decisions = combined.apply(classify_row, axis=1, result_type="expand")
    combined = pd.concat([combined, decisions], axis=1)
    combined["usage_demo_role"] = combined["decision"].map(
        {
            "candidate_for_training_or_comparison": "promote_candidate",
            "intake_pass_monitor_exposure": "retain_with_monitoring",
            "manual_review_before_claim": "inspect",
            "repair_or_replace_before_training": "block_or_repair",
            "stress_only_exclude_from_named_coverage": "stress_control",
            "diagnostic_control_not_method_coverage": "diagnostic_control",
        }
    )
    return combined.sort_values(["usage_demo_role", "artifact"]).reset_index(drop=True)


def summarize(decisions: pd.DataFrame) -> dict[str, Any]:
    counts = decisions["decision"].value_counts().sort_index().to_dict()
    promote = decisions[decisions["usage_demo_role"] == "promote_candidate"]["artifact"].tolist()
    blocked = decisions[decisions["usage_demo_role"].isin(["block_or_repair", "stress_control"])]["artifact"].tolist()
    inspected = decisions[decisions["usage_demo_role"] == "inspect"]["artifact"].tolist()
    return {
        "artifact_rows": int(len(decisions)),
        "decision_counts": {key: int(value) for key, value in counts.items()},
        "promote_candidates": promote,
        "blocked_or_stress_only": blocked,
        "manual_review": inspected,
        "questions_answered": [
            "Which artifact rows are safe to promote to expensive training/comparison?",
            "Which rows should remain stress/control evidence rather than named method coverage?",
            "Which rows need provenance or exposure monitoring before paper-facing use?",
        ],
    }


def write_walkthrough(path: Path, decisions: pd.DataFrame, summary: dict[str, Any]) -> None:
    promote = ", ".join(summary["promote_candidates"]) or "none"
    blocked = ", ".join(summary["blocked_or_stress_only"]) or "none"
    manual = ", ".join(summary["manual_review"]) or "none"
    lines = [
        "# SIDScope Usage Demo",
        "",
        "Status: G14 resource-use walkthrough",
        "Last updated: 2026-06-20",
        "",
        "This demo shows the intended resource use pattern: a researcher inspects",
        "compact SID artifact diagnostics, separates promotable artifacts from",
        "stress/control rows, and records what should or should not move to more",
        "expensive downstream training. It is a reproducible usage demonstration,",
        "not a claim that SIDScope predicts final recommender quality.",
        "",
        "## Inputs",
        "",
        "- `docs/reproducibility/table2_musical_diagnostic.csv`",
        "- `docs/reproducibility/official_adapter_metrics_snapshot.csv`",
        "- `docs/reproducibility/table1_evidence_catalog.csv`",
        "- `docs/reproducibility/extension_checks_snapshot.csv`",
        "",
        "## Walkthrough Outcome",
        "",
        f"- Artifact rows inspected: `{summary['artifact_rows']}`",
        f"- Promote candidates: {promote}",
        f"- Blocked or stress-only rows: {blocked}",
        f"- Manual-review rows: {manual}",
        "",
        "## Decision Table",
        "",
        "| Artifact | Decision | Question Answered | Answer | Risk Flags |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, row in decisions.iterrows():
        lines.append(
            "| {artifact} | {decision} | {question} | {answer} | {flags} |".format(
                artifact=str(row["artifact"]).replace("|", "/"),
                decision=str(row["decision"]),
                question=str(row["question_answered"]),
                answer=str(row["walkthrough_answer"]),
                flags=str(row["risk_flags"]),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "The demo uses deterministic thresholds only to illustrate resource",
            "operation. The thresholds are not universal acceptance rules, and the",
            "output should be read as a reproducible triage walkthrough rather than",
            "a downstream performance result.",
            "",
            "Regenerate with:",
            "",
            "```bash",
            "python3 tools/run_sidscope_usage_demo.py",
            "```",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_usage_demo(output_dir: Path, decision_csv: Path, summary_json: Path, walkthrough_md: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = load_sources()
    decisions = build_decision_table(sources)
    summary = summarize(decisions)

    decision_csv.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(decision_csv, index=False)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_walkthrough(walkthrough_md, decisions, summary)

    full_decision_csv = output_dir / "g14_usage_demo_decisions.csv"
    full_summary_json = output_dir / "g14_usage_demo_summary.json"
    decisions.to_csv(full_decision_csv, index=False)
    full_summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    status = "pass"
    if not summary["promote_candidates"] or not summary["blocked_or_stress_only"]:
        status = "fail"

    return {
        "schema": "sidscope.g14_usage_demo.v1",
        "run_id": "R745",
        "status": status,
        "gpu_required": False,
        "output_dir": str(output_dir),
        "public_outputs": {
            "decision_csv": str(decision_csv.relative_to(ROOT)),
            "summary_json": str(summary_json.relative_to(ROOT)),
            "walkthrough_md": str(walkthrough_md.relative_to(ROOT)),
        },
        "local_outputs": {
            "decision_csv": str(full_decision_csv.relative_to(ROOT)),
            "summary_json": str(full_summary_json.relative_to(ROOT)),
        },
        "summary": summary,
        "source_snapshots": [str((ROOT / "docs" / "reproducibility" / name).relative_to(ROOT)) for name in (
            "table1_evidence_catalog.csv",
            "table2_musical_diagnostic.csv",
            "official_adapter_metrics_snapshot.csv",
            "extension_checks_snapshot.csv",
        )],
        "boundary": (
            "G14 is a resource-use walkthrough over compact snapshots. It supports "
            "resource usability and decision-trace claims, not downstream model-quality claims."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SIDScope G14 usage-demo walkthrough.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--decision-csv", type=Path, default=DEFAULT_DECISION_CSV)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--walkthrough-md", type=Path, default=DEFAULT_WALKTHROUGH_MD)
    parser.add_argument("--result-json", type=Path, default=DEFAULT_RESULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_usage_demo(
        output_dir=args.output_dir.resolve(),
        decision_csv=args.decision_csv.resolve(),
        summary_json=args.summary_json.resolve(),
        walkthrough_md=args.walkthrough_md.resolve(),
    )
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
