from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from sidinspector.contracts.hashing import canonical_json_bytes, with_content_sha256
from sidinspector.evidence.bundle import (
    EvidenceBundle,
    EvidenceBundleValidationError,
    build_evidence_bundle,
    load_evidence_bundle,
    validate_evidence_bundle,
)
from sidinspector.evidence.object_store import ObjectStore


PUBLIC_PAYLOAD = b'{"decision":"pass"}'
PUBLIC_SHA = hashlib.sha256(PUBLIC_PAYLOAD).hexdigest()
ROLES = ("source", "data", "sid", "run", "checkpoint", "trace", "diagnostics", "conformance")


def _artifacts(*, public_payload: bytes = PUBLIC_PAYLOAD) -> list[dict[str, object]]:
    public_sha = hashlib.sha256(public_payload).hexdigest()
    rows: list[dict[str, object]] = []
    for index, role in enumerate(ROLES):
        content_digest = f"{index + 1:064x}"
        object_digest = public_sha if role == "conformance" else f"{index + 11:064x}"
        rows.append(
            {
                "artifact_id": f"artifact:{index}:{role}",
                "role": role,
                "schema_id": f"sidscope.{role}.v1",
                "schema_revision": "1.0.0",
                "content_sha256": content_digest,
                "object_sha256": object_digest,
                "size_bytes": len(public_payload) if role == "conformance" else 100 + index,
                "media_type": "application/json",
                "availability": "embedded_public" if role == "conformance" else "hash_reference_only",
            }
        )
    return rows


def _edges() -> list[dict[str, str]]:
    return [
        {
            "from_artifact": f"artifact:{index}:{ROLES[index]}",
            "to_artifact": f"artifact:{index + 1}:{ROLES[index + 1]}",
            "relation": "produces",
        }
        for index in range(len(ROLES) - 1)
    ]


def _bundle(
    *,
    public_payload: bytes = PUBLIC_PAYLOAD,
    rank_semantics: str = "exact_with_censoring",
) -> EvidenceBundle:
    artifacts = _artifacts(public_payload=public_payload)
    cutoff_only = rank_semantics == "cutoff_only"
    return build_evidence_bundle(
        bundle_id="fixture:beauty:rpg",
        producer={"name": "sidinspector.evidence", "version": "1.4.0.dev0"},
        profile_binding={
            "profile_id": "trained-generator",
            "profile_revision": "1.0.0",
            "conformance_report_sha256": artifacts[-1]["content_sha256"],
        },
        subject={"adapter_id": "rpg", "method_family": "parallel_graph_token_set"},
        compatibility={
            "dataset_identity_sha256": "a" * 64,
            "target_universe_sha256": "b" * 64,
            "evaluation_cutoff": 10,
            "publication_depth": 10 if cutoff_only else 100,
            "rank_semantics": rank_semantics,
        },
        artifacts=artifacts,
        provenance_edges=_edges(),
        result_card={
            "overall_metrics": {"hit_at_10": 0.2, "ndcg_at_10": 0.1},
            "slice_metrics": {"gap_gt_365d": {"hit_at_10": 0.0}},
            "failure_counts": {"generation_search_miss": 2, "success": 1},
            "compute": {"nfe": 12, "latency_ms": 4.5},
            "rank_observations": {
                "exact_count": 0 if cutoff_only else 2,
                "censored_count": 3 if cutoff_only else 1,
                "exact_ranks": [] if cutoff_only else [1, 11],
            },
        },
    )


def _rebind(document: dict[str, object]) -> dict[str, object]:
    return with_content_sha256(document)


def test_builder_is_deterministic_and_deep_copying() -> None:
    first = _bundle()
    document = first.to_dict()
    rebuilt = build_evidence_bundle(
        bundle_id=document["bundle_id"],
        producer=document["producer"],
        profile_binding=document["profile_binding"],
        subject=document["subject"],
        compatibility=document["compatibility"],
        artifacts=list(reversed(document["artifacts"])),
        provenance_edges=list(reversed(document["provenance_edges"])),
        result_card=document["result_card"],
        supersedes=document["supersedes"],
        privacy=document["privacy"],
    )
    assert rebuilt.content_sha256 == first.content_sha256
    assert rebuilt.to_dict() == first.to_dict()
    document["subject"]["adapter_id"] = "mutated"
    assert first.subject["adapter_id"] == "rpg"


