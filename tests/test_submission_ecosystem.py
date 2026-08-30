from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sidinspector.contracts.hashing import canonical_json_bytes, with_content_sha256
from sidinspector.conformance_core import load_profile_catalog, profile_catalog_content_sha256
from sidinspector.evidence.bundle import build_evidence_bundle
from sidinspector.submission import (
    canonical_index_bytes,
    check_submission,
    generate_submission_indexes,
    legacy_status_parity,
    validate_submission_check_report,
    validate_submission_package,
)
from sidinspector.submission.contracts import build_evidence_submission


ROOT = Path(__file__).resolve().parents[1]
NEGATIVE_INVENTORY = (
    ROOT / "examples" / "conformance_ecosystem_fixture" / "submission" / "negative_inventory.json"
)
POSITIVE_PACKAGE = (
    ROOT / "examples" / "conformance_ecosystem_fixture" / "submission" / "positive"
)
ROLES = ("source", "data", "sid", "run", "checkpoint", "trace", "diagnostics", "conformance")
SCHEMA_BY_ROLE = {
    "source": "sidscope.source_identity.v1",
    "data": "sidscope.prepared_dataset.v1",
    "sid": "sidscope.sid_space_identity.v1",
    "run": "sidscope.run_identity.v1",
    "checkpoint": "sidscope.checkpoint_binding.v1",
    "trace": "sidscope.trace_envelope.v1",
    "diagnostics": "sidscope.diagnostic_report.v1",
    "conformance": "sidscope.profile_conformance_report.v1",
}


