"""Canonical DatasetIdentity v1 model and fail-closed validator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Sequence

from .hashing import SHA256_PATTERN, verify_content_sha256, with_content_sha256
from .source_identity import ProducerIdentity


DATASET_IDENTITY_SCHEMA = "sidscope.dataset_identity.v1"
DATASET_IDENTITY_SCHEMA_REVISION = "1.0.0"
DATASET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SPLIT_ROLES = ("train", "validation", "test")
CATALOG_SCOPES = frozenset({"train_only", "full_dataset", "legacy_expected_items"})
TARGET_UNIVERSE_SCOPES = frozenset(
    {"train_only_catalog", "evaluation_targets", "legacy_expected_items"}
)
ITEM_IDENTITY_SCOPES = frozenset(
    {"pseudonymous_normalized_items", "normalized_items", "legacy_unspecified"}
)
LEGACY_UNBOUND_FIELDS = (
    "catalog.sha256",
    "dataset.category",
    "dataset.profile",
    "splits",
    "target_universe.sha256",
)


class DatasetIdentityValidationError(ValueError):
    """Typed DatasetIdentity validation failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class DatasetDescriptor:
    name: str
    normalized_name: str
    category: str | None
    profile: str | None


@dataclass(frozen=True)
class SplitIdentity:
    role: str
    split_id: str
    sha256: str
    row_count: int


@dataclass(frozen=True)
class UniverseIdentity:
    scope: str
    item_count: int
    sha256: str | None


@dataclass(frozen=True)
class PrivacyIdentity:
    item_identity: str
    contains_source_item_ids: bool


@dataclass(frozen=True)
class DatasetIdentity:
    schema: str
    schema_revision: str
    dataset_id: str
    producer: ProducerIdentity
    dataset: DatasetDescriptor
    splits: tuple[SplitIdentity, ...]
    catalog: UniverseIdentity
    target_universe: UniverseIdentity
    privacy: PrivacyIdentity
    identity_status: str
    unbound_fields: tuple[str, ...]
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_revision": self.schema_revision,
            "dataset_id": self.dataset_id,
            "producer": {"name": self.producer.name, "version": self.producer.version},
            "dataset": {
                "name": self.dataset.name,
                "normalized_name": self.dataset.normalized_name,
                "category": self.dataset.category,
                "profile": self.dataset.profile,
            },
            "splits": [
                {
                    "role": split.role,
                    "split_id": split.split_id,
                    "sha256": split.sha256,
                    "row_count": split.row_count,
                }
                for split in self.splits
            ],
            "catalog": {
                "scope": self.catalog.scope,
                "item_count": self.catalog.item_count,
                "sha256": self.catalog.sha256,
            },
            "target_universe": {
                "scope": self.target_universe.scope,
                "item_count": self.target_universe.item_count,
                "sha256": self.target_universe.sha256,
            },
            "privacy": {
                "item_identity": self.privacy.item_identity,
                "contains_source_item_ids": self.privacy.contains_source_item_ids,
            },
            "identity_status": self.identity_status,
            "unbound_fields": list(self.unbound_fields),
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class LegacyDatasetMigration:
    """Dataset-owned projection plus the SID-space field intentionally deferred."""

    identity: DatasetIdentity
    deferred_sid_depth: int


def _fail(code: str, detail: str) -> None:
    raise DatasetIdentityValidationError(code, detail)


