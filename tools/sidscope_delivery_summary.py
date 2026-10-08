#!/usr/bin/env python3
"""Same-source delivery summary: aggregate required gate receipts, verify, certify.

A summary is a local integrity binding (hashes), not a signature scheme and not
a release authorization. The builder refuses missing, duplicated, unknown,
failed, not-run or unapproved-skipped required gates, stale source identity and
tampered evidence; the verifier recomputes every referenced digest, re-runs
record v2 verification with recursive sub-evidence checks, re-derives the
performance verdict from the recorded measurements and the frozen baseline, and
checks the declared platform scope — it never trusts status strings.
Linux support is deferred in catalog v2; its standalone validator is retained.
Receipt gates are bound to the catalog invocations. Outputs are
created exclusively; existing files are never overwritten. This tool never
rewrites historical evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_json_bytes, with_content_sha256, load_json
from tools.check_sidscope_current_performance import classify, delivery_gate as compute_delivery_gate
from tools.sidscope_acceptance_scope import load_acceptance_scope, scope_digest
from tools.sidscope_local_release_record import (
    ReleaseRecordError,
    source_snapshot as full_source_snapshot,
    verify_record,
)

SUMMARY_FORMAT = "sidscope.delivery_summary.v2"
RECEIPT_FORMAT = "sidscope.gate_receipt.v1"
CAMPAIGN_FORMAT = "sidscope.performance_campaign.v1"
LINUX_FORMAT = "sidscope.linux_matrix_receipt.v1"
CATALOG_PATH = ROOT / "docs/reproducibility/sidscope_required_gate_catalog.v2.json"
REQUIRED_GATE_BINDINGS = {
    "full_cpu_test_suite": "catalog_command",
    "release_metadata_verifier": "catalog_command",
    "architecture_inventory_verifier": "catalog_command",
    "sdlc_acceptance_verifier": "catalog_command",
    "sdlc_hardening_engineering_ready": "catalog_command",
    "release_profiles_verifier": "catalog_command",
    "candidate_engineering_ready_clean": "catalog_command",
    "resource_package_verifier": "catalog_command",
    "performance_campaign": "campaign_receipt",
    "exact_source_record_v2": "record_v2",
}
PLATFORM_SUPPORT = {"accepted": "macOS arm64 / CPython 3.9.6",
                    "linux": "unsupported_in_2_0", "windows": "unverified"}
BASELINE_PATH = ROOT / "docs/reproducibility/sidscope_1_2_cli_cpu_baseline.json"
LINUX_PYTHONS = ("3.9", "3.10", "3.11", "3.12")
LINUX_REQUIRED_STEPS = ("pytest", "metadata", "architecture", "sdlc_acceptance",
                        "sdlc_hardening", "profiles", "resource")
UNVERIFIED_CLAIMS = [
    "independent_user_actual_use",
    "native_training_authenticity",
    "real_sid_refresh_effect",
    "multi_seed_statistical_conclusions",
    "linux_python_3_9_to_3_12_support",
]
PYTEST_SUMMARY = re.compile(r"(\d+) passed(?:,\s*(\d+) skipped)?(?:,\s*(\d+) deselected)?")


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
    if catalog.get("schema") != "sidscope.required_gate_catalog.v2":
        raise DeliverySummaryError("gate_catalog_invalid", "schema")
    gates = [row["gate_id"] for row in catalog.get("gates", [])]
    if not gates or len(set(gates)) != len(gates):
        raise DeliverySummaryError("gate_catalog_invalid", "gate ids must be non-empty and unique")
    by_id = {row["gate_id"]: row for row in catalog["gates"]}
    if {key: row.get("binding") for key, row in by_id.items()} != REQUIRED_GATE_BINDINGS:
        raise DeliverySummaryError("gate_catalog_invalid", "the ten required gates and bindings are frozen")
    if (catalog.get("deferred_gates") != ["linux_matrix"]
            or catalog.get("platform_support") != PLATFORM_SUPPORT):
        raise DeliverySummaryError("gate_catalog_invalid", "platform/deferred scope differs from ADR-0027")
    decision = catalog.get("decision") or {}
    if (decision.get("decided_by") != "project_owner" or decision.get("date") != "2026-10-08"
            or decision.get("adr") != "docs/adr/0027-defer-linux-support-beyond-2-0.md"
            or not (ROOT / decision["adr"]).is_file()):
        raise DeliverySummaryError("gate_catalog_invalid", "ADR-0027 owner decision required")
    for gate_id, row in by_id.items():
        if row.get("binding") == "catalog_command":
            invocation = row.get("invocation")
            if not isinstance(invocation, list) or not invocation or not all(isinstance(part, str) for part in invocation):
                raise DeliverySummaryError("gate_catalog_invalid", f"{gate_id}: invocation")
    return {"catalog": catalog, "digest": sha(CATALOG_PATH), "required": gates, "by_id": by_id}


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


def _exclusive_write(path: Path, payload: bytes, *, code: str) -> None:
    # Check the original path (never a resolved one): a symlink — including a
    # dangling one — must be refused without following or creating its target.
    path = Path(path)
    if path.is_symlink() or path.exists():
        raise DeliverySummaryError(code, f"{path} already exists; use a new attempt path")
    resolved_parent = path.resolve().parent
    if ROOT in [resolved_parent, *resolved_parent.parents] and ".local_artifacts" not in path.parts:
        raise DeliverySummaryError(code, "write under the ignored evidence area or outside the source tree")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = path.open("xb")
    with descriptor:
        descriptor.write(payload)


def validate_receipt(receipt: dict[str, Any], evidence_dir: Path, expected_source: dict[str, Any], gate_id: str,
                     *, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
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
    # R01: the executed argv must be exactly the catalog invocation for this
    # gate (with the documented {evidence_dir} placeholder substituted by the
    # runner), and the recorded digest must be derived from it, not trusted.
    info = (catalog or gate_catalog())["by_id"][gate_id]
    if info.get("binding") == "catalog_command":
        expected_invocation = [part.replace("{evidence_dir}", str(evidence_dir)) for part in info["invocation"]]
        if list(receipt.get("invocation") or []) != expected_invocation:
            raise DeliverySummaryError("gate_command_not_authorized",
                                       f"{gate_id}: {receipt.get('invocation')!r} != {expected_invocation!r}")
    if receipt.get("invocation_digest") != sha_bytes(canonical_json_bytes(receipt.get("invocation") or [])):
        raise DeliverySummaryError("invalid_gate_receipt", f"{gate_id}: invocation digest")
    if gate_id == "full_cpu_test_suite":
        _validate_skip_identities(receipt, evidence_dir, info)
    else:
        for skip in receipt.get("skip_dispositions", []) or []:
            if not skip.get("approved"):
                raise DeliverySummaryError("unapproved_skip", f"{gate_id}: {skip}")
    log = receipt.get("log") or {}
    log_path = evidence_dir / log.get("path", "")
    if not log_path.is_file() or sha(log_path) != log.get("sha256"):
        raise DeliverySummaryError("gate_log_integrity", gate_id)
    if log_path.resolve() == Path(log.get("path", "x")).resolve() and ".." in Path(log.get("path", "")).parts:
        raise DeliverySummaryError("gate_log_integrity", gate_id)
    for name, digest in (receipt.get("artifact_digests") or {}).items():
        if ".." in Path(name).parts:
            raise DeliverySummaryError("gate_artifact_integrity", f"{gate_id}: {name}")
        artifact = evidence_dir / name
        if not artifact.is_file() or sha(artifact) != digest:
            raise DeliverySummaryError("gate_artifact_integrity", f"{gate_id}: {name}")
    environment = receipt.get("environment") or {}
    if not environment.get("python") or not environment.get("platform"):
        raise DeliverySummaryError("invalid_gate_receipt", f"{gate_id}: environment")
    return receipt


def _junit_skips(junit_path: Path) -> list[dict[str, str]]:
    import xml.etree.ElementTree as ElementTree

    skips = []
    root = ElementTree.parse(junit_path).getroot()
    for case in root.iter("testcase"):
        for skipped in case.findall("skipped"):
            classname = case.get("classname", "")
            prefix = classname.replace(".", "/") + ".py::" if classname else ""
            skips.append({"nodeid": prefix + case.get("name", ""),
                          "reason": skipped.get("message") or ""})
    return skips


def _validate_skip_identities(receipt: dict[str, Any], evidence_dir: Path, info: dict[str, Any]) -> None:
    """Skips are approved by frozen identity, never by count (R01/C)."""
    gate_id = "full_cpu_test_suite"
    approved = {entry["nodeid"]: entry for entry in info.get("approved_skips") or []}
    if not approved:
        raise DeliverySummaryError("invalid_gate_receipt", f"{gate_id}: catalog approves no skips")
    passed = receipt.get("passed_count")
    if isinstance(passed, bool) or not isinstance(passed, int) or passed <= 0:
        raise DeliverySummaryError("invalid_gate_receipt", f"{gate_id}: passed_count {passed!r}")
    dispositions = receipt.get("skip_dispositions") or []
    recorded = receipt.get("skip_count")
    if isinstance(recorded, bool) or not isinstance(recorded, int) or recorded != len(dispositions):
        raise DeliverySummaryError("unapproved_skip", f"{gate_id}: skip_count {recorded!r} vs {len(dispositions)} dispositions")
    for disposition in dispositions:
        nodeid = disposition.get("nodeid")
        entry = approved.get(nodeid)
        if entry is None:
            raise DeliverySummaryError("unapproved_skip", f"{gate_id}: unknown skip {nodeid!r}")
        reason = str(disposition.get("reason") or "")
        if not reason or entry["reason_contains"] not in reason:
            raise DeliverySummaryError("unapproved_skip", f"{gate_id}: reason mismatch for {nodeid}")
        if disposition.get("approved") is not True:
            raise DeliverySummaryError("unapproved_skip", f"{gate_id}: {nodeid} not approved")
    if {d.get("nodeid") for d in dispositions} != set(approved):
        raise DeliverySummaryError("unapproved_skip",
                                   f"{gate_id}: skip set changed vs catalog (missing/extra entries)")
    # The bound JUnit record must independently reproduce the dispositions.
    junit_digest = (receipt.get("artifact_digests") or {}).get("pytest-junit.xml")
    junit_path = evidence_dir / "pytest-junit.xml"
    if not junit_digest or not junit_path.is_file() or sha(junit_path) != junit_digest:
        raise DeliverySummaryError("gate_artifact_integrity", f"{gate_id}: pytest-junit.xml")
    if _junit_skips(junit_path) != [{"nodeid": d["nodeid"], "reason": d["reason"]} for d in dispositions]:
        raise DeliverySummaryError("unapproved_skip", f"{gate_id}: JUnit record differs from dispositions")


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


def _baseline_payload() -> dict[str, Any]:
    if not BASELINE_PATH.is_file():
        raise DeliverySummaryError("baseline_missing", str(BASELINE_PATH))
    return load_json(BASELINE_PATH)


def validate_campaign(campaign: dict[str, Any], expected_source: dict[str, Any], *, evidence_dir: Path | None = None) -> dict[str, Any]:
    """Re-derive the whole campaign verdict from recorded measurements (R02)."""
    if campaign.get("format") != CAMPAIGN_FORMAT:
        raise DeliverySummaryError("invalid_campaign_receipt", "format")
    try:
        source_matches(expected_source, campaign.get("source") or {}, "performance campaign")
    except DeliverySummaryError as error:
        raise DeliverySummaryError("stale_campaign_source", error.detail) from error
    baseline = _baseline_payload()
    baseline_sha256 = sha_bytes(BASELINE_PATH.read_bytes())
    groups = campaign.get("groups") or []
    if len(groups) != 3 or [row.get("group") for row in groups] != [0, 1, 2]:
        raise DeliverySummaryError("invalid_campaign_receipt", f"expected groups [0,1,2], found {[row.get('group') for row in groups]}")
    group_files = campaign.get("group_files") or []
    if len(group_files) != len(groups):
        raise DeliverySummaryError("invalid_campaign_receipt", "group_files must cover every group")
    if evidence_dir is None:
        raise DeliverySummaryError("campaign_group_integrity", "evidence directory required to read group files")
    for index, group in enumerate(groups):
        gate = group.get("delivery_gate") or {}
        measurement = group.get("measurement") or {}
        if group.get("returncode") != 0:
            raise DeliverySummaryError("failed_required_gate", f"campaign group {index}: exit {group.get('returncode')}")
        if group.get("delivery_status") != "pass" or gate.get("status") != "pass":
            raise DeliverySummaryError("failed_required_gate", f"campaign group {index}")
        if group.get("observation_status") != measurement.get("status"):
            raise DeliverySummaryError("invalid_campaign_receipt", f"campaign group {index}: observation drift")
        if group.get("delivery_gate") != measurement.get("delivery_gate"):
            raise DeliverySummaryError("invalid_campaign_receipt", f"campaign group {index}: gate drift")
        # The recorded measurement must re-derive the recorded verdict.
        if measurement.get("baseline_sha256") != baseline_sha256:
            raise DeliverySummaryError("campaign_baseline_mismatch", f"group {index}")
        commands = measurement.get("commands") or {}
        if set(commands) != set(baseline["commands"]):
            raise DeliverySummaryError("invalid_campaign_receipt", f"group {index}: workload set")
        for name, sample in commands.items():
            if sample.get("repeats") != baseline["commands"][name].get("repeats"):
                raise DeliverySummaryError("invalid_campaign_receipt", f"group {index}: repeats for {name}")
        recomputed = compute_delivery_gate(baseline, measurement)
        if recomputed["status"] != "pass":
            raise DeliverySummaryError("failed_required_gate", f"campaign group {index}: recomputed {recomputed['status']}")
        if gate != recomputed:
            raise DeliverySummaryError("invalid_campaign_receipt", f"group {index}: delivery gate does not match recomputation")
        observation, _ = classify(baseline, measurement)
        if group.get("observation_status") != observation:
            raise DeliverySummaryError("invalid_campaign_receipt", f"group {index}: observation does not match recomputation")
        # The group file on disk must carry exactly this measurement.
        binding = group_files[index] or {}
        relative = binding.get("path", "")
        if ".." in Path(relative).parts or not relative or Path(relative).is_absolute():
            raise DeliverySummaryError("invalid_campaign_receipt", f"group {index}: group file path")
        group_path = evidence_dir / relative
        digest = sha_bytes(group_path.read_bytes()) if group_path.is_file() else None
        if digest is None or digest != binding.get("sha256"):
            raise DeliverySummaryError("campaign_group_integrity", f"group {index}: {relative}")
        if load_json(group_path) != measurement:
            raise DeliverySummaryError("campaign_group_integrity", f"group {index}: content drift")
    if campaign.get("aggregate", {}).get("status") != "pass":
        raise DeliverySummaryError("failed_required_gate", "campaign aggregate")
    return campaign


def validate_linux_matrix(matrix: dict[str, Any], expected_source: dict[str, Any], evidence_dir: Path) -> dict[str, Any]:
    """Validate Linux cells with the one shared rule (R03/A); labels, shared
    markers, zero pass counts and unmatched manifests are refused here exactly
    as in the receipt builder."""
    from tools.sidscope_linux_matrix_cells import MatrixCellError, validate_cell
    from tools.sidscope_source_manifest import tree_manifest_digest

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
    expected_manifest = tree_manifest_digest(ROOT)
    for version, cell in sorted(by_python.items()):
        try:
            validate_cell(cell, expected_manifest=expected_manifest,
                          head=expected_source["head"],
                          public_snapshot_digest=expected_source["public_snapshot_digest"],
                          log_base=evidence_dir)
        except MatrixCellError as error:
            raise DeliverySummaryError(error.code, error.detail) from error
    return matrix


def build_summary(evidence_dir: Path, output: Path, *, expected_record_sha256: str) -> dict[str, Any]:
    evidence_dir = Path(evidence_dir).resolve()
    # Keep the caller's path (not a resolved copy): symlink identity must
    # survive until the exclusive-create guard rejects it (R05/D).
    output = Path(output)
    if output == evidence_dir:
        raise DeliverySummaryError("summary_output_invalid", "the summary must not replace the evidence directory")
    if output.name in {"release-record.json", "performance-campaign.json", "linux-matrix.json"}:
        raise DeliverySummaryError("summary_output_invalid", f"the summary must not replace bound evidence: {output.name}")
    catalog_info = gate_catalog()
    required = catalog_info["required"]
    expected_source = short_source()
    if not expected_source["clean"]:
        raise DeliverySummaryError("dirty_candidate", "delivery evidence requires a clean candidate")
    record_path = evidence_dir / "release-record.json"
    record = load_json(record_path)
    # R04: verify_record now re-hashes every bound sub-evidence file.
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
               if gate_id not in receipts and gate_id not in ("performance_campaign", "exact_source_record_v2")]
    if missing:
        raise DeliverySummaryError("missing_required_gate", str(missing))
    gate_entries = []
    for gate_id in required:
        if gate_id in ("performance_campaign", "exact_source_record_v2"):
            continue
        receipt = validate_receipt(receipts[gate_id], evidence_dir, expected_source, gate_id, catalog=catalog_info)
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
    campaign_path = evidence_dir / "performance-campaign.json"
    if not campaign_path.is_file():
        raise DeliverySummaryError("missing_campaign_receipt", str(campaign_path))
    campaign = validate_campaign(load_json(campaign_path), expected_source, evidence_dir=evidence_dir)
    gate_entries.append({"gate_id": "performance_campaign", "status": "pass",
                         "receipt": {"path": "performance-campaign.json", "sha256": sha(campaign_path)},
                         "source": campaign["source"],
                         "environment_id": sha_bytes(canonical_json_bytes(campaign.get("environment") or {})),
                         "invocation_digest": campaign.get("invocation_digest", ""),
                         "exit_code": 0,
                         "log_digest": campaign["aggregate"].get("log_digest", ""),
                         "receipt_digest": sha(campaign_path),
                         "artifact_digests": {row["path"]: row["sha256"] for row in campaign.get("group_files", [])},
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
        "deferred_gates": catalog_info["catalog"]["deferred_gates"],
        "platform_support": catalog_info["catalog"]["platform_support"],
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
    # R05: exclusive create; an existing summary or symlink is never overwritten.
    _exclusive_write(output, canonical_json_bytes(summary) + b"\n", code="summary_output_exists")
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
    for field in ("deferred_gates", "platform_support"):
        if summary.get(field) != catalog_info["catalog"][field]:
            raise DeliverySummaryError("delivery_scope_mismatch", field)
    if summary.get("unverified_claims") != UNVERIFIED_CLAIMS:
        raise DeliverySummaryError("delivery_scope_mismatch", "unverified_claims")
    gate_ids = [row["gate_id"] for row in summary["gates"]]
    if sorted(gate_ids) != sorted(catalog_info["required"]):
        raise DeliverySummaryError("gate_catalog_incomplete", str(sorted(set(catalog_info["required"]) ^ set(gate_ids))))
    if len(set(gate_ids)) != len(gate_ids):
        raise DeliverySummaryError("duplicate_gate_receipt", "summary entries")
    expected_source = summary["source"]
    record_path = evidence_dir / "release-record.json"
    record_entry = next(row for row in summary["gates"] if row["gate_id"] == "exact_source_record_v2")
    verify_record(record_path, expected_record_sha256=record_entry["receipt"]["sha256"],
                  archive_path=evidence_dir / "runtime.zip", profile="runtime")
    verify_record(record_path, expected_record_sha256=record_entry["receipt"]["sha256"],
                  archive_path=evidence_dir / "conformance.zip", profile="conformance")
    verify_record(record_path, expected_record_sha256=record_entry["receipt"]["sha256"],
                  archive_path=evidence_dir / "evidence-full.zip", profile="evidence-full")
    for row in summary["gates"]:
        receipt_path = evidence_dir / row["receipt"]["path"]
        if ".." in Path(row["receipt"]["path"]).parts or not receipt_path.is_file() or sha(receipt_path) != row["receipt_digest"]:
            raise DeliverySummaryError("receipt_integrity", row["gate_id"])
        if row["status"] != "pass" or row["exit_code"] != 0:
            raise DeliverySummaryError("failed_required_gate", row["gate_id"])
        if row["gate_id"] in ("performance_campaign", "exact_source_record_v2"):
            continue
        receipt = load_json(receipt_path)
        validate_receipt(receipt, evidence_dir, expected_source, row["gate_id"], catalog=catalog_info)
        if receipt.get("invocation_digest") != row["invocation_digest"]:
            raise DeliverySummaryError("receipt_integrity", row["gate_id"] + ": invocation")
    campaign_path = evidence_dir / "performance-campaign.json"
    if not campaign_path.is_file():
        raise DeliverySummaryError("missing_campaign_receipt", str(campaign_path))
    validate_campaign(load_json(campaign_path), expected_source, evidence_dir=evidence_dir)
    return {"status": "pass", "summary_sha256": sha(summary_path), "source": expected_source,
            "delivery_ready": True, "certification_ready": summary.get("certification_ready") is True,
            "release_authorized": False}


def run_gate(gate_id: str, evidence_dir: Path, command: list[str] | None = None) -> dict[str, Any]:
    """Execute exactly the catalog invocation for the gate; never a caller command."""
    catalog_info = gate_catalog()
    if gate_id not in catalog_info["required"]:
        raise DeliverySummaryError("unknown_gate_receipt", gate_id)
    info = catalog_info["by_id"][gate_id]
    if info.get("binding") != "catalog_command":
        raise DeliverySummaryError("gate_command_not_authorized", f"{gate_id}: no bound invocation")
    expected_invocation = list(info["invocation"])
    if command is not None and list(command) != expected_invocation:
        raise DeliverySummaryError("gate_command_not_authorized",
                                   f"{gate_id}: {command!r} != {expected_invocation!r}")
    evidence_dir = evidence_dir.resolve()
    (evidence_dir / "gates").mkdir(parents=True, exist_ok=True)
    (evidence_dir / "logs").mkdir(parents=True, exist_ok=True)
    receipt_path = evidence_dir / f"gates/{gate_id}.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        raise DeliverySummaryError("duplicate_gate_receipt", f"{gate_id} receipt exists; use a new attempt directory")
    before = short_source()
    if not before["clean"]:
        raise DeliverySummaryError("dirty_candidate", f"{gate_id} requires a clean candidate")
    # The full-suite gate writes its JUnit record via PYTEST_ADDOPTS so the
    # executed argv stays exactly the frozen catalog command. The variable is
    # OVERWRITTEN, never inherited: an external PYTEST_ADDOPTS (for example a
    # -k expression) could otherwise shrink the suite while the summary line
    # still reports it as passing (third-round acceptance finding 1).
    import os
    gate_environment = dict(os.environ)
    if gate_id == "full_cpu_test_suite":
        gate_environment["PYTEST_ADDOPTS"] = f'--junitxml={evidence_dir / "pytest-junit.xml"}'
    run = subprocess.run([sys.executable, *expected_invocation], cwd=ROOT, capture_output=True,
                         shell=False, env=gate_environment)
    log_path = evidence_dir / f"logs/{gate_id}.log"
    log_path.write_bytes(run.stdout + run.stderr)
    after = short_source()
    source_stable = after == before
    status = "pass" if run.returncode == 0 and source_stable else "failed"
    receipt: dict[str, Any] = with_content_sha256({
        "format": RECEIPT_FORMAT, "gate_id": gate_id,
        "status": status,
        "source": before,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "invocation": expected_invocation,
        "invocation_digest": sha_bytes(canonical_json_bytes(expected_invocation)),
        "exit_code": run.returncode,
        "log": {"path": f"logs/{gate_id}.log", "sha256": sha(log_path)},
        "artifact_digests": {},
        "skip_dispositions": [],
    })
    if gate_id == "full_cpu_test_suite":
        approved = {entry["nodeid"]: entry for entry in info.get("approved_skips") or []}
        junit_path = evidence_dir / "pytest-junit.xml"
        tail = run.stdout.decode(errors="replace").strip().splitlines()[-1] if run.stdout else ""
        match = PYTEST_SUMMARY.search(tail)
        skips = _junit_skips(junit_path) if junit_path.is_file() else None
        if match is None or skips is None:
            receipt["status"] = "failed"
            receipt["skip_count"] = -1
            receipt["passed_count"] = 0
            receipt["skip_dispositions"] = []
            receipt["detail"] = "pytest summary line or JUnit record missing"
        else:
            receipt["passed_count"] = int(match.group(1))
            recorded = int(match.group(2) or 0)
            deselected = int(match.group(3) or 0)
            receipt["skip_count"] = recorded
            dispositions = []
            for skip in skips:
                entry = approved.get(skip["nodeid"])
                dispositions.append({"nodeid": skip["nodeid"], "reason": skip["reason"],
                                     "approved": bool(entry and entry["reason_contains"] in skip["reason"])})
            receipt["skip_dispositions"] = dispositions
            receipt["artifact_digests"] = {"pytest-junit.xml": sha(junit_path)}
            # A shrunk suite (deselected tests) can never count as the full
            # suite, and the JUnit record must account for exactly the
            # executed population with no failures or errors.
            if deselected:
                receipt["status"] = "failed"
                receipt["detail"] = f"suite shrunk by -k style selection: {deselected} deselected"
            else:
                import xml.etree.ElementTree as ElementTree

                junit_root = ElementTree.parse(junit_path).getroot()
                cases = junit_root.iter("testcase")
                case_count = sum(1 for _ in cases)
                failures = sum(len(list(case)) for case in junit_root.iter("testcase")
                               if case.findall("failure") or case.findall("error"))
                if case_count != receipt["passed_count"] + recorded:
                    receipt["status"] = "failed"
                    receipt["detail"] = (f"JUnit records {case_count} cases but the summary line reports "
                                         f"{receipt['passed_count']} passed + {recorded} skipped")
                elif failures:
                    receipt["status"] = "failed"
                    receipt["detail"] = f"JUnit records {failures} failing/error cases"
            if not source_stable:
                receipt["detail"] = "source tree changed during gate execution"
    with receipt_path.open("xb") as handle:
        handle.write(canonical_json_bytes(receipt) + b"\n")
    if receipt["status"] != "pass":
        return {"status": receipt["status"], "gate_id": gate_id, "exit_code": run.returncode,
                "receipt": str(receipt_path), "log": str(log_path),
                "code": None if run.returncode == 0 else "gate_command_failed"}
    return {"status": receipt["status"], "gate_id": gate_id, "exit_code": run.returncode,
            "receipt": str(receipt_path), "log": str(log_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run-gate")
    run.add_argument("--gate-id", required=True)
    run.add_argument("--evidence-dir", type=Path, required=True)
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
            result = run_gate(args.gate_id, args.evidence_dir)
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