def _write_json(path: Path, value: dict[str, Any]) -> bytes:
    payload = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _build_package(
    root: Path,
    *,
    adapter_id: str = "external-parallel",
    partial: bool = False,
    hit: float = 0.2,
    supersedes: list[str] | None = None,
) -> dict[str, Any]:
    profile = next(item for item in load_profile_catalog() if item.profile_kind == "generator")
    decision_status = "partial" if partial else "pass"
    dataset_sha = "a" * 64
    target_sha = "b" * 64
    descriptor = with_content_sha256(
        {
            "schema": "sidscope.dataset_profile_descriptor.v1",
            "schema_revision": "1.0.0",
            "descriptor_id": "external-vg-frozen",
            "producer": {"name": "third-party.example", "version": "0.1.0"},
            "dataset_identity_sha256": dataset_sha,
            "split_bindings": [
                {"role": "train", "content_sha256": "1" * 64, "row_count": 100},
                {"role": "validation", "content_sha256": "2" * 64, "row_count": 20},
                {"role": "test", "content_sha256": "3" * 64, "row_count": 25},
            ],
            "catalog": {
                "scope": "train_only",
                "item_count": 90,
                "content_sha256": "4" * 64,
            },
            "target_universe": {
                "scope": "evaluation_targets",
                "item_count": 25,
                "content_sha256": target_sha,
            },
            "evaluation": {
                "cutoff": 10,
                "publication_depth": 100,
                "slices": [
                    {"slice_id": "gap_gt_365d", "definition_sha256": "5" * 64},
                    {"slice_id": "overall", "definition_sha256": "6" * 64},
                ],
            },
            "privacy": {
                "policy_sha256": "7" * 64,
                "source_user_ids_exported": False,
                "source_item_ids_exported": False,
                "absolute_private_paths_exported": False,
            },
        }
    )
    descriptor_payload = _write_json(root / "contracts" / "dataset_profile.json", descriptor)

    report = with_content_sha256(
        {
            "schema": "sidscope.profile_conformance_report.v1",
            "schema_revision": "1.0.0",
            "report_id": f"report:{adapter_id}",
            "producer": {"name": "sidscope.profile-engine", "version": "1.5.0.dev0"},
            "profile_binding": {
                "profile_id": profile.profile_id,
                "profile_revision": profile.revision,
                "catalog_sha256": profile_catalog_content_sha256(),
            },
            "descriptor_binding": {
                "schema_id": "sidscope.dataset_profile_descriptor.v1",
                "schema_revision": "1.0.0",
                "content_sha256": descriptor["content_sha256"],
            },
            "artifacts": [
                {
                    "artifact_id": "dataset-profile",
                    "role": "dataset_profile_descriptor",
                    "schema_id": "sidscope.dataset_profile_descriptor.v1",
                    "schema_revision": "1.0.0",
                    "content_sha256": descriptor["content_sha256"],
                }
            ],
            "gates": [
                {
                    "gate_id": gate.gate_id,
                    "status": "partial" if partial and gate.gate_id == profile.gates[-1].gate_id else "pass",
                    "failure": (
                        {"code": gate.failure_code, "detail": "public evidence is intentionally partial"}
                        if partial and gate.gate_id == profile.gates[-1].gate_id
                        else None
                    ),
                }
                for gate in profile.gates
            ],
            "decision": {
                "status": decision_status,
                "status_label": profile.status_label_policy[decision_status],
            },
        }
    )
    report_payload = _write_json(root / "reports" / "conformance.json", report)
    report_object_sha = _sha(report_payload)

    artifacts = []
    for index, role in enumerate(ROLES):
        if role == "conformance":
            content_sha = report["content_sha256"]
            object_sha = report_object_sha
            size_bytes = len(report_payload)
            availability = "embedded_public"
        else:
            content_sha = f"{index + 20:064x}"
            object_sha = f"{index + 40:064x}"
            size_bytes = index + 100
            availability = "hash_reference_only"
        artifacts.append(
            {
                "artifact_id": f"artifact:{index}:{role}",
                "role": role,
                "schema_id": SCHEMA_BY_ROLE[role],
                "schema_revision": "1.0.0",
                "content_sha256": content_sha,
                "object_sha256": object_sha,
                "size_bytes": size_bytes,
                "media_type": "application/json",
                "availability": availability,
            }
        )
    edges = [
        {
            "from_artifact": f"artifact:{index}:{ROLES[index]}",
            "to_artifact": f"artifact:{index + 1}:{ROLES[index + 1]}",
            "relation": "produces",
        }
        for index in range(len(ROLES) - 1)
    ]
    bundle = build_evidence_bundle(
        bundle_id=f"external:{adapter_id}:vg",
        producer={"name": "third-party.example", "version": "0.1.0"},
        profile_binding={
            "profile_id": profile.profile_id,
            "profile_revision": profile.revision,
            "conformance_report_sha256": report["content_sha256"],
        },
        subject={"adapter_id": adapter_id, "method_family": "parallel_graph_token_set"},
        compatibility={
            "dataset_identity_sha256": dataset_sha,
            "target_universe_sha256": target_sha,
            "evaluation_cutoff": 10,
            "publication_depth": 100,
            "rank_semantics": "exact_with_censoring",
        },
        artifacts=artifacts,
        provenance_edges=edges,
        result_card={
            "overall_metrics": {"hit_at_10": hit, "ndcg_at_10": hit / 2},
            "slice_metrics": {"gap_gt_365d": {"hit_at_10": 0.0, "ndcg_at_10": 0.0}},
            "failure_counts": {"generation_search_miss": 2, "success": 1},
            "compute": {"nfe": 20, "latency_ms": 4.0},
            "rank_observations": {
                "exact_count": 2,
                "censored_count": 1,
                "exact_ranks": [1, 17],
            },
        },
        supersedes=supersedes or [],
    )
    bundle_payload = _write_json(root / "evidence" / "bundle.json", bundle.to_dict())
    artifact_rows = [
        {
            "artifact_id": "core:bundle",
            "role": "evidence_bundle",
            "path": "evidence/bundle.json",
            "sha256": _sha(bundle_payload),
        },
        {
            "artifact_id": "core:descriptor",
            "role": "dataset_profile_descriptor",
            "path": "contracts/dataset_profile.json",
            "sha256": _sha(descriptor_payload),
        },
        {
            "artifact_id": "core:report",
            "role": "profile_conformance_report",
            "path": "reports/conformance.json",
            "sha256": report_object_sha,
        },
    ]
    submission = build_evidence_submission(
        submission_id=f"submission:{adapter_id}",
        producer={"name": "third-party.example", "version": "0.1.0"},
        artifacts=artifact_rows,
        claims={
            "profile_id": profile.profile_id,
            "profile_revision": profile.revision,
            "dataset_identity_sha256": dataset_sha,
            "target_universe_sha256": target_sha,
            "evaluation_cutoff": 10,
            "publication_depth": 100,
            "rank_semantics": "exact_with_censoring",
            "exact_ranks": [1, 17],
        },
    )
    _write_json(root / "submission.json", submission.to_dict())
    return {
        "descriptor": descriptor,
        "report": report,
        "bundle": bundle,
        "submission": submission,
    }