def test_load_and_content_hash_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "bundle.json"
    bundle = _bundle()
    path.write_bytes(canonical_json_bytes(bundle.to_dict()) + b"\n")
    assert load_evidence_bundle(path).content_sha256 == bundle.content_sha256
    changed = bundle.to_dict()
    changed["result_card"]["overall_metrics"]["hit_at_10"] = 0.9
    with pytest.raises(EvidenceBundleValidationError) as captured:
        validate_evidence_bundle(changed)
    assert captured.value.code == "content_hash_mismatch"


def test_store_admission_verify_iter_and_atomic_idempotence(tmp_path: Path) -> None:
    bundle = _bundle()
    store = ObjectStore(tmp_path / "store")
    path = store.admit_bundle(bundle, {PUBLIC_SHA: PUBLIC_PAYLOAD})
    assert path == store.bundle_path(bundle.content_sha256)
    first_bytes = path.read_bytes()
    assert first_bytes == canonical_json_bytes(bundle.to_dict()) + b"\n"
    assert store.object_path(PUBLIC_SHA).read_bytes() == PUBLIC_PAYLOAD
    assert store.verify_bundle(bundle.content_sha256).bundle_id == bundle.bundle_id
    assert [item.content_sha256 for item in store.iter_bundles()] == [bundle.content_sha256]

    # Re-admission is byte-identical and leaves no staging files behind.
    assert store.admit_bundle(bundle, {PUBLIC_SHA: PUBLIC_PAYLOAD}) == path
    assert path.read_bytes() == first_bytes
    assert not list(path.parent.glob("*.tmp"))
    # Referenced checkpoint/source objects are intentionally absent.
    referenced = next(row for row in bundle.artifacts if row["role"] == "checkpoint")
    assert not store.object_path(referenced["object_sha256"]).exists()


def test_missing_or_mismatched_public_artifact_fails_closed(tmp_path: Path) -> None:
    bundle = _bundle()
    store = ObjectStore(tmp_path / "store")
    with pytest.raises(EvidenceBundleValidationError) as missing:
        store.admit_bundle(bundle)
    assert missing.value.code == "missing_public_artifact"

    with pytest.raises(EvidenceBundleValidationError) as mismatch:
        store.admit_bundle(bundle, {PUBLIC_SHA: b"different"})
    assert mismatch.value.code == "artifact_hash_mismatch"

    reference = next(row for row in bundle.artifacts if row["role"] == "checkpoint")
    with pytest.raises(EvidenceBundleValidationError) as unexpected:
        store.admit_bundle(
            bundle,
            {PUBLIC_SHA: PUBLIC_PAYLOAD, reference["object_sha256"]: b"private checkpoint"},
        )
    assert unexpected.value.code == "unexpected_public_artifact"


def test_stored_object_and_bundle_tamper_are_detected(tmp_path: Path) -> None:
    bundle = _bundle()
    store = ObjectStore(tmp_path / "store")
    store.admit_bundle(bundle, {PUBLIC_SHA: PUBLIC_PAYLOAD})
    store.object_path(PUBLIC_SHA).write_bytes(b"tampered")
    with pytest.raises(EvidenceBundleValidationError) as object_tamper:
        store.verify_bundle(bundle.content_sha256)
    assert object_tamper.value.code == "stored_artifact_tamper"

    # Restore the object, then alter only JSON whitespace: the semantic hash is
    # unchanged but canonical on-disk bytes are required.
    store.object_path(PUBLIC_SHA).write_bytes(PUBLIC_PAYLOAD)
    bundle_path = store.bundle_path(bundle.content_sha256)
    bundle_path.write_text(json.dumps(bundle.to_dict(), indent=2), encoding="utf-8")
    with pytest.raises(EvidenceBundleValidationError) as storage_tamper:
        store.load_bundle(bundle.content_sha256)
    assert storage_tamper.value.code == "noncanonical_bundle_storage"
    with pytest.raises(EvidenceBundleValidationError) as collision:
        store.admit_bundle(bundle, {PUBLIC_SHA: PUBLIC_PAYLOAD})
    assert collision.value.code == "bundle_collision_or_tamper"


