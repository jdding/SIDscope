import hashlib
import json
from pathlib import Path

import pytest

from tools import sidscope_delivery_summary as summary
from tools import sidscope_local_release_record as record
from tools.sidscope_delivery_summary import (
    DeliverySummaryError,
    build_summary,
    gate_catalog,
    verify_summary,
)

SOURCE = {"head": "a" * 40, "branch": "codex/sidscope-v2", "clean": True,
          "public_snapshot_digest": "b" * 64}
RECEIPT_GATES = ["full_cpu_test_suite", "release_metadata_verifier", "architecture_inventory_verifier",
                 "sdlc_acceptance_verifier", "sdlc_hardening_engineering_ready", "release_profiles_verifier",
                 "candidate_engineering_ready_clean", "resource_package_verifier"]
PROFILE_ARCHIVES = {"runtime": "c" * 64, "conformance": "d" * 64, "evidence-full": "e" * 64}


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_receipt(evidence: Path, gate_id: str, *, status="pass", exit_code=0, head=SOURCE["head"],
                  snapshot=SOURCE["public_snapshot_digest"], skip=None, log_text=b"ok\n"):
    log_path = evidence / "logs" / f"{gate_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(log_text)
    from tools import sidscope_delivery_summary as gate_module
    catalog = gate_module.gate_catalog()["by_id"].get(gate_id)
    invocation = list(catalog["invocation"]) if catalog else ["python", gate_id]
    receipt = {"format": summary.RECEIPT_FORMAT, "gate_id": gate_id, "status": status,
               "source": {"head": head, "branch": SOURCE["branch"], "clean": True,
                          "public_snapshot_digest": snapshot},
               "environment": {"python": "3.9.6", "platform": "macOS-26.6.2-arm64-arm-64bit"},
               "invocation": invocation,
               "invocation_digest": digest_bytes(summary.canonical_json_bytes(invocation)),
               "exit_code": exit_code,
               "log": {"path": f"logs/{gate_id}.log", "sha256": digest_bytes(log_path.read_bytes())},
               "artifact_digests": {}, "skip_dispositions": skip or []}
    if gate_id == "full_cpu_test_suite":
        receipt["passed_count"] = 649
        receipt["skip_count"] = len(skip) if skip else 0
    path = evidence / "gates" / f"{gate_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(summary.canonical_json_bytes(receipt) + b"\n")
    return receipt


BASELINE_PAYLOAD = json.loads(
    (Path(__file__).resolve().parents[1] / "docs/reproducibility/sidscope_1_2_cli_cpu_baseline.json").read_text())
BASELINE_SHA = hashlib.sha256(
    (Path(__file__).resolve().parents[1] / "docs/reproducibility/sidscope_1_2_cli_cpu_baseline.json").read_bytes()).hexdigest()


def _recomputed_measurement():
    measurement = {"status": "pass", "environment": dict(BASELINE_PAYLOAD["environment"]),
                   "commands": {name: {"median_ms": sample["median_ms"], "repeats": sample["repeats"]}
                                for name, sample in BASELINE_PAYLOAD["commands"].items()},
                   "baseline_sha256": BASELINE_SHA}
    from tools.check_sidscope_current_performance import delivery_gate as compute_gate
    measurement["delivery_gate"] = compute_gate(BASELINE_PAYLOAD, measurement)
    return measurement


