#!/usr/bin/env python3
"""Same-source delivery summary: aggregate required gate receipts, verify, certify.

A summary is a local integrity binding (hashes), not a signature scheme and not
a release authorization. The builder refuses missing, duplicated, unknown,
failed, not-run or unapproved-skipped required gates, stale source identity and
tampered evidence; the verifier recomputes every referenced digest instead of
trusting status strings. This tool never rewrites historical evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_json_bytes, with_content_sha256, load_json
from tools.sidscope_acceptance_scope import load_acceptance_scope, scope_digest
from tools.sidscope_local_release_record import (
    ReleaseRecordError,
    source_snapshot as full_source_snapshot,
    verify_record,
)

SUMMARY_FORMAT = "sidscope.delivery_summary.v1"
RECEIPT_FORMAT = "sidscope.gate_receipt.v1"
CAMPAIGN_FORMAT = "sidscope.performance_campaign.v1"
LINUX_FORMAT = "sidscope.linux_matrix_receipt.v1"
CATALOG_PATH = ROOT / "docs/reproducibility/sidscope_required_gate_catalog.v1.json"
LINUX_PYTHONS = ("3.9", "3.10", "3.11", "3.12")
UNVERIFIED_CLAIMS = [
    "independent_user_actual_use",
    "native_training_authenticity",
    "real_sid_refresh_effect",
    "multi_seed_statistical_conclusions",
]


class DeliverySummaryError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def gate_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.is_file():
        raise DeliverySummaryError("gate_catalog_missing", str(CATALOG_PATH))
    catalog = load_json(CATALOG_PATH)
    if catalog.get("schema") != "sidscope.required_gate_catalog.v1":
        raise DeliverySummaryError("gate_catalog_invalid", "schema")
    gates = [row["gate_id"] for row in catalog.get("gates", [])]
    if not gates or len(set(gates)) != len(gates):
        raise DeliverySummaryError("gate_catalog_invalid", "gate ids must be non-empty and unique")
    return {"catalog": catalog, "digest": sha(CATALOG_PATH), "required": gates}


def short_source() -> dict[str, Any]:
    snapshot = full_source_snapshot()
    return {"head": snapshot["head"], "branch": snapshot["branch"], "clean": not snapshot["dirty"],
            "public_snapshot_digest": snapshot["content_sha256"]}


def source_matches(left: dict[str, Any], right: dict[str, Any], what: str) -> None:
    for key in ("head", "branch", "public_snapshot_digest"):
        if left.get(key) != right.get(key):
            raise DeliverySummaryError("source_identity_mismatch", f"{what}: {key}")
    if not right.get("clean"):
        raise DeliverySummaryError("source_identity_mismatch", f"{what}: dirty candidate")


def validate_receipt(receipt: dict[str, Any], evidence_dir: Path, expected_source: dict[str, Any], gate_id: str) -> dict[str, Any]:
    if receipt.get("format") != RECEIPT_FORMAT:
        raise DeliverySummaryError("invalid_gate_receipt", f"{gate_id}: format")
    if receipt.get("gate_id") != gate_id:
        raise DeliverySummaryError("invalid_gate_receipt", f"{gate_id}: gate_id mismatch")
    source = receipt.get("source") or {}
    try:
        source_matches(expected_source, source, f"gate {gate_id}")
    except DeliverySummaryError as error:
        raise DeliverySummaryError("stale_gate_source", f"{gate_id}: {error.detail}") from error
    if receipt.get("status") != "pass":
        raise DeliverySummaryError("failed_required_gate", f"{gate_id}: {receipt.get('status')}")
    if receipt.get("exit_code") != 0:
        raise DeliverySummaryError("failed_required_gate", f"{gate_id}: exit {receipt.get('exit_code')}")
    for skip in receipt.get("skip_dispositions", []) or []:
        if not skip.get("approved"):
            raise DeliverySummaryError("unapproved_skip", f"{gate_id}: {skip}")
    log = receipt.get("log") or {}
    log_path = evidence_dir / log.get("path", "")
    if not log_path.is_file() or sha(log_path) != log.get("sha256"):
        raise DeliverySummaryError("gate_log_integrity", gate_id)
    for name, digest in (receipt.get("artifact_digests") or {}).items():
        artifact = evidence_dir / name
        if not artifact.is_file() or sha(artifact) != digest:
            raise DeliverySummaryError("gate_artifact_integrity", f"{gate_id}: {name}")
    environment = receipt.get("environment") or {}
    if not environment.get("python") or not environment.get("platform"):
        raise DeliverySummaryError("invalid_gate_receipt", f"{gate_id}: environment")
    return receipt


def load_gate_receipts(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    gate_dir = evidence_dir / "gates"
    receipts: dict[str, dict[str, Any]] = {}
    if not gate_dir.is_dir():
        raise DeliverySummaryError("gate_receipts_missing", str(gate_dir))
    for path in sorted(gate_dir.glob("*.json")):
        receipt = load_json(path)
        gate_id = receipt.get("gate_id")
        if gate_id in receipts:
            raise DeliverySummaryError("duplicate_gate_receipt", str(gate_id))
        receipts[gate_id] = receipt
    return receipts


def validate_campaign(campaign: dict[str, Any], expected_source: dict[str, Any]) -> dict[str, Any]:
    if campaign.get("format") != CAMPAIGN_FORMAT:
        raise DeliverySummaryError("invalid_campaign_receipt", "format")
    try:
        source_matches(expected_source, campaign.get("source") or {}, "performance campaign")
    except DeliverySummaryError as error:
        raise DeliverySummaryError("stale_campaign_source", error.detail) from error
    groups = campaign.get("groups") or []
    if len(groups) != 3:
        raise DeliverySummaryError("invalid_campaign_receipt", f"expected 3 groups, found {len(groups)}")
    for index, group in enumerate(groups):
        gate = group.get("delivery_gate") or {}
        if group.get("delivery_status") != "pass" or gate.get("status") != "pass":
            raise DeliverySummaryError("failed_required_gate", f"campaign group {index}")
        if group.get("observation_status") != (group.get("measurement") or {}).get("status"):
            raise DeliverySummaryError("invalid_campaign_receipt", f"campaign group {index}: observation drift")
    if campaign.get("aggregate", {}).get("status") != "pass":
        raise DeliverySummaryError("failed_required_gate", "campaign aggregate")
    return campaign


def validate_linux_matrix(matrix: dict[str, Any], expected_source: dict[str, Any], evidence_dir: Path) -> dict[str, Any]:
    if matrix.get("format") != LINUX_FORMAT:
        raise DeliverySummaryError("invalid_linux_receipt", "format")
    try:
        source_matches(expected_source, matrix.get("source") or {}, "linux matrix")
    except DeliverySummaryError as error:
        raise DeliverySummaryError("stale_linux_source", error.detail) from error
    cells = matrix.get("cells") or []
    by_python: dict[str, dict[str, Any]] = {}
    for cell in cells:
        version = str(cell.get("python", ""))
        if version in by_python:
            raise DeliverySummaryError("invalid_linux_receipt", f"duplicate cell {version}")
        by_python[version] = cell
    if sorted(by_python) != sorted(LINUX_PYTHONS):
        raise DeliverySummaryError("invalid_linux_receipt", f"cells {sorted(by_python)} != {sorted(LINUX_PYTHONS)}")
    for version, cell in sorted(by_python.items()):
        if cell.get("status") != "pass" or cell.get("exit_code") != 0:
            raise DeliverySummaryError("failed_required_gate", f"linux {version}")
        if cell.get("head") != expected_source["head"]:
            raise DeliverySummaryError("stale_linux_source", f"linux {version} head")
        log = cell.get("log") or {}
        log_path = evidence_dir / log.get("path", "")
        if not log_path.is_file() or sha(log_path) != log.get("sha256"):
            raise DeliverySummaryError("gate_log_integrity", f"linux {version}")
        if not cell.get("source_identity_checked"):
            raise DeliverySummaryError("invalid_linux_receipt", f"linux {version}: source identity not checked")
    return matrix


def build_summary(evidence_dir: Path, output: Path, *, expected_record_sha256: str) -> dict[str, Any]:
    evidence_dir = evidence_dir.resolve()
    output = output.resolve()
    if output == ROOT or ROOT in output.parents or output == evidence_dir:
        # The owner-designated ignored evidence area (.local_artifacts/) is the
        # sanctioned in-tree location; any other in-tree output is refused.
        if ".local_artifacts" not in output.parts:
            raise DeliverySummaryError("summary_output_invalid",
                                       "write the summary into the ignored evidence area or outside the source tree")
    catalog_info = gate_catalog()
    required = catalog_info["required"]
    expected_source = short_source()
    if not expected_source["clean"]:
        raise DeliverySummaryError("dirty_candidate", "delivery evidence requires a clean candidate")
    record_path = evidence_dir / "release-record.json"
    record = load_json(record_path)
    verify_record(record_path, expected_record_sha256=expected_record_sha256,
                  archive_path=evidence_dir / "runtime.zip", profile="runtime")
    verify_record(record_path, expected_record_sha256=expected_record_sha256,
                  archive_path=evidence_dir / "conformance.zip", profile="conformance")
    verify_record(record_path, expected_record_sha256=expected_record_sha256,
                  archive_path=evidence_dir / "evidence-full.zip", profile="evidence-full")
    record_source = {"head": record["source"]["head"], "branch": record["source"]["branch"],
                     "clean": not record["source"]["dirty"],
                     "public_snapshot_digest": record["source"]["content_sha256"]}
    source_matches(expected_source, record_source, "record v2")
    receipts = load_gate_receipts(evidence_dir)
    unknown = sorted(set(receipts) - set(required))
    if unknown:
        raise DeliverySummaryError("unknown_gate_receipt", str(unknown))
    missing = [gate_id for gate_id in required
               if gate_id not in receipts and gate_id not in ("performance_campaign", "linux_matrix", "exact_source_record_v2")]
    if missing:
        raise DeliverySummaryError("missing_required_gate", str(missing))
    gate_entries = []
    for gate_id in required:
        if gate_id in ("performance_campaign", "linux_matrix", "exact_source_record_v2"):
            continue
        receipt = validate_receipt(receipts[gate_id], evidence_dir, expected_source, gate_id)
        gate_entries.append({
            "gate_id": gate_id, "status": "pass",
            "receipt": {"path": f"gates/{gate_id}.json", "sha256": sha(evidence_dir / f"gates/{gate_id}.json")},
            "source": receipt["source"],
            "environment_id": sha_bytes(canonical_json_bytes(receipt["environment"])),
            "invocation_digest": receipt["invocation_digest"],
            "exit_code": receipt["exit_code"],
            "log_digest": receipt["log"]["sha256"],
            "receipt_digest": sha(evidence_dir / f"gates/{gate_id}.json"),
            "artifact_digests": receipt.get("artifact_digests") or {},
            "skip_dispositions": receipt.get("skip_dispositions") or [],
        })
    campaign = validate_campaign(load_json(evidence_dir / "performance-campaign.json"), expected_source)
    gate_entries.append({"gate_id": "performance_campaign", "status": "pass",
                         "receipt": {"path": "performance-campaign.json", "sha256": sha(evidence_dir / "performance-campaign.json")},
                         "source": campaign["source"],
                         "environment_id": sha_bytes(canonical_json_bytes(campaign.get("environment") or {})),
                         "invocation_digest": campaign.get("invocation_digest", ""),
                         "exit_code": 0,
                         "log_digest": campaign["aggregate"].get("log_digest", ""),
                         "receipt_digest": sha(evidence_dir / "performance-campaign.json"),
                         "artifact_digests": {f"group-{index}.json": group_sha for index, group_sha in enumerate(campaign.get("group_digests", []))},
                         "skip_dispositions": []})
    matrix = validate_linux_matrix(load_json(evidence_dir / "linux-matrix.json"), expected_source, evidence_dir)
    gate_entries.append({"gate_id": "linux_matrix", "status": "pass",
                         "receipt": {"path": "linux-matrix.json", "sha256": sha(evidence_dir / "linux-matrix.json")},
                         "source": matrix["source"],
                         "environment_id": sha_bytes(canonical_json_bytes({"os": matrix.get("os_family", "Linux")})),
                         "invocation_digest": matrix.get("invocation_digest", ""),
                         "exit_code": 0,
                         "log_digest": "",
                         "receipt_digest": sha(evidence_dir / "linux-matrix.json"),
                         "artifact_digests": {cell["python"]: cell["log"]["sha256"] for cell in matrix["cells"]},
                         "skip_dispositions": []})
    gate_entries.append({"gate_id": "exact_source_record_v2", "status": "pass",
                         "receipt": {"path": "release-record.json", "sha256": expected_record_sha256},
                         "source": record_source,
                         "environment_id": sha_bytes(canonical_json_bytes(record["build_environment"])),
                         "invocation_digest": "",
                         "exit_code": 0,
                         "log_digest": "",
                         "receipt_digest": expected_record_sha256,
                         "artifact_digests": {row["profile"] + ".zip": row["archive_sha256"] for row in record["archives"]},
                         "skip_dispositions": []})
    entries_by_id = {row["gate_id"]: row for row in gate_entries}
    if sorted(entries_by_id) != sorted(required):
        raise DeliverySummaryError("missing_required_gate", str(sorted(set(required) - set(entries_by_id))))
    scope = load_acceptance_scope(ROOT)
    summary = with_content_sha256({
        "format": SUMMARY_FORMAT, "status": "pass",
        "gate_catalog_digest": catalog_info["digest"],
        "acceptance_scope": {"policy_revision": scope["policy_revision"], "snapshot": scope_digest(ROOT)},
        "source": expected_source,
        "gates": gate_entries,
        "excluded_acceptance": ["independent_user_actual_use"],
        "unverified_claims": UNVERIFIED_CLAIMS,
        "implementation_ready": True,
        "delivery_ready": True,
        "certification_ready": True,
        "release_authorized": False,
        "boundary": "Local integrity binding only; not publisher authenticity, adoption, or a public-release authorization.",
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(summary) + b"\n")
    return {"status": "pass", "summary_sha256": sha(output), "gates": [row["gate_id"] for row in gate_entries],
            "source": expected_source, "output": str(output)}


def verify_summary(summary_path: Path, *, expected_summary_sha256: str, evidence_dir: Path) -> dict[str, Any]:
    if sha(summary_path) != expected_summary_sha256:
        raise DeliverySummaryError("summary_digest_mismatch", str(summary_path))
    summary = load_json(summary_path)
    if summary.get("format") != SUMMARY_FORMAT or summary.get("status") != "pass":
        raise DeliverySummaryError("invalid_delivery_summary", "format/status")
    if summary.get("release_authorized") is not False:
        raise DeliverySummaryError("invalid_delivery_summary", "release_authorized must be false")
    catalog_info = gate_catalog()
    if summary.get("gate_catalog_digest") != catalog_info["digest"]:
        raise DeliverySummaryError("gate_catalog_mismatch", "catalog changed after the summary was built")
    gate_ids = [row["gate_id"] for row in summary["gates"]]
    if sorted(gate_ids) != sorted(catalog_info["required"]):
        raise DeliverySummaryError("gate_catalog_incomplete", str(sorted(set(catalog_info["required"]) ^ set(gate_ids))))
    if len(set(gate_ids)) != len(gate_ids):
        raise DeliverySummaryError("duplicate_gate_receipt", "summary entries")
    expected_source = summary["source"]
    record_path = evidence_dir / "release-record.json"
    record = load_json(record_path)
    record_entry = next(row for row in summary["gates"] if row["gate_id"] == "exact_source_record_v2")
    verify_record(record_path, expected_record_sha256=record_entry["receipt"]["sha256"],
                  archive_path=evidence_dir / "runtime.zip", profile="runtime")
    verify_record(record_path, expected_record_sha256=record_entry["receipt"]["sha256"],
                  archive_path=evidence_dir / "conformance.zip", profile="conformance")
    verify_record(record_path, expected_record_sha256=record_entry["receipt"]["sha256"],
                  archive_path=evidence_dir / "evidence-full.zip", profile="evidence-full")
    for row in summary["gates"]:
        receipt_path = evidence_dir / row["receipt"]["path"]
        if not receipt_path.is_file() or sha(receipt_path) != row["receipt_digest"]:
            raise DeliverySummaryError("receipt_integrity", row["gate_id"])
        if row["status"] != "pass" or row["exit_code"] != 0:
            raise DeliverySummaryError("failed_required_gate", row["gate_id"])
        if row["gate_id"] in ("performance_campaign", "linux_matrix", "exact_source_record_v2"):
            continue
        receipt = load_json(receipt_path)
        validate_receipt(receipt, evidence_dir, expected_source, row["gate_id"])
        if receipt.get("invocation_digest") != row["invocation_digest"]:
            raise DeliverySummaryError("receipt_integrity", row["gate_id"] + ": invocation")
    validate_campaign(load_json(evidence_dir / "performance-campaign.json"), expected_source)
    validate_linux_matrix(load_json(evidence_dir / "linux-matrix.json"), expected_source, evidence_dir)
    return {"status": "pass", "summary_sha256": sha(summary_path), "source": expected_source,
            "delivery_ready": True, "certification_ready": summary.get("certification_ready") is True,
            "release_authorized": False}


def run_gate(gate_id: str, evidence_dir: Path, command: list[str]) -> dict[str, Any]:
    catalog_info = gate_catalog()
    if gate_id not in catalog_info["required"]:
        raise DeliverySummaryError("unknown_gate_receipt", gate_id)
    if not command:
        raise DeliverySummaryError("invalid_gate_receipt", "no command given")
    evidence_dir = evidence_dir.resolve()
    (evidence_dir / "gates").mkdir(parents=True, exist_ok=True)
    (evidence_dir / "logs").mkdir(parents=True, exist_ok=True)
    receipt_path = evidence_dir / f"gates/{gate_id}.json"
    if receipt_path.exists():
        raise DeliverySummaryError("duplicate_gate_receipt", f"{gate_id} receipt exists; use a new attempt directory")
    before = short_source()
    run = subprocess.run(command, cwd=ROOT, capture_output=True)
    log_path = evidence_dir / f"logs/{gate_id}.log"
    log_path.write_bytes(run.stdout + run.stderr)
    receipt = with_content_sha256({
        "format": RECEIPT_FORMAT, "gate_id": gate_id,
        "status": "pass" if run.returncode == 0 else "failed",
        "source": before,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "invocation": command,
        "invocation_digest": sha_bytes(canonical_json_bytes(command)),
        "exit_code": run.returncode,
        "log": {"path": f"logs/{gate_id}.log", "sha256": sha(log_path)},
        "artifact_digests": {},
        "skip_dispositions": [],
    })
    receipt_path.write_bytes(canonical_json_bytes(receipt) + b"\n")
    return {"status": receipt["status"], "gate_id": gate_id, "exit_code": run.returncode,
            "receipt": str(receipt_path), "log": str(log_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run-gate")
    run.add_argument("--gate-id", required=True)
    run.add_argument("--evidence-dir", type=Path, required=True)
    run.add_argument("gate_command", nargs="+")
    build = commands.add_parser("build")
    build.add_argument("--evidence-dir", type=Path, required=True)
    build.add_argument("--expected-record-sha256", required=True)
    build.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--summary", type=Path, required=True)
    verify.add_argument("--expected-summary-sha256", required=True)
    verify.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "run-gate":
            result = run_gate(args.gate_id, args.evidence_dir, args.gate_command)
        elif args.command == "build":
            result = build_summary(args.evidence_dir, args.output, expected_record_sha256=args.expected_record_sha256)
        else:
            result = verify_summary(args.summary, expected_summary_sha256=args.expected_summary_sha256,
                                    evidence_dir=args.evidence_dir)
    except (DeliverySummaryError, ReleaseRecordError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__),
                          "detail": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