def test_bundle_privacy_private_path_and_secret_fail_closed() -> None:
    for mutation, code in (
        (lambda doc: doc["result_card"]["failure_counts"].update({"source_user_id": 1}), "forbidden_field"),
        (
            lambda doc: doc["producer"].update(
                {"name": "/" + "Users" + "/person/" + "private" + "/run"}
            ),
            "private_path_exposure",
        ),
        (
            lambda doc: doc["producer"].update({"name": "pass" + "word=hunter2"}),
            "credential_exposure",
        ),
        (lambda doc: doc["privacy"].update({"checkpoint_payload_exported": True}), "privacy_boundary_violation"),
    ):
        document = _bundle().to_dict()
        mutation(document)
        with pytest.raises(EvidenceBundleValidationError) as captured:
            validate_evidence_bundle(_rebind(document))
        assert captured.value.code == code


def test_public_json_identity_leak_is_rejected_at_admission(tmp_path: Path) -> None:
    payload = b'{"source_item_id":"raw-17"}'
    bundle = _bundle(public_payload=payload)
    digest = hashlib.sha256(payload).hexdigest()
    with pytest.raises(EvidenceBundleValidationError) as captured:
        ObjectStore(tmp_path / "store").admit_bundle(bundle, {digest: payload})
    assert captured.value.code == "forbidden_field"


@pytest.mark.parametrize("payload,reason", [
    (('{"note":"/' + 'Users/person/pri' + 'vate/run' + '","note":"public"}').encode(), "duplicate_json_key"),
    (b'{"note":{"label":"secret","label":"public"}}', "duplicate_json_key"),
    (b'{"value":NaN}', "nonfinite_json_number"),
    (b'[' * 65 + b'0' + b']' * 65, "json_depth_exceeded"),
    (b'{"value":"\xff"}', "invalid_json_input"),
])
def test_public_json_strict_scan_before_any_publication(tmp_path, payload, reason):
    bundle = _bundle(public_payload=payload)
    digest = hashlib.sha256(payload).hexdigest()
    store = ObjectStore(tmp_path / "store")
    with pytest.raises(EvidenceBundleValidationError) as error:
        store.admit_bundle(bundle, {digest: payload})
    assert error.value.code == "invalid_public_json"
    assert reason in str(error.value)
    assert not store.root.exists()
    # Legacy stored bytes must be rescanned too, not grandfathered by hashes.
    store.bundle_path(bundle.content_sha256).parent.mkdir(parents=True)
    store.bundle_path(bundle.content_sha256).write_bytes(store._bundle_bytes(bundle))
    store.object_path(digest).parent.mkdir(parents=True)
    store.object_path(digest).write_bytes(payload)
    with pytest.raises(EvidenceBundleValidationError, match="invalid_public_json"):
        store.verify_bundle(bundle.content_sha256)


def test_public_json_pretty_safe_payload_remains_accepted(tmp_path):
    payload = b'{\n  "note": "public", "value": 1.25\n}\n'
    bundle = _bundle(public_payload=payload)
    store = ObjectStore(tmp_path / "store")
    store.admit_bundle(bundle, {hashlib.sha256(payload).hexdigest(): payload})
    assert store.verify_bundle(bundle.content_sha256) == bundle