def write_record(evidence: Path):
    content = SOURCE["public_snapshot_digest"]
    artifact_files = {}
    for name in ("performance.json", "distribution/result.json"):
        path = evidence / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic sub-evidence for " + name.encode())
        artifact_files[name] = digest_bytes(path.read_bytes())
    for index in range(5):
        path = evidence / f"test-{index}.log"
        path.write_bytes(f"synthetic test log {index}\n".encode())
        artifact_files[f"test-{index}.log"] = digest_bytes(path.read_bytes())
    for profile in PROFILE_ARCHIVES:
        for suffix in ("-smoke.json", "-g8.json", "-g8.log"):
            path = evidence / (profile + suffix)
            path.write_bytes(b"synthetic " + (profile + suffix).encode())
            artifact_files[profile + suffix] = digest_bytes(path.read_bytes())
    payload = {"format": "sidscope.local_release_record.v2", "status": "pass",
               "source": {"head": SOURCE["head"], "branch": SOURCE["branch"], "dirty": False,
                          "content_sha256": content, "public_files": {}},
               "tests": [{"command": ["pytest"], "returncode": 0, "output_sha256": "0" * 64,
                          "source_snapshot_sha256": content}],
               "performance": {"result_sha256": "0" * 64, "observation_status": "environment_review_required",
                               "delivery_status": "pass", "disposition": "platform_version_variance_within_frozen_threshold",
                               "measurement": {"status": "environment_review_required",
                                               "delivery_gate": {"status": "pass",
                                                                 "disposition": "platform_version_variance_within_frozen_threshold"}},
                               "source_snapshot_sha256": content},
               "archives": [{"profile": profile, "archive_sha256": archive,
                             "source_snapshot_sha256": content, "smoke": "pass"}
                            for profile, archive in PROFILE_ARCHIVES.items()],
               "build_environment": {"python": "3.9.6", "platform": "darwin"},
               "release_authorized": False,
               "artifact_files": artifact_files}
    path = evidence / "release-record.json"
    path.write_bytes(record.canonical_json_bytes(payload) + b"\n")
    return path, record.sha(path)


def write_campaign(evidence: Path, *, groups=3, delivery_status="pass"):
    measurement = _recomputed_measurement()
    if delivery_status != "pass":
        measurement["commands"] = {}
        measurement["delivery_gate"] = {**measurement["delivery_gate"], "status": "blocked"}
    group_rows = []
    group_files = []
    for index in range(groups):
        group_path = evidence / f"performance-campaign-group-{index}.json"
        payload = json.loads(json.dumps(measurement))
        group_path.write_bytes(summary.canonical_json_bytes(payload) + b"\n")
        group_files.append({"path": group_path.name, "sha256": digest_bytes(group_path.read_bytes())})
        group_rows.append({"group": index, "returncode": 0 if delivery_status == "pass" else 2,
                           "delivery_status": delivery_status,
                           "observation_status": measurement["status"],
                           "delivery_gate": measurement["delivery_gate"],
                           "disposition": measurement["delivery_gate"]["disposition"],
                           "median_ratios": measurement["delivery_gate"]["median_ratios"],
                           "environment": measurement["environment"], "measurement": payload})
    receipt = {"format": summary.CAMPAIGN_FORMAT, "status": "pass" if delivery_status == "pass" else "failed",
               "source": dict(SOURCE), "baseline_sha256": BASELINE_SHA,
               "environment": {"python": "3.9.6", "platform": "macOS-26.6.2-arm64-arm-64bit"},
               "invocation_digest": "0" * 64, "groups": group_rows,
               "group_files": group_files,
               "group_digests": [row["sha256"] for row in group_files],
               "aggregate": {"status": "pass" if delivery_status == "pass" else "failed"}, "group_count": groups}
    path = evidence / "performance-campaign.json"
    path.write_bytes(summary.canonical_json_bytes(receipt) + b"\n")
    return path


LINUX_IMAGES = {"3.9": "python:3.9-slim", "3.10": "python:3.10-slim",
                "3.11": "python:3.11-slim", "3.12": "python:3.12-slim"}
LINUX_STEPS = ("pytest", "metadata", "architecture", "sdlc_acceptance",
               "sdlc_hardening", "profiles", "resource")


