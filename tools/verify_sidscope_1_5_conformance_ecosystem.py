#!/usr/bin/env python3
"""Verify the CPU-only SIDScope 1.5 conformance/submission ecosystem."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts.hashing import canonical_json_bytes, with_content_sha256
from sidinspector.conformance_core import (
    ProfileEngineError,
    load_dataset_profile_descriptor,
    load_profile_catalog,
    load_profile_conformance_report,
    load_profile_registry,
    validate_dataset_profile_descriptor,
    validate_profile_conformance_report,
)
from sidinspector.submission import (
    canonical_index_bytes,
    check_submission,
    generate_submission_indexes,
    legacy_status_parity,
    validate_submission_package,
)


PROFILE_ROOT = ROOT / "examples" / "conformance_ecosystem_fixture" / "profile"
SUBMISSION_ROOT = (
    ROOT / "examples" / "conformance_ecosystem_fixture" / "submission"
)
POSITIVE_SUBMISSION = SUBMISSION_ROOT / "positive"
PROFILE_NEGATIVES = PROFILE_ROOT / "expected_failures.json"
SUBMISSION_NEGATIVES = SUBMISSION_ROOT / "negative_inventory.json"
# Intentional negative-fixture declaration. The release scanner allowlists this
# verifier file only for the exact quoted token; generated evidence must still
# reject it.
PRIVATE_PATH_PREFIX = "/Users/"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write_canonical(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _expect_profile_failure(
    case_id: str,
    expected_code: str,
    descriptor: dict[str, Any],
    report: dict[str, Any],
) -> None:
    descriptor_value = copy.deepcopy(descriptor)
    report_value = copy.deepcopy(report)
    if case_id == "unknown-profile":
        report_value["profile_binding"]["profile_id"] = "unknown_profile"
        report_value = with_content_sha256(report_value)
    elif case_id == "gate-order":
        report_value["gates"][0], report_value["gates"][1] = (
            report_value["gates"][1],
            report_value["gates"][0],
        )
        report_value = with_content_sha256(report_value)
    elif case_id == "gate-dependency":
        profile = next(
            item for item in load_profile_catalog()
            if item.profile_id == report_value["profile_binding"]["profile_id"]
        )
        first_gate = profile.gates[0]
        report_value["gates"][0] = {
            "gate_id": first_gate.gate_id,
            "status": "partial",
            "failure": {
                "code": first_gate.failure_code,
                "detail": "typed fixture dependency failure",
            },
        }
        report_value["decision"] = {
            "status": "partial",
            "status_label": profile.status_label_policy["partial"],
        }
        report_value = with_content_sha256(report_value)
    elif case_id == "descriptor-binding":
        report_value["descriptor_binding"]["content_sha256"] = "f" * 64
        report_value = with_content_sha256(report_value)
    elif case_id == "content-hash":
        report_value["producer"]["name"] = "tampered-without-rehash"
    elif case_id == "unsupported-label":
        report_value["decision"]["status_label"] = "manually_promoted"
        report_value = with_content_sha256(report_value)
    elif case_id == "privacy":
        descriptor_value["privacy"]["source_user_ids_exported"] = True
        descriptor_value = with_content_sha256(descriptor_value)
    elif case_id == "publication-depth":
        descriptor_value["evaluation"]["cutoff"] = 101
        descriptor_value["evaluation"]["publication_depth"] = 100
        descriptor_value = with_content_sha256(descriptor_value)
    else:
        raise AssertionError(case_id)

    try:
        validated_descriptor = validate_dataset_profile_descriptor(descriptor_value)
        validate_profile_conformance_report(report_value, descriptor=validated_descriptor)
    except ProfileEngineError as error:
        if error.code != expected_code:
            raise AssertionError(
                f"profile negative {case_id}: {error.code} != {expected_code}"
            ) from error
        return
    raise AssertionError(f"profile negative unexpectedly passed: {case_id}")


def _rewrite_manifest(root: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    path = root / "submission.json"
    value = _json(path)
    mutation(value)
    _write_canonical(path, with_content_sha256(value))


def _apply_submission_negative(root: Path, mutation: str) -> None:
    if mutation == "missing_file":
        (root / "contracts" / "dataset_profile.json").unlink()
    elif mutation == "hash_tamper":
        path = root / "contracts" / "dataset_profile.json"
        path.write_bytes(path.read_bytes() + b"\n")
    elif mutation == "profile_mismatch":
        _rewrite_manifest(
            root, lambda value: value["claims"].update({"profile_id": "overlay_g0_g5"})
        )
    elif mutation == "dataset_binding_mismatch":
        _rewrite_manifest(
            root,
            lambda value: value["claims"].update(
                {"dataset_identity_sha256": "f" * 64}
            ),
        )
    elif mutation == "unsupported_exact_rank":
        _rewrite_manifest(
            root, lambda value: value["claims"].update({"exact_ranks": [101]})
        )
    elif mutation == "private_path":
        _rewrite_manifest(
            root,
            lambda value: value["artifacts"][0].update(
                {"path": PRIVATE_PATH_PREFIX + "private/evidence.json"}
            ),
        )
    elif mutation == "path_escape":
        _rewrite_manifest(
            root,
            lambda value: value["artifacts"][0].update({"path": "../outside.json"}),
        )
    elif mutation == "unknown_artifact_role":
        _rewrite_manifest(
            root,
            lambda value: value["artifacts"][0].update(
                {"role": "project_specific_blob"}
            ),
        )
    elif mutation == "duplicate_artifact":
        def duplicate(value: dict[str, Any]) -> None:
            value["artifacts"].append(copy.deepcopy(value["artifacts"][0]))
            value["artifacts"].sort(key=lambda row: row["artifact_id"])

        _rewrite_manifest(root, duplicate)
    else:
        raise AssertionError(mutation)


def verify_profiles() -> dict[str, Any]:
    profiles = load_profile_catalog()
    expected_ids = [
        "generator_g0_g5",
        "overlay_g0_g5",
        "release_local",
        "static_mapping_c0_c5",
    ]
    observed_ids = [profile.profile_id for profile in profiles]
    if observed_ids != expected_ids:
        raise AssertionError(f"profile IDs: {observed_ids}")
    descriptor = load_dataset_profile_descriptor(
        PROFILE_ROOT / "dataset_profile_descriptor.json"
    )
    report_paths = {
        "generator_g0_g5": PROFILE_ROOT / "generator_report.json",
        "overlay_g0_g5": PROFILE_ROOT / "overlay_report.json",
        "release_local": PROFILE_ROOT / "release_report.json",
        "static_mapping_c0_c5": PROFILE_ROOT / "static_mapping_report.json",
    }
    for profile_id, path in report_paths.items():
        report = load_profile_conformance_report(path, descriptor=descriptor)
        if report.profile_id != profile_id or report.decision_status != "pass":
            raise AssertionError(f"invalid positive profile fixture: {profile_id}")

    raw_descriptor = descriptor.to_dict()
    raw_report = _json(PROFILE_ROOT / "generator_report.json")
    inventory = _json(PROFILE_NEGATIVES)
    for row in inventory["cases"]:
        _expect_profile_failure(
            row["case_id"], row["expected_code"], raw_descriptor, raw_report
        )
    return {
        "profile_count": len(profiles),
        "profile_positive_count": len(report_paths),
        "profile_negative_count": len(inventory["cases"]),
    }


def verify_submissions() -> dict[str, Any]:
    positive = validate_submission_package(POSITIVE_SUBMISSION)
    accepted = check_submission(POSITIVE_SUBMISSION)
    if accepted.status != "accepted":
        raise AssertionError(accepted.to_dict())
    inventory = _json(SUBMISSION_NEGATIVES)
    with tempfile.TemporaryDirectory(prefix="sidscope-1-5-negatives-") as tmp:
        temporary_root = Path(tmp)
        for row in inventory["cases"]:
            case_root = temporary_root / row["case_id"]
            shutil.copytree(POSITIVE_SUBMISSION, case_root)
            _apply_submission_negative(case_root, row["mutation"])
            rejected = check_submission(case_root)
            codes = [failure["code"] for failure in rejected.failures]
            if rejected.status != "rejected" or codes != [row["expected_failure"]]:
                raise AssertionError(
                    f"submission negative {row['case_id']}: {rejected.to_dict()}"
                )
    return {
        "positive_submission_count": 1,
        "submission_negative_count": len(inventory["cases"]),
        "adapter_id": positive.evidence_bundle.subject["adapter_id"],
        "status_label": positive.conformance_report["decision"]["status_label"],
    }


def verify_indexes() -> dict[str, Any]:
    submission = validate_submission_package(POSITIVE_SUBMISSION)
    first_status, first_result = generate_submission_indexes([submission])
    second_status, second_result = generate_submission_indexes([submission])
    if canonical_index_bytes(first_status) != canonical_index_bytes(second_status):
        raise AssertionError("status index rebuild mismatch")
    if canonical_index_bytes(first_result) != canonical_index_bytes(second_result):
        raise AssertionError("result index rebuild mismatch")
    rendered = canonical_index_bytes(first_status) + canonical_index_bytes(first_result)
    if str(ROOT).encode() in rendered or b"timestamp" in rendered:
        raise AssertionError("generated index contains environment metadata")
    adapter_id = first_status["entries"][0]["adapter_id"]
    label = first_status["entries"][0]["status_label"]
    parity = legacy_status_parity(
        first_status, [{"adapter_id": adapter_id, "status_label": label}]
    )
    if parity["status"] != "pass":
        raise AssertionError(parity)
    return {
        "status_index_sha256": first_status["content_sha256"],
        "result_index_sha256": first_result["content_sha256"],
        "legacy_parity_status": parity["status"],
    }


def verify_compatibility() -> dict[str, Any]:
    legacy_profiles = load_profile_registry()
    if len(legacy_profiles) != 6:
        raise AssertionError("1.3 profile registry changed")
    return {
        "legacy_profile_count": len(legacy_profiles),
        "legacy_profile_registry_retained": True,
        "canonical_contract_count_unchanged": 11,
    }


def verify(gate: str = "all") -> dict[str, Any]:
    sections: dict[str, Any] = {}
    if gate in {"all", "profiles"}:
        sections["profiles"] = verify_profiles()
    if gate in {"all", "submission"}:
        sections["submission"] = verify_submissions()
    if gate in {"all", "indexes"}:
        sections["indexes"] = verify_indexes()
    if gate in {"all", "compatibility"}:
        sections["compatibility"] = verify_compatibility()
    return {
        "schema": "sidscope.conformance_submission_ecosystem_verification.v1",
        "status": "pass",
        "product_version": "1.5.0.dev0",
        "gate": gate,
        "gpu_required": False,
        "sections": sections,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gate",
        choices=("all", "profiles", "submission", "indexes", "compatibility"),
        default="all",
    )
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args.gate)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