def test_provenance_cycle_and_disconnected_chain_fail_closed() -> None:
    cycle = _bundle().to_dict()
    cycle["provenance_edges"].append(
        {
            "from_artifact": "artifact:7:conformance",
            "to_artifact": "artifact:0:source",
            "relation": "invalid-cycle",
        }
    )
    cycle["provenance_edges"].sort(
        key=lambda row: (row["from_artifact"], row["to_artifact"], row["relation"])
    )
    with pytest.raises(EvidenceBundleValidationError) as captured_cycle:
        validate_evidence_bundle(_rebind(cycle))
    assert captured_cycle.value.code == "provenance_cycle"

    disconnected = _bundle().to_dict()
    disconnected["provenance_edges"] = disconnected["provenance_edges"][:-1]
    with pytest.raises(EvidenceBundleValidationError) as captured_disconnected:
        validate_evidence_bundle(_rebind(disconnected))
    assert captured_disconnected.value.code == "disconnected_provenance_chain"


def test_rank_claims_and_conformance_binding_fail_closed() -> None:
    too_deep = _bundle().to_dict()
    too_deep["result_card"]["rank_observations"]["exact_ranks"][-1] = 101
    with pytest.raises(EvidenceBundleValidationError) as rank:
        validate_evidence_bundle(_rebind(too_deep))
    assert rank.value.code == "unsupported_exact_rank_claim"

    count_mismatch = _bundle().to_dict()
    count_mismatch["result_card"]["rank_observations"]["exact_count"] = 1
    with pytest.raises(EvidenceBundleValidationError) as count:
        validate_evidence_bundle(_rebind(count_mismatch))
    assert count.value.code == "exact_rank_count_mismatch"

    cutoff_only = _bundle(rank_semantics="cutoff_only").to_dict()
    cutoff_only["result_card"]["rank_observations"].update(
        {"exact_count": 1, "censored_count": 2, "exact_ranks": [1]}
    )
    with pytest.raises(EvidenceBundleValidationError) as unsupported:
        validate_evidence_bundle(_rebind(cutoff_only))
    assert unsupported.value.code == "unsupported_exact_rank_claim"

    wrong_profile = _bundle().to_dict()
    wrong_profile["profile_binding"]["conformance_report_sha256"] = "c" * 64
    with pytest.raises(EvidenceBundleValidationError) as profile:
        validate_evidence_bundle(_rebind(wrong_profile))
    assert profile.value.code == "conformance_profile_binding_mismatch"


def test_supersession_and_quarantine_are_immutable(tmp_path: Path) -> None:
    first = _bundle()
    corrected_doc = first.to_dict()
    corrected_doc["bundle_id"] = "fixture:beauty:rpg:corrected"
    corrected_doc["result_card"]["overall_metrics"]["hit_at_10"] = 0.3
    corrected = build_evidence_bundle(
        bundle_id=corrected_doc["bundle_id"],
        producer=corrected_doc["producer"],
        profile_binding=corrected_doc["profile_binding"],
        subject=corrected_doc["subject"],
        compatibility=corrected_doc["compatibility"],
        artifacts=corrected_doc["artifacts"],
        provenance_edges=corrected_doc["provenance_edges"],
        result_card=corrected_doc["result_card"],
        supersedes=[first.content_sha256],
        privacy=corrected_doc["privacy"],
    )
    assert corrected.content_sha256 != first.content_sha256
    assert corrected.supersedes == (first.content_sha256,)

    store = ObjectStore(tmp_path / "store")
    with pytest.raises(EvidenceBundleValidationError) as missing_predecessor:
        store.admit_bundle(corrected, {PUBLIC_SHA: PUBLIC_PAYLOAD})
    assert missing_predecessor.value.code == "missing_superseded_bundle"
    store.admit_bundle(first, {PUBLIC_SHA: PUBLIC_PAYLOAD})
    quarantined = store.quarantine_bundle(first.content_sha256)
    store.admit_bundle(corrected, {PUBLIC_SHA: PUBLIC_PAYLOAD})
    assert quarantined.read_bytes() == canonical_json_bytes(first.to_dict()) + b"\n"
    assert not store.bundle_path(first.content_sha256).exists()
    with pytest.raises(EvidenceBundleValidationError) as missing:
        store.load_bundle(first.content_sha256)
    assert missing.value.code == "bundle_not_found"
    assert [bundle.content_sha256 for bundle in store.iter_quarantined_bundles()] == [
        first.content_sha256
    ]
