"""Deterministic JSON hashing for canonical SIDScope artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON-compatible data using the SIDScope canonical JSON v1 rules."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Hash an exact JSON value after canonical JSON v1 serialization."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_artifact_sha256(
    document: Mapping[str, Any], *, hash_field: str = "content_sha256"
) -> str:
    """Hash an artifact payload while excluding its top-level hash field.

    Excluding exactly one declared top-level field avoids self-referential hashes.
    Nested fields are never removed implicitly.
    """

    payload = dict(document)
    payload.pop(hash_field, None)
    return canonical_sha256(payload)


def with_content_sha256(
    document: Mapping[str, Any], *, hash_field: str = "content_sha256"
) -> dict[str, Any]:
    """Return a copy with a canonical, non-self-referential content hash."""

    result = dict(document)
    result[hash_field] = canonical_artifact_sha256(result, hash_field=hash_field)
    return result


def verify_content_sha256(
    document: Mapping[str, Any], *, hash_field: str = "content_sha256"
) -> bool:
    """Return whether an artifact contains a well-formed matching content hash."""

    observed = document.get(hash_field)
    return (
        isinstance(observed, str)
        and SHA256_PATTERN.fullmatch(observed) is not None
        and observed == canonical_artifact_sha256(document, hash_field=hash_field)
    )
