"""Deterministic evidence indexes, immutable bundles, and derived registries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sidinspector.contracts import (
    ContractRegistryError,
    load_contract_registry,
    load_registered_contract,
    validate_evidence_index,
    with_content_sha256,
)

from .bundle import (
    EVIDENCE_BUNDLE_SCHEMA,
    EVIDENCE_BUNDLE_SCHEMA_REVISION,
    EvidenceBundle,
    EvidenceBundleValidationError,
    build_evidence_bundle,
    load_evidence_bundle,
    scan_evidence_content,
    validate_evidence_bundle,
)
from .comparison import compare_evidence_bundles
from .object_store import ObjectStore
from .registry import EvidenceRegistry, EvidenceRegistryError


def build_evidence_index(
    artifact_paths: Sequence[Path], *, index_id: str
) -> dict[str, Any]:
    registry = load_contract_registry()
    loaded: dict[str, tuple[Any, Any]] = {}
    for path in artifact_paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ContractRegistryError("invalid_type", str(path))
        descriptor = registry.by_schema_id(str(raw.get("schema")))
        if descriptor.contract_type == "evidence-index":
            raise ContractRegistryError("recursive_evidence_index", str(path))
        if descriptor.schema_id in loaded:
            raise ContractRegistryError("duplicate_evidence_schema", descriptor.schema_id)
        _, artifact = load_registered_contract(descriptor.contract_type, path)
        loaded[descriptor.schema_id] = (descriptor, artifact)

    artifacts = []
    artifact_id_by_schema: dict[str, str] = {}
    for schema_id, (descriptor, artifact) in loaded.items():
        artifact_id = f"{descriptor.contract_type}:{artifact.to_dict()[descriptor.result_id_field]}"
        artifact_id_by_schema[schema_id] = artifact_id
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "role": descriptor.contract_type,
                "schema_id": schema_id,
                "schema_revision": artifact.schema_revision,
                "content_sha256": artifact.content_sha256,
            }
        )
    artifacts.sort(key=lambda row: row["artifact_id"])
    edges = []
    for schema_id, (descriptor, _) in loaded.items():
        for dependency in descriptor.dependencies:
            if dependency.schema_id not in loaded:
                raise ContractRegistryError(
                    "missing_evidence_dependency",
                    f"{schema_id} requires {dependency.schema_id}",
                )
            edges.append(
                {
                    "from_artifact": artifact_id_by_schema[schema_id],
                    "to_artifact": artifact_id_by_schema[dependency.schema_id],
                    "relation": f"depends_on:{dependency.schema_id}",
                }
            )
    edges.sort(key=lambda row: (row["from_artifact"], row["to_artifact"], row["relation"]))
    document = with_content_sha256(
        {
            "schema": "sidscope.evidence_index.v1",
            "schema_revision": "1.0.0",
            "evidence_index_id": index_id,
            "producer": {"name": "sidinspector.evidence", "version": "1.2.0.dev0"},
            "artifacts": artifacts,
            "edges": edges,
            "omissions": [],
            "privacy": {
                "source_user_ids_exported": False,
                "source_item_ids_exported": False,
                "absolute_private_paths_exported": False,
            },
        }
    )
    validate_evidence_index(document)
    return document


__all__ = [
    "EVIDENCE_BUNDLE_SCHEMA",
    "EVIDENCE_BUNDLE_SCHEMA_REVISION",
    "EvidenceBundle",
    "EvidenceBundleValidationError",
    "EvidenceRegistry",
    "EvidenceRegistryError",
    "ObjectStore",
    "build_evidence_bundle",
    "build_evidence_index",
    "compare_evidence_bundles",
    "load_evidence_bundle",
    "scan_evidence_content",
    "validate_evidence_bundle",
]