def _rewrite_manifest(root: Path, mutate: Any) -> None:
    path = root / "submission.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    _write_json(path, with_content_sha256(value))


def _apply_negative(root: Path, mutation: str) -> None:
    if mutation == "missing_file":
        (root / "contracts" / "dataset_profile.json").unlink()
    elif mutation == "hash_tamper":
        path = root / "contracts" / "dataset_profile.json"
        path.write_bytes(path.read_bytes() + b"\n")
    elif mutation == "profile_mismatch":
        _rewrite_manifest(root, lambda value: value["claims"].update({"profile_id": "overlay"}))
    elif mutation == "dataset_binding_mismatch":
        _rewrite_manifest(
            root,
            lambda value: value["claims"].update({"dataset_identity_sha256": "f" * 64}),
        )
    elif mutation == "unsupported_exact_rank":
        _rewrite_manifest(root, lambda value: value["claims"].update({"exact_ranks": [101]}))
    elif mutation == "private_path":
        def private_path(value: dict[str, Any]) -> None:
            value["artifacts"][0]["path"] = (
                "/" + "Users" + "/" + "private" + "/evidence.json"
            )
        _rewrite_manifest(root, private_path)
    elif mutation == "path_escape":
        def path_escape(value: dict[str, Any]) -> None:
            value["artifacts"][0]["path"] = "../outside.json"
        _rewrite_manifest(root, path_escape)
    elif mutation == "unknown_artifact_role":
        def unknown_role(value: dict[str, Any]) -> None:
            value["artifacts"][0]["role"] = "project_specific_blob"
        _rewrite_manifest(root, unknown_role)
    elif mutation == "duplicate_artifact":
        def duplicate(value: dict[str, Any]) -> None:
            value["artifacts"].append(copy.deepcopy(value["artifacts"][0]))
            value["artifacts"].sort(key=lambda row: row["artifact_id"])
        _rewrite_manifest(root, duplicate)
    else:
        raise AssertionError(mutation)


def test_external_adapter_submission_onboards_without_project_verifier(tmp_path: Path) -> None:
    _build_package(tmp_path)
    validated = validate_submission_package(tmp_path)
    assert validated.evidence_bundle.subject["adapter_id"] == "external-parallel"
    report = check_submission(tmp_path)
    assert report.status == "accepted"
    assert report.bindings is not None
    profile = next(item for item in load_profile_catalog() if item.profile_kind == "generator")
    assert report.bindings["status_label"] == profile.status_label_policy["pass"]
    assert validate_submission_check_report(report.to_dict()) == report
    assert check_submission(tmp_path).to_dict() == report.to_dict()
    checked_in = validate_submission_package(POSITIVE_PACKAGE)
    assert checked_in.evidence_bundle.content_sha256 == validated.evidence_bundle.content_sha256
    for relative in (
        "submission.json",
        "contracts/dataset_profile.json",
        "reports/conformance.json",
        "evidence/bundle.json",
    ):
        assert (POSITIVE_PACKAGE / relative).read_bytes() == (tmp_path / relative).read_bytes()


def test_every_registered_negative_package_is_rejected(tmp_path: Path) -> None:
    inventory = json.loads(NEGATIVE_INVENTORY.read_text(encoding="utf-8"))
    assert inventory["schema"] == "sidscope.submission_negative_inventory.v1"
    observed = []
    for row in inventory["cases"]:
        package = tmp_path / row["case_id"]
        _build_package(package)
        _apply_negative(package, row["mutation"])
        report = check_submission(package)
        assert report.status == "rejected", row["case_id"]
        assert report.bindings is None
        assert [failure["code"] for failure in report.failures] == [row["expected_failure"]]
        observed.append(row["case_id"])
    assert observed == sorted(observed)


