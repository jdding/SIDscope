"""Canonical PreparedDataset v1 model, bindings, and RPG legacy bridge."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Sequence

from .dataset_identity import (
    DATASET_IDENTITY_SCHEMA,
    DATASET_IDENTITY_SCHEMA_REVISION,
    DatasetIdentity,
    validate_dataset_identity,
)
from .hashing import SHA256_PATTERN, canonical_sha256, verify_content_sha256, with_content_sha256
from .sid_space_identity import (
    SID_SPACE_IDENTITY_SCHEMA,
    SID_SPACE_IDENTITY_SCHEMA_REVISION,
    SIDSpaceIdentity,
    validate_sid_space_identity,
)
from .source_identity import ProducerIdentity
from .producer_versions import CONTRACT_PRODUCER_VERSION


PREPARED_DATASET_SCHEMA = "sidscope.prepared_dataset.v1"
PREPARED_DATASET_SCHEMA_REVISION = "1.0.0"
PREPARED_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SPLIT_ROLES = ("train", "validation", "test")
ARTIFACT_ROLES = ("interaction_sequences", "item_mapping", "semantic_id_cache")


class PreparedDatasetValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class IdentityBinding:
    schema_id: str
    schema_revision: str
    content_sha256: str


@dataclass(frozen=True)
class PreparedSplit:
    role: str
    split_id: str
    sha256: str
    row_count: int


@dataclass(frozen=True)
class PreparedArtifact:
    role: str
    sha256: str
    row_count: int


@dataclass(frozen=True)
class PreparedUniverse:
    scope: str
    item_count: int
    sha256: str


@dataclass(frozen=True)
class PreparedDataset:
    schema: str
    schema_revision: str
    prepared_dataset_id: str
    producer: ProducerIdentity
    dataset_binding: IdentityBinding
    sid_space_binding: IdentityBinding
    normalization: Mapping[str, Any]
    splits: tuple[PreparedSplit, ...]
    artifacts: tuple[PreparedArtifact, ...]
    catalog: PreparedUniverse
    target_universe: PreparedUniverse
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_revision": self.schema_revision,
            "prepared_dataset_id": self.prepared_dataset_id,
            "producer": {"name": self.producer.name, "version": self.producer.version},
            "dataset_binding": self.dataset_binding.__dict__.copy(),
            "sid_space_binding": self.sid_space_binding.__dict__.copy(),
            "normalization": dict(self.normalization),
            "splits": [row.__dict__.copy() for row in self.splits],
            "artifacts": [row.__dict__.copy() for row in self.artifacts],
            "catalog": self.catalog.__dict__.copy(),
            "target_universe": self.target_universe.__dict__.copy(),
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class PreparedDatasetMigration:
    dataset_identity: DatasetIdentity
    sid_space_identity: SIDSpaceIdentity
    prepared_dataset: PreparedDataset


def _fail(code: str, detail: str) -> None:
    raise PreparedDatasetValidationError(code, detail)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_value", f"{field} must be a non-empty string")
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def _count(value: Any, field: str, *, allow_zero: bool = True) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_count", f"{field} must be integer >= {minimum}")
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


def _binding(value: Mapping[str, Any], key: str, expected_schema: str) -> IdentityBinding:
    raw = _object(value, key, {"schema_id", "schema_revision", "content_sha256"})
    schema_id = _text(raw.get("schema_id"), f"{key}.schema_id")
    if schema_id != expected_schema:
        _fail("dependency_schema_mismatch", f"{key}={schema_id}")
    return IdentityBinding(
        schema_id,
        _text(raw.get("schema_revision"), f"{key}.schema_revision"),
        _sha(raw.get("content_sha256"), f"{key}.content_sha256"),
    )


def _universe(value: Mapping[str, Any], key: str, scopes: set[str]) -> PreparedUniverse:
    raw = _object(value, key, {"scope", "item_count", "sha256"})
    scope = _text(raw.get("scope"), f"{key}.scope")
    if scope not in scopes:
        _fail("unsupported_scope", f"{key}.scope={scope}")
    return PreparedUniverse(
        scope,
        _count(raw.get("item_count"), f"{key}.item_count", allow_zero=False),
        _sha(raw.get("sha256"), f"{key}.sha256"),
    )


def validate_prepared_dataset(value: Mapping[str, Any]) -> PreparedDataset:
    if not isinstance(value, Mapping):
        _fail("invalid_type", "prepared dataset must be an object")
    fields = {
        "schema", "schema_revision", "prepared_dataset_id", "producer",
        "dataset_binding", "sid_space_binding", "normalization", "splits",
        "artifacts", "catalog", "target_universe", "content_sha256",
    }
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        _fail("unknown_field", f"unsupported top-level fields: {unknown}")
    if missing:
        _fail("missing_field", f"missing top-level fields: {missing}")
    if value.get("schema") != PREPARED_DATASET_SCHEMA:
        _fail("schema_mismatch", f"schema must be {PREPARED_DATASET_SCHEMA}")
    if value.get("schema_revision") != PREPARED_DATASET_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))
    prepared_id = _text(value.get("prepared_dataset_id"), "prepared_dataset_id")
    if PREPARED_ID_PATTERN.fullmatch(prepared_id) is None:
        _fail("invalid_prepared_dataset_id", prepared_id)
    producer_raw = _object(value, "producer", {"name", "version"})
    producer = ProducerIdentity(
        _text(producer_raw.get("name"), "producer.name"),
        _text(producer_raw.get("version"), "producer.version"),
    )
    dataset_binding = _binding(value, "dataset_binding", DATASET_IDENTITY_SCHEMA)
    sid_binding = _binding(value, "sid_space_binding", SID_SPACE_IDENTITY_SCHEMA)
    if dataset_binding.schema_revision != DATASET_IDENTITY_SCHEMA_REVISION:
        _fail("dependency_revision_mismatch", "dataset_binding")
    if sid_binding.schema_revision != SID_SPACE_IDENTITY_SCHEMA_REVISION:
        _fail("dependency_revision_mismatch", "sid_space_binding")

    normalization = _object(
        value,
        "normalization",
        {
            "representation", "item_identity", "episode_identity",
            "source_item_ids_exported", "source_user_ids_exported",
            "evaluator_labels_in_generator_input",
        },
    )
    expected_normalization = {
        "representation": "normalized_item_sequences",
        "item_identity": "pseudonymous_normalized_items",
        "episode_identity": "pseudonymous_episode_ids",
        "source_item_ids_exported": False,
        "source_user_ids_exported": False,
        "evaluator_labels_in_generator_input": False,
    }
    if dict(normalization) != expected_normalization:
        _fail("normalization_or_privacy_mismatch", str(dict(normalization)))

    splits_raw = value.get("splits")
    if not isinstance(splits_raw, Sequence) or isinstance(splits_raw, (str, bytes)):
        _fail("invalid_type", "splits must be an array")
    splits: list[PreparedSplit] = []
    for index, raw in enumerate(splits_raw):
        if not isinstance(raw, Mapping) or set(raw) != {"role", "split_id", "sha256", "row_count"}:
            _fail("invalid_split", f"splits[{index}]")
        splits.append(
            PreparedSplit(
                _text(raw.get("role"), f"splits[{index}].role"),
                _text(raw.get("split_id"), f"splits[{index}].split_id"),
                _sha(raw.get("sha256"), f"splits[{index}].sha256"),
                _count(raw.get("row_count"), f"splits[{index}].row_count"),
            )
        )
    if [row.role for row in splits] != list(SPLIT_ROLES):
        _fail("noncanonical_split_order", "splits must be train, validation, test")

    artifacts_raw = value.get("artifacts")
    if not isinstance(artifacts_raw, Sequence) or isinstance(artifacts_raw, (str, bytes)):
        _fail("invalid_type", "artifacts must be an array")
    artifacts: list[PreparedArtifact] = []
    for index, raw in enumerate(artifacts_raw):
        if not isinstance(raw, Mapping) or set(raw) != {"role", "sha256", "row_count"}:
            _fail("invalid_artifact", f"artifacts[{index}]")
        artifacts.append(
            PreparedArtifact(
                _text(raw.get("role"), f"artifacts[{index}].role"),
                _sha(raw.get("sha256"), f"artifacts[{index}].sha256"),
                _count(raw.get("row_count"), f"artifacts[{index}].row_count"),
            )
        )
    if [row.role for row in artifacts] != list(ARTIFACT_ROLES):
        _fail("noncanonical_artifact_order", f"artifacts must be {ARTIFACT_ROLES}")

    catalog = _universe(value, "catalog", {"train_only", "full_dataset"})
    target = _universe(
        value, "target_universe", {"train_only_catalog", "evaluation_targets"}
    )
    artifact_map = {row.role: row for row in artifacts}
    if artifact_map["item_mapping"].row_count != catalog.item_count:
        _fail("catalog_artifact_count_mismatch", "item_mapping")
    if artifact_map["semantic_id_cache"].row_count != catalog.item_count:
        _fail("catalog_artifact_count_mismatch", "semantic_id_cache")
    if artifact_map["interaction_sequences"].row_count != sum(row.row_count for row in splits):
        _fail("interaction_artifact_count_mismatch", "interaction_sequences")
    if artifact_map["item_mapping"].sha256 != catalog.sha256:
        _fail("catalog_artifact_hash_mismatch", "item_mapping")

    content_sha256 = _sha(value.get("content_sha256"), "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", "content_sha256 does not bind the canonical payload")
    return PreparedDataset(
        PREPARED_DATASET_SCHEMA,
        PREPARED_DATASET_SCHEMA_REVISION,
        prepared_id,
        producer,
        dataset_binding,
        sid_binding,
        dict(normalization),
        tuple(splits),
        tuple(artifacts),
        catalog,
        target,
        content_sha256,
    )


def validate_prepared_dataset_bindings(
    prepared: PreparedDataset,
    dataset: DatasetIdentity,
    sid_space: SIDSpaceIdentity,
) -> None:
    if dataset.identity_status != "fully_bound" or sid_space.identity_status != "fully_bound":
        _fail("partial_dependency", "PreparedDataset requires fully_bound dependencies")
    if prepared.dataset_binding.content_sha256 != dataset.content_sha256:
        _fail("dataset_binding_mismatch", dataset.content_sha256)
    if prepared.sid_space_binding.content_sha256 != sid_space.content_sha256:
        _fail("sid_space_binding_mismatch", sid_space.content_sha256)
    expected_splits = [
        (row.role, row.split_id, row.sha256, row.row_count) for row in dataset.splits
    ]
    observed_splits = [
        (row.role, row.split_id, row.sha256, row.row_count) for row in prepared.splits
    ]
    if observed_splits != expected_splits:
        _fail("dataset_split_binding_mismatch", str(observed_splits))
    if (
        prepared.catalog.scope != dataset.catalog.scope
        or prepared.catalog.item_count != dataset.catalog.item_count
        or prepared.catalog.sha256 != dataset.catalog.sha256
    ):
        _fail("dataset_catalog_binding_mismatch", prepared.catalog.sha256)
    if (
        prepared.target_universe.scope != dataset.target_universe.scope
        or prepared.target_universe.item_count != dataset.target_universe.item_count
        or prepared.target_universe.sha256 != dataset.target_universe.sha256
    ):
        _fail("dataset_target_universe_binding_mismatch", prepared.target_universe.sha256)
    semantic = {row.role: row for row in prepared.artifacts}["semantic_id_cache"]
    if semantic.sha256 != sid_space.tokenizer.artifact_sha256:
        _fail("sid_cache_binding_mismatch", semantic.sha256)


def load_prepared_dataset(path: Path) -> PreparedDataset:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain a JSON object")
    return validate_prepared_dataset(value)


def prepared_dataset_schema_path() -> Path:
    return Path(resources.files("sidinspector.schemas").joinpath("prepared_dataset.v1.schema.json"))


def from_rpg_prepared_dataset(value: Mapping[str, Any]) -> PreparedDatasetMigration:
    """Migrate the complete RPG bridge fixture without importing the legacy runtime."""

    if value.get("schema") != "sidscope.rpg_prepared_dataset.v1":
        _fail("legacy_schema_mismatch", "expected sidscope.rpg_prepared_dataset.v1")
    dataset_raw = value.get("dataset")
    splits_raw = value.get("splits")
    catalog_raw = value.get("catalog")
    artifacts_raw = value.get("artifacts")
    config = value.get("configuration")
    if not all(
        isinstance(row, Mapping)
        for row in (dataset_raw, splits_raw, catalog_raw, artifacts_raw, config)
    ):
        _fail("legacy_prepared_insufficient", "RPG prepared sections are incomplete")
    for role in SPLIT_ROLES:
        row = splits_raw.get(role)
        if not isinstance(row, Mapping) or not {
            "split_id",
            "sha256",
            "row_count",
        }.issubset(row):
            _fail("legacy_prepared_insufficient", f"splits.{role} is incomplete")
    for role in ARTIFACT_ROLES:
        row = artifacts_raw.get(role)
        if not isinstance(row, Mapping) or "sha256" not in row:
            _fail("legacy_prepared_insufficient", f"artifacts.{role} is incomplete")
    if not {"name", "category", "profile"}.issubset(dataset_raw):
        _fail("legacy_prepared_insufficient", "dataset identity is incomplete")
    if not {"row_count", "target_universe_sha256"}.issubset(catalog_raw):
        _fail("legacy_prepared_insufficient", "catalog identity is incomplete")
    normalized_name = re.sub(
        r"[^a-z0-9]+", "_", _text(dataset_raw.get("name"), "dataset.name").lower()
    ).strip("_")
    split_rows = [
        {
            "role": role,
            "split_id": splits_raw[role]["split_id"],
            "sha256": splits_raw[role]["sha256"],
            "row_count": splits_raw[role]["row_count"],
        }
        for role in SPLIT_ROLES
    ]
    catalog_count = _count(catalog_raw.get("row_count"), "catalog.row_count", allow_zero=False)
    dataset_doc = with_content_sha256(
        {
            "schema": DATASET_IDENTITY_SCHEMA,
            "schema_revision": DATASET_IDENTITY_SCHEMA_REVISION,
            "dataset_id": f"rpg:{normalized_name}:{catalog_count}",
            "producer": {
                "name": "sidinspector.contracts",
                "version": CONTRACT_PRODUCER_VERSION,
            },
            "dataset": {
                "name": dataset_raw["name"],
                "normalized_name": normalized_name,
                "category": dataset_raw["category"],
                "profile": dataset_raw["profile"],
            },
            "splits": split_rows,
            "catalog": {
                "scope": "train_only",
                "item_count": catalog_count,
                "sha256": artifacts_raw["item_mapping"]["sha256"],
            },
            "target_universe": {
                "scope": "train_only_catalog",
                "item_count": catalog_count,
                "sha256": catalog_raw["target_universe_sha256"],
            },
            "privacy": {
                "item_identity": "pseudonymous_normalized_items",
                "contains_source_item_ids": False,
            },
            "identity_status": "fully_bound",
            "unbound_fields": [],
        }
    )
    dataset = validate_dataset_identity(dataset_doc)

    depth = _count(config.get("n_codebooks"), "configuration.n_codebooks", allow_zero=False)
    size = _count(config.get("codebook_size"), "configuration.codebook_size", allow_zero=False)
    sid_config = {
        "codebook_sizes": [size] * depth,
        "position_offsets": [1 + position * size for position in range(depth)],
        "token_offset_rule": "position_times_codebook_size_plus_code_plus_one",
    }
    sid_doc = with_content_sha256(
        {
            "schema": SID_SPACE_IDENTITY_SCHEMA,
            "schema_revision": SID_SPACE_IDENTITY_SCHEMA_REVISION,
            "sid_space_id": f"rpg:{value.get('contract_id')}",
            "producer": {
                "name": "sidinspector.contracts",
                "version": CONTRACT_PRODUCER_VERSION,
            },
            "structure": {
                "tuple_kind": "unordered_set",
                "length_kind": "fixed",
                "depth": depth,
                "hierarchy": "none",
            },
            "vocabulary": {
                "semantic_code_min": 0,
                "codebook_sizes": sid_config["codebook_sizes"],
                "position_offsets": sid_config["position_offsets"],
                "position_disjoint": True,
                "model_vocabulary_size": 1 + depth * size,
                "special_tokens": {
                    "pad": 0, "bos": None, "eos": None, "mask": None, "unknown": None
                },
            },
            "tokenizer": {
                "kind": "rpg_semantic_id_cache",
                "tokenizer_factor": "official_rpg_opq_cache",
                "configuration_sha256": canonical_sha256(sid_config),
                "artifact_sha256": artifacts_raw["semantic_id_cache"]["sha256"],
            },
            "resolution": {
                "dedup_semantics": "preserve_all_item_collisions",
                "collision_semantics": "many_items_per_sid_allowed",
            },
            "identity_status": "fully_bound",
            "unbound_fields": [],
        }
    )
    sid_space = validate_sid_space_identity(sid_doc)

    artifact_rows = [
        {
            "role": "interaction_sequences",
            "sha256": artifacts_raw["interaction_sequences"]["sha256"],
            "row_count": sum(row["row_count"] for row in split_rows),
        },
        {
            "role": "item_mapping",
            "sha256": artifacts_raw["item_mapping"]["sha256"],
            "row_count": catalog_count,
        },
        {
            "role": "semantic_id_cache",
            "sha256": artifacts_raw["semantic_id_cache"]["sha256"],
            "row_count": catalog_count,
        },
    ]
    prepared_doc = with_content_sha256(
        {
            "schema": PREPARED_DATASET_SCHEMA,
            "schema_revision": PREPARED_DATASET_SCHEMA_REVISION,
            "prepared_dataset_id": f"rpg:{value.get('contract_id')}",
            "producer": {
                "name": "sidinspector.contracts",
                "version": CONTRACT_PRODUCER_VERSION,
            },
            "dataset_binding": {
                "schema_id": dataset.schema,
                "schema_revision": dataset.schema_revision,
                "content_sha256": dataset.content_sha256,
            },
            "sid_space_binding": {
                "schema_id": sid_space.schema,
                "schema_revision": sid_space.schema_revision,
                "content_sha256": sid_space.content_sha256,
            },
            "normalization": {
                "representation": "normalized_item_sequences",
                "item_identity": "pseudonymous_normalized_items",
                "episode_identity": "pseudonymous_episode_ids",
                "source_item_ids_exported": False,
                "source_user_ids_exported": False,
                "evaluator_labels_in_generator_input": False,
            },
            "splits": split_rows,
            "artifacts": artifact_rows,
            "catalog": dataset_doc["catalog"],
            "target_universe": dataset_doc["target_universe"],
        }
    )
    prepared = validate_prepared_dataset(prepared_doc)
    validate_prepared_dataset_bindings(prepared, dataset, sid_space)
    return PreparedDatasetMigration(dataset, sid_space, prepared)


def require_regeneration_for_legacy_prepared(value: Mapping[str, Any]) -> None:
    schema = value.get("schema")
    if schema in {
        "sidscope.diffgrm_prepared_dataset.v1",
        "sidscope.llada_rec_prepared_dataset.v1",
    }:
        _fail(
            "legacy_prepared_regeneration_required",
            f"{schema} lacks canonical split counts or artifact bindings",
        )
    _fail("legacy_schema_mismatch", str(schema))
