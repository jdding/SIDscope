"""Canonical SIDScope contracts introduced by the 1.2 migration facade."""

from .hashing import (
    canonical_artifact_sha256,
    canonical_json_bytes,
    canonical_sha256,
    verify_content_sha256,
    with_content_sha256,
)
from .source_identity import (
    SOURCE_IDENTITY_SCHEMA,
    SOURCE_IDENTITY_SCHEMA_REVISION,
    SourceIdentity,
    SourceIdentityValidationError,
    from_legacy_adapter_manifest,
    load_source_identity,
    source_identity_schema_path,
    validate_source_identity,
)

__all__ = [
    "SOURCE_IDENTITY_SCHEMA",
    "SOURCE_IDENTITY_SCHEMA_REVISION",
    "SourceIdentity",
    "SourceIdentityValidationError",
    "canonical_artifact_sha256",
    "canonical_json_bytes",
    "canonical_sha256",
    "from_legacy_adapter_manifest",
    "load_source_identity",
    "source_identity_schema_path",
    "validate_source_identity",
    "verify_content_sha256",
    "with_content_sha256",
]