def write_linux(evidence: Path, *, cells=("3.9", "3.10", "3.11", "3.12"), head=SOURCE["head"],
                status="pass", os_name="Linux 6.5.0-arm64", steps="full",
                snapshot=SOURCE["public_snapshot_digest"]):
    rows = []
    for version in cells:
        log_path = evidence / "logs" / f"linux-{version}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        step_rows = []
        markers = []
        for name in LINUX_STEPS:
            if steps == "full" or (steps == "no-resource" and name != "resource"):
                marker = f"STEP-OK {name} {version}"
                step_rows.append({"name": name, "exit_code": 0,
                                  "passed_count": 649 if name == "pytest" else None,
                                  "log_marker": marker})
                markers.append(marker)
        log_path.write_text("\n".join(markers) + "\n")
        rows.append({"python": version, "image": LINUX_IMAGES[version], "os": os_name,
                     "arch": "aarch64", "interpreter": "/usr/local/bin/python3",
                     "status": status, "exit_code": 0 if status == "pass" else 1,
                     "head": head,
                     "source_check": {"head": head, "public_snapshot_digest": snapshot, "clean": True},
                     "steps": step_rows,
                     "log": {"path": f"logs/linux-{version}.log", "sha256": digest_bytes(log_path.read_bytes())}})
    receipt = {"format": summary.LINUX_FORMAT, "source": dict(SOURCE), "os_family": "Linux",
               "invocation_digest": "0" * 64, "cells": rows}
    path = evidence / "linux-matrix.json"
    path.write_bytes(summary.canonical_json_bytes(receipt) + b"\n")
    return path


@pytest.fixture()
def evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(summary, "short_source", lambda: dict(SOURCE))
    monkeypatch.setattr(record, "verify_archive_digest", lambda *args, **kwargs: None)
    monkeypatch.setattr(record, "read_archive_profile", lambda *args, **kwargs: None)
    store = tmp_path / "evidence"
    (store / "logs").mkdir(parents=True)
    for gate_id in RECEIPT_GATES:
        write_receipt(store, gate_id)
    write_record(store)
    write_campaign(store)
    write_linux(store)
    return store


def test_catalog_is_frozen_and_matches_the_builder():
    info = gate_catalog()
    assert len(info["required"]) == 11
    assert "exact_source_record_v2" in info["required"]
    assert info["digest"] == hashlib.sha256(
        (summary.ROOT / "docs/reproducibility/sidscope_required_gate_catalog.v1.json").read_bytes()).hexdigest()


def test_build_and_reverify_roundtrip(evidence, tmp_path):
    _, record_sha = write_record(evidence)
    output = tmp_path / "delivery-summary.json"
    built = build_summary(evidence, output, expected_record_sha256=record_sha)
    assert built["status"] == "pass" and len(built["gates"]) == 11
    verified = verify_summary(output, expected_summary_sha256=built["summary_sha256"], evidence_dir=evidence)
    assert verified["delivery_ready"] is True
    loaded = json.loads(output.read_text())
    assert loaded["release_authorized"] is False
    assert loaded["excluded_acceptance"] == ["independent_user_actual_use"]
    assert "independent_user_actual_use" in loaded["unverified_claims"]
    assert loaded["gate_catalog_digest"] == gate_catalog()["digest"]


def test_missing_required_gate_is_rejected(evidence, tmp_path):
    (evidence / "gates" / "release_metadata_verifier.json").unlink()
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "missing_required_gate"


def test_unknown_gate_receipt_is_rejected(evidence, tmp_path):
    write_receipt(evidence, "invented_gate")
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "unknown_gate_receipt"


def test_duplicate_gate_receipt_is_rejected(evidence, tmp_path):
    receipt = write_receipt(evidence, "full_cpu_test_suite")
    second = evidence / "gates" / "full_cpu_test_suite.copy.json"
    second.write_bytes(summary.canonical_json_bytes(receipt) + b"\n")
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "duplicate_gate_receipt"


def test_single_command_success_cannot_produce_ready(evidence, tmp_path):
    for gate_id in RECEIPT_GATES[1:]:
        (evidence / "gates" / f"{gate_id}.json").unlink()
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "missing_required_gate"


