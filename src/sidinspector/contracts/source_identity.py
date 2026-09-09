"""Canonical SourceIdentity v1 model and fail-closed validator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Sequence

from .hashing import SHA256_PATTERN, verify_content_sha256, with_content_sha256


SOURCE_IDENTITY_SCHEMA = "sidscope.source_identity.v1"
SOURCE_IDENTITY_SCHEMA_REVISION = "1.0.0"
SOURCE_LICENSE_STATES = frozenset(
    {
        "licensed",
        "restricted_source_license",
        "source_licensed_artifact_boundary_unresolved",
        "no_license_detected",
    }
)
SOURCE_REVISION_KINDS = frozenset(
    {"git_commit", "content_sha256", "archive_digest", "other_immutable"}
)
SOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class SourceIdentityValidationError(ValueError):
    """Typed SourceIdentity validation failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ProducerIdentity:
    name: str
    version: str


@dataclass(frozen=True)
class PaperIdentity:
    title: str
    url: str | None


@dataclass(frozen=True)
class RepositoryIdentity:
    url: str
    revision_kind: str
    revision: str


@dataclass(frozen=True)
class LicenseIdentity:
    status: str
    identifier: str | None
    notices: tuple[str, ...]
    redistribution_policy: str


@dataclass(frozen=True)
class SourcePatchIdentity:
    path: str
    sha256: str
    purpose: str


@dataclass(frozen=True)
class SourceIdentity:
    schema: str
    schema_revision: str
    source_id: str
    producer: ProducerIdentity
    paper: PaperIdentity
    repository: RepositoryIdentity
    license: LicenseIdentity
    derivation: str
    artifact_name: str
    patches: tuple[SourcePatchIdentity, ...]
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_revision": self.schema_revision,
            "source_id": self.source_id,
            "producer": {
                "name": self.producer.name,
                "version": self.producer.version,
            },
            "paper": {"title": self.paper.title, "url": self.paper.url},
            "repository": {
                "url": self.repository.url,
                "revision_kind": self.repository.revision_kind,
                "revision": self.repository.revision,
            },
            "license": {
                "status": self.license.status,
                "identifier": self.license.identifier,
                "notices": list(self.license.notices),
                "redistribution_policy": self.license.redistribution_policy,
            },
            "derivation": self.derivation,
            "artifact_name": self.artifact_name,
            "patches": [
                {"path": patch.path, "sha256": patch.sha256, "purpose": patch.purpose}
                for patch in self.patches
            ],
            "content_sha256": self.content_sha256,
        }


def _fail(code: str, detail: str) -> None:
    raise SourceIdentityValidationError(code, detail)


def _object(parent: Mapping[str, Any], key: str, fields: set[str]) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{key} must be an object")
    unknown = sorted(set(value) - fields)
    if unknown:
        _fail("unknown_field", f"{key} contains unsupported fields: {unknown}")
    missing = sorted(fields - set(value))
    if missing:
        _fail("missing_field", f"{key} is missing fields: {missing}")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be a non-empty string")
    return value