def _text(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be a non-empty string")
    return value


def _object(parent: Mapping[str, Any], key: str, fields: set[str]) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{key} must be an object")
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        _fail("unknown_field", f"{key} contains unsupported fields: {unknown}")
    if missing:
        _fail("missing_field", f"{key} is missing fields: {missing}")
    return value


def _count(value: Any, field: str, *, allow_zero: bool = True) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_count", f"{field} must be an integer >= {minimum}")
    return value


def _sha(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def _universe(
    value: Mapping[str, Any],
    key: str,
    allowed_scopes: frozenset[str],
) -> UniverseIdentity:
    raw = _object(value, key, {"scope", "item_count", "sha256"})
    scope = _text(raw.get("scope"), f"{key}.scope") or ""
    if scope not in allowed_scopes:
        _fail("unsupported_scope", f"{key}.scope={scope}")
    return UniverseIdentity(
        scope=scope,
        item_count=_count(raw.get("item_count"), f"{key}.item_count", allow_zero=False),
        sha256=_sha(raw.get("sha256"), f"{key}.sha256", nullable=True),
    )


def validate_dataset_identity(value: Mapping[str, Any]) -> DatasetIdentity:
    """Validate and parse one canonical DatasetIdentity artifact."""

    if not isinstance(value, Mapping):
        _fail("invalid_type", "dataset identity must be an object")
    fields = {
        "schema",
        "schema_revision",
        "dataset_id",
        "producer",
        "dataset",
        "splits",
        "catalog",
        "target_universe",
        "privacy",
        "identity_status",
        "unbound_fields",
        "content_sha256",
    }
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        _fail("unknown_field", f"unsupported top-level fields: {unknown}")
    if missing:
        _fail("missing_field", f"missing top-level fields: {missing}")
    if value.get("schema") != DATASET_IDENTITY_SCHEMA:
        _fail("schema_mismatch", f"schema must be {DATASET_IDENTITY_SCHEMA}")
    if value.get("schema_revision") != DATASET_IDENTITY_SCHEMA_REVISION:
        _fail(
            "schema_revision_mismatch",
            f"schema_revision must be {DATASET_IDENTITY_SCHEMA_REVISION}",
        )

    dataset_id = _text(value.get("dataset_id"), "dataset_id") or ""
    if DATASET_ID_PATTERN.fullmatch(dataset_id) is None:
        _fail("invalid_dataset_id", dataset_id)

    producer_raw = _object(value, "producer", {"name", "version"})
    producer = ProducerIdentity(
        name=_text(producer_raw.get("name"), "producer.name") or "",
        version=_text(producer_raw.get("version"), "producer.version") or "",
    )
    dataset_raw = _object(
        value, "dataset", {"name", "normalized_name", "category", "profile"}
    )
    dataset = DatasetDescriptor(
        name=_text(dataset_raw.get("name"), "dataset.name") or "",
        normalized_name=_text(dataset_raw.get("normalized_name"), "dataset.normalized_name")
        or "",
        category=_text(dataset_raw.get("category"), "dataset.category", nullable=True),
        profile=_text(dataset_raw.get("profile"), "dataset.profile", nullable=True),
    )

    splits_raw = value.get("splits")
    if not isinstance(splits_raw, Sequence) or isinstance(splits_raw, (str, bytes)):
        _fail("invalid_type", "splits must be an array")
    splits: list[SplitIdentity] = []
    for index, split_raw in enumerate(splits_raw):
        if not isinstance(split_raw, Mapping):
            _fail("invalid_type", f"splits[{index}] must be an object")
        unknown_split = sorted(set(split_raw) - {"role", "split_id", "sha256", "row_count"})
        missing_split = sorted({"role", "split_id", "sha256", "row_count"} - set(split_raw))
        if unknown_split:
            _fail("unknown_field", f"splits[{index}] fields: {unknown_split}")
        if missing_split:
            _fail("missing_field", f"splits[{index}] fields: {missing_split}")
        role = _text(split_raw.get("role"), f"splits[{index}].role") or ""
        if role not in SPLIT_ROLES:
            _fail("unsupported_split_role", role)
        splits.append(
            SplitIdentity(
                role=role,
                split_id=_text(split_raw.get("split_id"), f"splits[{index}].split_id") or "",
                sha256=_sha(split_raw.get("sha256"), f"splits[{index}].sha256") or "",
                row_count=_count(split_raw.get("row_count"), f"splits[{index}].row_count"),
            )
        )
    roles = [split.role for split in splits]
    expected_roles = [role for role in SPLIT_ROLES if role in roles]
    if roles != expected_roles or len(roles) != len(set(roles)):
        _fail(
            "noncanonical_split_order",
            "splits must be unique and ordered train, validation, test",
        )

    catalog = _universe(value, "catalog", CATALOG_SCOPES)
    target_universe = _universe(value, "target_universe", TARGET_UNIVERSE_SCOPES)
    privacy_raw = _object(value, "privacy", {"item_identity", "contains_source_item_ids"})
    item_identity = _text(privacy_raw.get("item_identity"), "privacy.item_identity") or ""
    if item_identity not in ITEM_IDENTITY_SCOPES:
        _fail("unsupported_item_identity", item_identity)
    contains_source = privacy_raw.get("contains_source_item_ids")
    if not isinstance(contains_source, bool):
        _fail("invalid_type", "privacy.contains_source_item_ids must be boolean")
    if contains_source:
        _fail("source_item_id_exposure", "canonical DatasetIdentity must be pseudonymous")
    privacy = PrivacyIdentity(item_identity=item_identity, contains_source_item_ids=False)

    status = _text(value.get("identity_status"), "identity_status") or ""
    if status not in {"fully_bound", "legacy_partial"}:
        _fail("unsupported_identity_status", status)
    unbound_raw = value.get("unbound_fields")
    if not isinstance(unbound_raw, Sequence) or isinstance(unbound_raw, (str, bytes)):
        _fail("invalid_type", "unbound_fields must be an array")
    unbound_fields = tuple(
        _text(item, "unbound_fields[]") or "" for item in unbound_raw
    )
    if list(unbound_fields) != sorted(set(unbound_fields)):
        _fail("noncanonical_order", "unbound_fields must be sorted and unique")

    if status == "fully_bound":
        if roles != list(SPLIT_ROLES):
            _fail("missing_split_binding", "fully_bound requires train, validation, test")
        if dataset.category is None or dataset.profile is None:
            _fail("missing_dataset_binding", "fully_bound requires category and profile")
        if catalog.sha256 is None or target_universe.sha256 is None:
            _fail("missing_universe_binding", "fully_bound requires catalog and target hashes")
        if unbound_fields:
            _fail("unexpected_unbound_fields", "fully_bound must have no unbound_fields")
        if catalog.scope == "legacy_expected_items" or target_universe.scope == "legacy_expected_items":
            _fail("legacy_scope_in_fully_bound", "fully_bound cannot use legacy scopes")
        if item_identity == "legacy_unspecified":
            _fail("legacy_privacy_in_fully_bound", "fully_bound requires explicit item identity")
    else:
        if splits:
            _fail("legacy_partial_split_claim", "legacy_partial cannot claim split bindings")
        if catalog.scope != "legacy_expected_items" or target_universe.scope != "legacy_expected_items":
            _fail("legacy_partial_scope_mismatch", "legacy_partial requires legacy scopes")
        if catalog.sha256 is not None or target_universe.sha256 is not None:
            _fail("legacy_partial_hash_claim", "legacy_partial cannot claim universe hashes")
        if unbound_fields != LEGACY_UNBOUND_FIELDS:
            _fail("legacy_unbound_fields_mismatch", "legacy_partial unbound fields are fixed")

    content_sha256 = _sha(value.get("content_sha256"), "content_sha256") or ""
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", "content_sha256 does not bind the canonical payload")

    return DatasetIdentity(
        schema=DATASET_IDENTITY_SCHEMA,
        schema_revision=DATASET_IDENTITY_SCHEMA_REVISION,
        dataset_id=dataset_id,
        producer=producer,
        dataset=dataset,
        splits=tuple(splits),
        catalog=catalog,
        target_universe=target_universe,
        privacy=privacy,
        identity_status=status,
        unbound_fields=unbound_fields,
        content_sha256=content_sha256,
    )


def load_dataset_identity(path: Path) -> DatasetIdentity:
    from .json_io import load_json
    value = load_json(path)
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain a JSON object")
    return validate_dataset_identity(value)


def dataset_identity_schema_path() -> Path:
    return Path(resources.files("sidinspector.schemas").joinpath("dataset_identity.v1.schema.json"))


def _legacy_dataset_id(name: str, expected_items: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "dataset"
    return f"legacy:{normalized}:{expected_items}"


def from_legacy_adapter_manifest(manifest: Mapping[str, Any]) -> LegacyDatasetMigration:
    """Project dataset-owned fields without inventing absent split/SID semantics."""

    if manifest.get("schema_version") != "sidscope.adapter_manifest.v1":
        _fail("legacy_schema_mismatch", "expected sidscope.adapter_manifest.v1")
    dataset = manifest.get("dataset")
    if not isinstance(dataset, Mapping):
        _fail("legacy_missing_dataset", "legacy manifest.dataset must be an object")
    name = _text(dataset.get("name"), "dataset.name") or ""
    normalized_name = dataset.get("normalized_name", name)
    normalized_name = _text(normalized_name, "dataset.normalized_name") or ""
    expected_items = _count(dataset.get("expected_items"), "dataset.expected_items", allow_zero=False)
    sid_depth = _count(dataset.get("sid_depth"), "dataset.sid_depth", allow_zero=False)
    document = {
        "schema": DATASET_IDENTITY_SCHEMA,
        "schema_revision": DATASET_IDENTITY_SCHEMA_REVISION,
        "dataset_id": _legacy_dataset_id(normalized_name, expected_items),
        "producer": {
            "name": "sidinspector.conformance",
            "version": "sidscope.adapter_manifest.v1",
        },
        "dataset": {
            "name": name,
            "normalized_name": normalized_name,
            "category": None,
            "profile": None,
        },
        "splits": [],
        "catalog": {
            "scope": "legacy_expected_items",
            "item_count": expected_items,
            "sha256": None,
        },
        "target_universe": {
            "scope": "legacy_expected_items",
            "item_count": expected_items,
            "sha256": None,
        },
        "privacy": {
            "item_identity": "legacy_unspecified",
            "contains_source_item_ids": False,
        },
        "identity_status": "legacy_partial",
        "unbound_fields": list(LEGACY_UNBOUND_FIELDS),
    }
    return LegacyDatasetMigration(
        identity=validate_dataset_identity(with_content_sha256(document)),
        deferred_sid_depth=sid_depth,
    )