def test_failed_or_skipped_required_gate_is_rejected(evidence, tmp_path):
    write_receipt(evidence, "full_cpu_test_suite", status="failed", exit_code=1)
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "failed_required_gate"
    write_receipt(evidence, "full_cpu_test_suite",
                  skip=[{"reason": "external input unavailable", "approved": False}])
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "unapproved_skip"


def test_stale_source_identity_is_rejected(evidence, tmp_path):
    write_receipt(evidence, "full_cpu_test_suite", head="9" * 40)
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "stale_gate_source"


def test_dirty_candidate_cannot_build(evidence, tmp_path, monkeypatch):
    dirty = dict(SOURCE)
    dirty["clean"] = False
    monkeypatch.setattr(summary, "short_source", lambda: dirty)
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "dirty_candidate"


def test_tampered_evidence_fails_verification(evidence, tmp_path):
    _, record_sha = write_record(evidence)
    output = tmp_path / "s.json"
    built = build_summary(evidence, output, expected_record_sha256=record_sha)
    log = evidence / "logs" / "full_cpu_test_suite.log"
    original = log.read_bytes()
    log.write_bytes(original + b"tampered\n")
    with pytest.raises((DeliverySummaryError, Exception)) as caught:
        verify_summary(output, expected_summary_sha256=built["summary_sha256"], evidence_dir=evidence)
    assert "integrity" in str(getattr(caught.value, "code", "")).lower()
    log.write_bytes(original)
    assert verify_summary(output, expected_summary_sha256=built["summary_sha256"], evidence_dir=evidence)["status"] == "pass"


def test_summary_digest_and_catalog_binding_are_enforced(evidence, tmp_path):
    _, record_sha = write_record(evidence)
    output = tmp_path / "s.json"
    built = build_summary(evidence, output, expected_record_sha256=record_sha)
    with pytest.raises(DeliverySummaryError) as caught:
        verify_summary(output, expected_summary_sha256="0" * 64, evidence_dir=evidence)
    assert caught.value.code == "summary_digest_mismatch"
    summary_bytes = output.read_bytes()
    output.write_bytes(summary_bytes + b" ")
    with pytest.raises(DeliverySummaryError) as caught:
        verify_summary(output, expected_summary_sha256=built["summary_sha256"], evidence_dir=evidence)
    assert caught.value.code == "summary_digest_mismatch"
    output.write_bytes(summary_bytes)


def test_campaign_shape_is_enforced(evidence, tmp_path):
    write_campaign(evidence, groups=2)
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "invalid_campaign_receipt"
    write_campaign(evidence, delivery_status="blocked")
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "failed_required_gate"


def test_linux_matrix_shape_is_enforced(evidence, tmp_path):
    write_linux(evidence, cells=("3.9", "3.10", "3.11"))
    _, record_sha = write_record(evidence)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "invalid_linux_receipt"
    write_linux(evidence, head="9" * 40)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "stale_linux_source"


