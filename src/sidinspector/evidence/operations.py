"""Application operations over the content-addressed store and its registry.

Shared by the CLI and package API so a business judgement has one authority.
The CAS stays authoritative and the SQLite projection disposable: compare
verifies active state and CAS contents before consulting the projection,
invalid quarantine reasons are rejected before any persistent write, and a
CAS quarantine whose index update fails stays quarantined behind a typed
failure until rebuild reconciles. Operations return data or raise typed
errors; they never print or exit.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

from sidinspector.contracts import bounded_bytes
from sidinspector.evidence.bundle import (
    EvidenceBundle,
    EvidenceBundleValidationError,
)
from sidinspector.evidence.comparison import compare_evidence_bundles
from sidinspector.evidence.object_store import ObjectStore
from sidinspector.evidence.registry import EvidenceRegistry, EvidenceRegistryError

__all__ = [
    "active_bundle_document",
    "compare_active_bundles",
    "order_bundles_for_admission",
    "parse_supplied_artifacts",
    "quarantine_bundle",
    "rebuild_registry",
    "register_bundles",
    "supersede_bundle",
]


def parse_supplied_artifacts(values: Sequence[str]) -> dict[str, Path]:
    """Parse SHA256=PATH artifact arguments into a digest-keyed map."""
    result: dict[str, Path] = {}
    for value in values:
        digest, separator, raw_path = value.partition("=")
        if not separator or not digest or not raw_path:
            raise EvidenceBundleValidationError(
                "invalid_artifact_argument", "expected SHA256=PATH"
            )
        if digest in result:
            raise EvidenceBundleValidationError("duplicate_artifact_argument", digest)
        result[digest] = Path(raw_path)
    return result


def order_bundles_for_admission(store: ObjectStore, bundles: Sequence[EvidenceBundle]) -> list[EvidenceBundle]:
    available = {bundle.content_sha256 for bundle in store.iter_bundles()}
    remaining = {bundle.content_sha256: bundle for bundle in bundles}
    ordered: list[EvidenceBundle] = []
    while remaining:
        ready = sorted(
            digest
            for digest, bundle in remaining.items()
            if set(bundle.supersedes) <= available
        )
        if not ready:
            referenced = {
                predecessor
                for bundle in remaining.values()
                for predecessor in bundle.supersedes
            }
            missing = sorted(referenced - available - set(remaining))
            code = "missing_superseded_bundle" if missing else "supersession_cycle"
            raise EvidenceBundleValidationError(code, ",".join(missing or sorted(remaining)))
        for digest in ready:
            ordered.append(remaining.pop(digest))
            available.add(digest)
    return ordered


def register_bundles(
    store: ObjectStore,
    registry: EvidenceRegistry,
    bundles: Sequence[EvidenceBundle],
    supplied: Mapping[str, Path],
    *,
    operation: str,
) -> list[EvidenceBundle]:
    """Admit bundles to the CAS in supersession order, then project to the registry."""
    if operation not in {"add", "import"}:
        raise EvidenceRegistryError("invalid_registry_operation", operation)
    used_artifacts: set[str] = set()
    for bundle in order_bundles_for_admission(store, bundles):
        embedded = {
            str(row["object_sha256"])
            for row in bundle.artifacts
            if row["availability"] == "embedded_public"
        }
        selected = {digest: path for digest, path in supplied.items() if digest in embedded}
        used_artifacts.update(selected)
        store.admit_bundle(bundle, selected)
    unused = sorted(set(supplied) - used_artifacts)
    if unused:
        raise EvidenceBundleValidationError("unexpected_public_artifact", ",".join(unused))
    if operation == "import":
        registry.import_bundles(list(bundles))
    else:
        for bundle in bundles:
            registry.add(bundle)
    return list(bundles)


def supersede_bundle(
    store: ObjectStore,
    registry: EvidenceRegistry,
    bundle: EvidenceBundle,
    prior: str,
    supplied: Mapping[str, Path],
) -> dict[str, str]:
    if prior not in bundle.supersedes:
        raise EvidenceRegistryError("missing_supersession_declaration", prior)
    store.admit_bundle(bundle, dict(supplied))
    registry.add(bundle)
    return {"prior_bundle_sha256": prior, "replacement_bundle_sha256": bundle.content_sha256}


def active_bundle_document(store: ObjectStore, registry: EvidenceRegistry, digest: str) -> dict[str, Any]:
    projection = registry.show(digest, require_active=True)
    # CAS is authoritative even if an interrupted quarantine left
    # the disposable projection stale or the bundle was re-added.
    if store.quarantine_path(digest).exists():
        raise EvidenceRegistryError("bundle_quarantined", digest)
    document = store.verify_bundle(digest).to_dict()
    if projection != document:
        raise EvidenceRegistryError("registry_projection_mismatch", digest)
    return document


def _verification_objects(store: ObjectStore, bundle: Mapping[str, Any]) -> dict[str, bytes]:
    return {
        row["object_sha256"]: bounded_bytes(store.object_path(row["object_sha256"]))
        for row in bundle["artifacts"]
        if row["availability"] == "embedded_public"
        and row["role"] in {"evaluation_protocol", "selection", "trace", "diagnostics"}
    }


def compare_active_bundles(store: ObjectStore, registry: EvidenceRegistry, left: str, right: str) -> dict[str, Any]:
    left_bundle = active_bundle_document(store, registry, left)
    right_bundle = active_bundle_document(store, registry, right)
    return compare_evidence_bundles(
        left_bundle,
        right_bundle,
        left_objects=_verification_objects(store, left_bundle),
        right_objects=_verification_objects(store, right_bundle),
    )


def rebuild_registry(store: ObjectStore, registry: EvidenceRegistry) -> dict[str, int]:
    bundles = list(store.iter_bundles())
    quarantined = list(store.iter_quarantined_bundles())
    registry.rebuild([*bundles, *quarantined])
    for bundle in quarantined:
        registry.quarantine(bundle.content_sha256, reason="object_store_quarantine")
    return {"bundle_count": len(bundles) + len(quarantined), "quarantined_bundle_count": len(quarantined)}


def quarantine_bundle(store: ObjectStore, registry: EvidenceRegistry, digest: str, reason: str) -> None:
    if not reason.strip():
        raise EvidenceRegistryError("invalid_quarantine_reason", "reason is empty")
    registry.show(digest)
    store.quarantine_bundle(digest)
    try:
        registry.quarantine(digest, reason=reason)
    except (sqlite3.Error, OSError, EvidenceRegistryError) as exc:
        # Do not reactivate suspect evidence on a projection failure.
        # Rebuild derives the quarantine state from the durable CAS.
        raise EvidenceRegistryError(
            "quarantine_index_update_failed",
            "CAS remains quarantined; run registry rebuild to reconcile the index",
        ) from exc