def _https_url(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    text = _text(value, field)
    if not text.startswith("https://"):
        _fail("invalid_url", f"{field} must use https")
    return text


def _validate_revision(kind: str, revision: str) -> None:
    if kind not in SOURCE_REVISION_KINDS:
        _fail("unsupported_revision_kind", kind)
    if kind == "git_commit" and GIT_COMMIT_PATTERN.fullmatch(revision) is None:
        _fail("mutable_revision", "git_commit must be an exact 40-character lowercase SHA")
    if kind == "content_sha256" and SHA256_PATTERN.fullmatch(revision) is None:
        _fail("invalid_sha256", "content_sha256 revision must be lowercase SHA-256")


def validate_source_identity(value: Mapping[str, Any]) -> SourceIdentity:
    """Validate and parse one canonical SourceIdentity artifact."""

    if not isinstance(value, Mapping):
        _fail("invalid_type", "source identity must be an object")
    fields = {
        "schema",
        "schema_revision",
        "source_id",
        "producer",
        "paper",
        "repository",
        "license",
        "derivation",
        "artifact_name",
        "patches",
        "content_sha256",
    }
    unknown = sorted(set(value) - fields)
    if unknown:
        _fail("unknown_field", f"unsupported top-level fields: {unknown}")
    missing = sorted(fields - set(value))
    if missing:
        _fail("missing_field", f"missing top-level fields: {missing}")

    if value.get("schema") != SOURCE_IDENTITY_SCHEMA:
        _fail("schema_mismatch", f"schema must be {SOURCE_IDENTITY_SCHEMA}")
    if value.get("schema_revision") != SOURCE_IDENTITY_SCHEMA_REVISION:
        _fail(
            "schema_revision_mismatch",
            f"schema_revision must be {SOURCE_IDENTITY_SCHEMA_REVISION}",
        )

    source_id = _text(value.get("source_id"), "source_id")
    if SOURCE_ID_PATTERN.fullmatch(source_id) is None:
        _fail("invalid_source_id", source_id)

    producer_raw = _object(value, "producer", {"name", "version"})
    producer = ProducerIdentity(
        name=_text(producer_raw.get("name"), "producer.name"),
        version=_text(producer_raw.get("version"), "producer.version"),
    )

    paper_raw = _object(value, "paper", {"title", "url"})
    paper = PaperIdentity(
        title=_text(paper_raw.get("title"), "paper.title"),
        url=_https_url(paper_raw.get("url"), "paper.url", nullable=True),
    )

    repository_raw = _object(value, "repository", {"url", "revision_kind", "revision"})
    revision_kind = _text(repository_raw.get("revision_kind"), "repository.revision_kind")
    revision = _text(repository_raw.get("revision"), "repository.revision")
    _validate_revision(revision_kind, revision)
    repository = RepositoryIdentity(
        url=_https_url(repository_raw.get("url"), "repository.url") or "",
        revision_kind=revision_kind,
        revision=revision,
    )

    license_raw = _object(
        value,
        "license",
        {"status", "identifier", "notices", "redistribution_policy"},
    )
    license_status = _text(license_raw.get("status"), "license.status")
    if license_status not in SOURCE_LICENSE_STATES:
        _fail("unsupported_license_state", license_status)
    license_identifier = license_raw.get("identifier")
    if license_identifier is not None and not isinstance(license_identifier, str):
        _fail("invalid_type", "license.identifier must be a string or null")
    notices_raw = license_raw.get("notices")
    if not isinstance(notices_raw, Sequence) or isinstance(notices_raw, (str, bytes)):
        _fail("invalid_type", "license.notices must be an array of strings")
    notices = tuple(_text(notice, "license.notices[]") for notice in notices_raw)
    if list(notices) != sorted(set(notices)):
        _fail("noncanonical_order", "license.notices must be sorted and unique")
    license_identity = LicenseIdentity(
        status=license_status,
        identifier=license_identifier,
        notices=notices,
        redistribution_policy=_text(
            license_raw.get("redistribution_policy"),
            "license.redistribution_policy",
        ),
    )

    patches_raw = value.get("patches")
    if not isinstance(patches_raw, Sequence) or isinstance(patches_raw, (str, bytes)):
        _fail("invalid_type", "patches must be an array")
    patches: list[SourcePatchIdentity] = []
    for index, patch_raw in enumerate(patches_raw):
        if not isinstance(patch_raw, Mapping):
            _fail("invalid_type", f"patches[{index}] must be an object")
        unknown_patch = sorted(set(patch_raw) - {"path", "sha256", "purpose"})
        missing_patch = sorted({"path", "sha256", "purpose"} - set(patch_raw))
        if unknown_patch:
            _fail("unknown_field", f"patches[{index}] fields: {unknown_patch}")
        if missing_patch:
            _fail("missing_field", f"patches[{index}] fields: {missing_patch}")
        patch_path = _text(patch_raw.get("path"), f"patches[{index}].path")
        if Path(patch_path).is_absolute() or ".." in Path(patch_path).parts:
            _fail("unsafe_patch_path", patch_path)
        patch_sha256 = _text(patch_raw.get("sha256"), f"patches[{index}].sha256")
        if SHA256_PATTERN.fullmatch(patch_sha256) is None:
            _fail("invalid_sha256", f"patches[{index}].sha256")
        patches.append(
            SourcePatchIdentity(
                path=patch_path,
                sha256=patch_sha256,
                purpose=_text(patch_raw.get("purpose"), f"patches[{index}].purpose"),
            )
        )
    patch_paths = [patch.path for patch in patches]
    if patch_paths != sorted(set(patch_paths)):
        _fail("noncanonical_order", "patches must be sorted by unique path")

    content_sha256 = value.get("content_sha256")
    if not isinstance(content_sha256, str) or SHA256_PATTERN.fullmatch(content_sha256) is None:
        _fail("invalid_sha256", "content_sha256 must be lowercase SHA-256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", "content_sha256 does not bind the canonical payload")

    return SourceIdentity(
        schema=SOURCE_IDENTITY_SCHEMA,
        schema_revision=SOURCE_IDENTITY_SCHEMA_REVISION,
        source_id=source_id,
        producer=producer,
        paper=paper,
        repository=repository,
        license=license_identity,
        derivation=_text(value.get("derivation"), "derivation"),
        artifact_name=_text(value.get("artifact_name"), "artifact_name"),
        patches=tuple(patches),
        content_sha256=content_sha256,
    )


def load_source_identity(path: Path) -> SourceIdentity:
    from .json_io import load_json
    value = load_json(path)
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain a JSON object")
    return validate_source_identity(value)


def source_identity_schema_path() -> Path:
    return Path(resources.files("sidinspector.schemas").joinpath("source_identity.v1.schema.json"))


def from_legacy_adapter_manifest(manifest: Mapping[str, Any]) -> SourceIdentity:
    """Map one adapter_manifest.v1 source block without changing its meaning."""

    if manifest.get("schema_version") != "sidscope.adapter_manifest.v1":
        _fail("legacy_schema_mismatch", "expected sidscope.adapter_manifest.v1")
    source = manifest.get("source")
    if not isinstance(source, Mapping):
        _fail("legacy_missing_source", "legacy manifest.source must be an object")
    document = {
        "schema": SOURCE_IDENTITY_SCHEMA,
        "schema_revision": SOURCE_IDENTITY_SCHEMA_REVISION,
        "source_id": _text(manifest.get("artifact_id"), "artifact_id"),
        "producer": {
            "name": "sidinspector.conformance",
            "version": "sidscope.adapter_manifest.v1",
        },
        "paper": {
            "title": _text(manifest.get("paper_label"), "paper_label"),
            "url": None,
        },
        "repository": {
            "url": source.get("url"),
            "revision_kind": "git_commit",
            "revision": source.get("revision"),
        },
        "license": {
            "status": source.get("license_status"),
            "identifier": source.get("license_identifier"),
            "notices": [],
            "redistribution_policy": source.get("redistribution_policy"),
        },
        "derivation": source.get("derivation"),
        "artifact_name": source.get("artifact_name"),
        "patches": [],
    }
    return validate_source_identity(with_content_sha256(document))