def test_probe_regressions_are_all_rejected(evidence, tmp_path):
    """Six negative probes from the 2026-09-28 acceptance report, now refused."""
    # R01: an unrelated command can never run for a bound gate.
    with pytest.raises(DeliverySummaryError) as caught:
        summary.run_gate("full_cpu_test_suite", tmp_path, ["/usr/bin/true"])
    assert caught.value.code == "gate_command_not_authorized"
    receipt = write_receipt(evidence, "full_cpu_test_suite")
    receipt["invocation"] = ["/usr/bin/true"]
    with pytest.raises(DeliverySummaryError) as caught:
        summary.validate_receipt(receipt, evidence, dict(SOURCE), "full_cpu_test_suite")
    assert caught.value.code == "gate_command_not_authorized"
    # R01b: skips beyond the documented boundary cannot hide in a receipt.
    receipt = write_receipt(evidence, "full_cpu_test_suite",
                            skip=[{"reason": "invented", "approved": True}] * 7)
    receipt["skip_count"] = 7
    with pytest.raises(DeliverySummaryError) as caught:
        summary.validate_receipt(receipt, evidence, dict(SOURCE), "full_cpu_test_suite")
    assert caught.value.code == "unapproved_skip"
    write_receipt(evidence, "full_cpu_test_suite")
    # R02: failed groups with emptied measurements are refused by recomputation.
    import copy
    campaign = json.loads((evidence / "performance-campaign.json").read_text())
    bad = copy.deepcopy(campaign)
    for group in bad["groups"]:
        group["returncode"] = 2
        group["measurement"]["commands"] = {}
        group["measurement"]["delivery_gate"]["status"] = "blocked"
    with pytest.raises(DeliverySummaryError) as caught:
        summary.validate_campaign(bad, dict(SOURCE), evidence_dir=evidence)
    assert caught.value.code == "failed_required_gate"
    # R02b: baseline rebinding is refused.
    bad = copy.deepcopy(campaign)
    bad["baseline_sha256"] = "0" * 64
    with pytest.raises(DeliverySummaryError) as caught:
        summary.validate_campaign(bad, dict(SOURCE), evidence_dir=evidence)
    assert caught.value.code == "campaign_baseline_mismatch"
    # R02c: tampered group files on disk are refused.
    group_file = evidence / campaign["group_files"][0]["path"]
    original = group_file.read_bytes()
    group_file.write_bytes(original + b"tampered")
    with pytest.raises(DeliverySummaryError) as caught:
        summary.validate_campaign(campaign, dict(SOURCE), evidence_dir=evidence)
    assert caught.value.code == "campaign_group_integrity"
    group_file.write_bytes(original)
    # R03: Darwin labels, missing steps and fake source checks are refused.
    _, record_sha = write_record(evidence)
    write_linux(evidence, os_name="Darwin 24.0.0")
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "invalid_linux_cell"
    write_linux(evidence, steps="no-resource")
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "invalid_linux_cell"
    write_linux(evidence, snapshot="0" * 64)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, tmp_path / "s.json", expected_record_sha256=record_sha)
    assert caught.value.code == "stale_linux_source"


def test_existing_summary_output_is_never_overwritten(evidence, tmp_path):
    _, record_sha = write_record(evidence)
    output = tmp_path / "s.json"
    built = build_summary(evidence, output, expected_record_sha256=record_sha)
    original = output.read_bytes()
    output.write_bytes(b"DO NOT OVERWRITE")
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, output, expected_record_sha256=record_sha)
    assert caught.value.code == "summary_output_exists"
    alias = tmp_path / "alias.json"
    alias.symlink_to(output)
    with pytest.raises(DeliverySummaryError) as caught:
        build_summary(evidence, alias, expected_record_sha256=record_sha)
    assert caught.value.code == "summary_output_exists"
    output.write_bytes(original)
    assert verify_summary(output, expected_summary_sha256=built["summary_sha256"], evidence_dir=evidence)["status"] == "pass"


def test_record_sub_evidence_files_are_recursively_verified(evidence, tmp_path):
    _, record_sha = write_record(evidence)
    (evidence / "test-3.log").unlink()
    with pytest.raises(record.ReleaseRecordError) as caught:
        record.verify_record(evidence / "release-record.json", expected_record_sha256=record_sha,
                             archive_path=evidence / "runtime.zip", profile="runtime")
    assert caught.value.code == "record_sub_evidence_missing_or_tampered"
    write_record(evidence)
    tampered = evidence / "runtime-g8.log"
    original = tampered.read_bytes()
    tampered.write_bytes(original + b"tampered")
    with pytest.raises(record.ReleaseRecordError) as caught:
        record.verify_record(evidence / "release-record.json", expected_record_sha256=record_sha,
                             archive_path=evidence / "runtime.zip", profile="runtime")
    assert caught.value.code == "record_sub_evidence_missing_or_tampered"
    tampered.write_bytes(original)