def test_symlink_and_forbidden_content_are_rejected(tmp_path: Path) -> None:
    package = tmp_path / "symlink"
    _build_package(package)
    descriptor = package / "contracts" / "dataset_profile.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(descriptor.read_bytes())
    descriptor.unlink()
    descriptor.symlink_to(outside)
    report = check_submission(package)
    assert report.failures[0]["code"] == "submission_symlink_forbidden"

    leaked = tmp_path / "leaked"
    _build_package(leaked)
    report_path = leaked / "reports" / "conformance.json"
    value = json.loads(report_path.read_text(encoding="utf-8"))
    value["producer"]["name"] = (
        "/" + "Users" + "/" + "private" + "/checkpoint/run"
    )
    _write_json(report_path, with_content_sha256(value))
    # The manifest hash is updated so privacy scanning, not hash mismatch, is decisive.
    _rewrite_manifest(
        leaked,
        lambda manifest: next(
            row for row in manifest["artifacts"] if row["role"] == "profile_conformance_report"
        ).update({"sha256": _sha(report_path.read_bytes())}),
    )
    privacy_report = check_submission(leaked)
    assert privacy_report.failures[0]["code"] == "private_path_exposure"
    assert "/" + "Users" + "/" not in json.dumps(privacy_report.to_dict())


def test_status_and_result_indexes_are_rebuild_deterministic(tmp_path: Path) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    _build_package(left_root, adapter_id="external-a", hit=0.2)
    _build_package(right_root, adapter_id="external-b", partial=True, hit=0.3)
    left = validate_submission_package(left_root)
    right = validate_submission_package(right_root)
    first_status, first_result = generate_submission_indexes([right, left])
    second_status, second_result = generate_submission_indexes([left, right])
    assert canonical_index_bytes(first_status) == canonical_index_bytes(second_status)
    assert canonical_index_bytes(first_result) == canonical_index_bytes(second_result)
    assert [row["adapter_id"] for row in first_status["entries"]] == ["external-a", "external-b"]
    profile = next(item for item in load_profile_catalog() if item.profile_kind == "generator")
    assert first_status["entries"][1]["status_label"] == profile.status_label_policy["partial"]
    assert first_result["entries"][1]["result_card"]["overall_metrics"]["hit_at_10"] == 0.3
    rendered = canonical_index_bytes(first_status) + canonical_index_bytes(first_result)
    assert str(tmp_path).encode() not in rendered
    assert b"timestamp" not in rendered


def test_superseded_submission_is_not_active_and_legacy_is_comparison_only(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    corrected_root = tmp_path / "corrected"
    first_built = _build_package(first_root, adapter_id="external-a", hit=0.1)
    first = validate_submission_package(first_root)
    _build_package(
        corrected_root,
        adapter_id="external-a",
        hit=0.4,
        supersedes=[first_built["bundle"].content_sha256],
    )
    corrected = validate_submission_package(corrected_root)
    status_index, result_index = generate_submission_indexes([first, corrected])
    assert len(status_index["entries"]) == 1
    assert status_index["entries"][0]["evidence_bundle_sha256"] == corrected.evidence_bundle.content_sha256
    assert result_index["entries"][0]["result_card"]["overall_metrics"]["hit_at_10"] == 0.4

    parity = legacy_status_parity(
        status_index,
        [
            {
                "adapter_id": "external-a",
                "status": "named_adapter",
                "path": "/" + "private" + "/old",
            }
        ],
    )
    assert parity["status"] == "pass"
    assert parity["authority"] == "profile_conformance_reports"
    assert "path" not in json.dumps(parity)
    mismatch = legacy_status_parity(
        status_index,
        [{"adapter_id": "external-a", "status_label": "fixture_only"}],
    )
    assert mismatch["status"] == "mismatch"
    assert mismatch["differences"][0]["generated_status_label"] == "named_adapter"
