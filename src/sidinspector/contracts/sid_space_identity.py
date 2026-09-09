"""Canonical SIDSpaceIdentity v1 model and fail-closed validator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Sequence

from .hashing import SHA256_PATTERN, canonical_sha256, verify_content_sha256, with_content_sha256
from .source_identity import ProducerIdentity


SID_SPACE_IDENTITY_SCHEMA = "sidscope.sid_space_identity.v1"
SID_SPACE_IDENTITY_SCHEMA_REVISION = "1.0.0"
SID_SPACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
TUPLE_KINDS = frozenset({"ordered", "unordered_set", "legacy_unspecified"})
LENGTH_KINDS = frozenset({"fixed", "variable", "legacy_unspecified"})
HIERARCHY_KINDS = frozenset({"prefix", "position_only", "none", "legacy_unspecified"})
DEDUP_SEMANTICS = frozenset(
    {"preserve_all_item_collisions", "unique_sid_required", "legacy_unspecified"}
)
COLLISION_SEMANTICS = frozenset(
    {"many_items_per_sid_allowed", "one_item_per_sid", "legacy_unspecified"}
)
SPECIAL_TOKEN_FIELDS = ("pad", "bos", "eos", "mask", "unknown")
LEGACY_UNBOUND_FIELDS = (
    "resolution.collision_semantics",
    "resolution.dedup_semantics",
    "structure.hierarchy",
    "structure.tuple_kind",
    "vocabulary.codebook_sizes",
    "vocabulary.model_vocabulary_size",
    "vocabulary.position_disjoint",
    "vocabulary.position_offsets",
    "vocabulary.special_tokens",
)


class SIDSpaceIdentityValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SIDStructure:
    tuple_kind: str
    length_kind: str
    depth: int | None
    hierarchy: str


@dataclass(frozen=True)
class SIDVocabulary:
    semantic_code_min: int
    codebook_sizes: tuple[int, ...]
    position_offsets: tuple[int, ...]
    position_disjoint: bool | None
    model_vocabulary_size: int | None
    special_tokens: Mapping[str, int | None]


@dataclass(frozen=True)
class TokenizerIdentity:
    kind: str
    tokenizer_factor: str
    configuration_sha256: str
    artifact_sha256: str


@dataclass(frozen=True)
class SIDResolution:
    dedup_semantics: str
    collision_semantics: str


@dataclass(frozen=True)
class SIDSpaceIdentity:
    schema: str
    schema_revision: str
    sid_space_id: str
    producer: ProducerIdentity
    structure: SIDStructure
    vocabulary: SIDVocabulary
    tokenizer: TokenizerIdentity
    resolution: SIDResolution
    identity_status: str
    unbound_fields: tuple[str, ...]
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_revision": self.schema_revision,
            "sid_space_id": self.sid_space_id,
            "producer": {"name": self.producer.name, "version": self.producer.version},
            "structure": {
                "tuple_kind": self.structure.tuple_kind,
                "length_kind": self.structure.length_kind,
                "depth": self.structure.depth,
                "hierarchy": self.structure.hierarchy,
            },
            "vocabulary": {
                "semantic_code_min": self.vocabulary.semantic_code_min,
                "codebook_sizes": list(self.vocabulary.codebook_sizes),
                "position_offsets": list(self.vocabulary.position_offsets),
                "position_disjoint": self.vocabulary.position_disjoint,
                "model_vocabulary_size": self.vocabulary.model_vocabulary_size,
                "special_tokens": dict(self.vocabulary.special_tokens),
            },
            "tokenizer": {
                "kind": self.tokenizer.kind,
                "tokenizer_factor": self.tokenizer.tokenizer_factor,
                "configuration_sha256": self.tokenizer.configuration_sha256,
                "artifact_sha256": self.tokenizer.artifact_sha256,
            },
            "resolution": {
                "dedup_semantics": self.resolution.dedup_semantics,
                "collision_semantics": self.resolution.collision_semantics,
            },
            "identity_status": self.identity_status,
            "unbound_fields": list(self.unbound_fields),
            "content_sha256": self.content_sha256,
        }


def _fail(code: str, detail: str) -> None:
    raise SIDSpaceIdentityValidationError(code, detail)


def _text(value: Any, field: str) -> str:
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


def _optional_int(value: Any, field: str, *, minimum: int = 0) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_integer", f"{field} must be null or integer >= {minimum}")
    return value


def _integer_array(value: Any, field: str, *, minimum: int) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _fail("invalid_type", f"{field} must be an array")
    rows: list[int] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int) or item < minimum:
            _fail("invalid_integer", f"{field}[{index}] must be >= {minimum}")
        rows.append(item)
    return tuple(rows)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def validate_sid_space_identity(value: Mapping[str, Any]) -> SIDSpaceIdentity:
    if not isinstance(value, Mapping):
        _fail("invalid_type", "SID space identity must be an object")
    fields = {
        "schema", "schema_revision", "sid_space_id", "producer", "structure",
        "vocabulary", "tokenizer", "resolution", "identity_status",
        "unbound_fields", "content_sha256",
    }
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        _fail("unknown_field", f"unsupported top-level fields: {unknown}")
    if missing:
        _fail("missing_field", f"missing top-level fields: {missing}")
    if value.get("schema") != SID_SPACE_IDENTITY_SCHEMA:
        _fail("schema_mismatch", f"schema must be {SID_SPACE_IDENTITY_SCHEMA}")
    if value.get("schema_revision") != SID_SPACE_IDENTITY_SCHEMA_REVISION:
        _fail("schema_revision_mismatch", str(value.get("schema_revision")))

    sid_space_id = _text(value.get("sid_space_id"), "sid_space_id")
    if SID_SPACE_ID_PATTERN.fullmatch(sid_space_id) is None:
        _fail("invalid_sid_space_id", sid_space_id)
    producer_raw = _object(value, "producer", {"name", "version"})
    producer = ProducerIdentity(
        name=_text(producer_raw.get("name"), "producer.name"),
        version=_text(producer_raw.get("version"), "producer.version"),
    )

    structure_raw = _object(
        value, "structure", {"tuple_kind", "length_kind", "depth", "hierarchy"}
    )
    tuple_kind = _text(structure_raw.get("tuple_kind"), "structure.tuple_kind")
    length_kind = _text(structure_raw.get("length_kind"), "structure.length_kind")
    hierarchy = _text(structure_raw.get("hierarchy"), "structure.hierarchy")
    if tuple_kind not in TUPLE_KINDS:
        _fail("unsupported_tuple_kind", tuple_kind)
    if length_kind not in LENGTH_KINDS:
        _fail("unsupported_length_kind", length_kind)
    if hierarchy not in HIERARCHY_KINDS:
        _fail("unsupported_hierarchy", hierarchy)
    depth = _optional_int(structure_raw.get("depth"), "structure.depth", minimum=1)
    structure = SIDStructure(tuple_kind, length_kind, depth, hierarchy)

    vocabulary_raw = _object(
        value,
        "vocabulary",
        {
            "semantic_code_min", "codebook_sizes", "position_offsets",
            "position_disjoint", "model_vocabulary_size", "special_tokens",
        },
    )
    semantic_code_min = _optional_int(
        vocabulary_raw.get("semantic_code_min"), "vocabulary.semantic_code_min"
    )
    if semantic_code_min is None:
        _fail("invalid_integer", "vocabulary.semantic_code_min cannot be null")
    codebook_sizes = _integer_array(
        vocabulary_raw.get("codebook_sizes"), "vocabulary.codebook_sizes", minimum=1
    )
    position_offsets = _integer_array(
        vocabulary_raw.get("position_offsets"), "vocabulary.position_offsets", minimum=0
    )
    position_disjoint = vocabulary_raw.get("position_disjoint")
    if position_disjoint is not None and not isinstance(position_disjoint, bool):
        _fail("invalid_type", "vocabulary.position_disjoint must be boolean or null")
    model_vocabulary_size = _optional_int(
        vocabulary_raw.get("model_vocabulary_size"),
        "vocabulary.model_vocabulary_size",
        minimum=1,
    )
    special_raw = _object(vocabulary_raw, "special_tokens", set(SPECIAL_TOKEN_FIELDS))
    special_tokens = {
        name: _optional_int(special_raw.get(name), f"special_tokens.{name}", minimum=-1)
        for name in SPECIAL_TOKEN_FIELDS
    }
    vocabulary = SIDVocabulary(
        semantic_code_min,
        codebook_sizes,
        position_offsets,
        position_disjoint,
        model_vocabulary_size,
        special_tokens,
    )

    tokenizer_raw = _object(
        value,
        "tokenizer",
        {"kind", "tokenizer_factor", "configuration_sha256", "artifact_sha256"},
    )
    tokenizer = TokenizerIdentity(
        kind=_text(tokenizer_raw.get("kind"), "tokenizer.kind"),
        tokenizer_factor=_text(
            tokenizer_raw.get("tokenizer_factor"), "tokenizer.tokenizer_factor"
        ),
        configuration_sha256=_sha(
            tokenizer_raw.get("configuration_sha256"), "tokenizer.configuration_sha256"
        ),
        artifact_sha256=_sha(
            tokenizer_raw.get("artifact_sha256"), "tokenizer.artifact_sha256"
        ),
    )
    resolution_raw = _object(
        value, "resolution", {"dedup_semantics", "collision_semantics"}
    )
    dedup = _text(resolution_raw.get("dedup_semantics"), "resolution.dedup_semantics")
    collision = _text(
        resolution_raw.get("collision_semantics"), "resolution.collision_semantics"
    )
    if dedup not in DEDUP_SEMANTICS:
        _fail("unsupported_dedup_semantics", dedup)
    if collision not in COLLISION_SEMANTICS:
        _fail("unsupported_collision_semantics", collision)
    resolution = SIDResolution(dedup, collision)

    status = _text(value.get("identity_status"), "identity_status")
    if status not in {"fully_bound", "legacy_partial"}:
        _fail("unsupported_identity_status", status)
    unbound_raw = value.get("unbound_fields")
    if not isinstance(unbound_raw, Sequence) or isinstance(unbound_raw, (str, bytes)):
        _fail("invalid_type", "unbound_fields must be an array")
    unbound_fields = tuple(_text(item, "unbound_fields[]") for item in unbound_raw)
    if list(unbound_fields) != sorted(set(unbound_fields)):
        _fail("noncanonical_order", "unbound_fields must be sorted and unique")

    if status == "fully_bound":
        if tuple_kind == "legacy_unspecified" or length_kind == "legacy_unspecified":
            _fail("legacy_structure_in_fully_bound", "fully_bound requires explicit structure")
        if hierarchy == "legacy_unspecified":
            _fail("legacy_hierarchy_in_fully_bound", "fully_bound requires hierarchy")
        if length_kind == "fixed" and depth is None:
            _fail("missing_sid_depth", "fixed SID space requires depth")
        if depth is not None and (
            len(codebook_sizes) != depth or len(position_offsets) != depth
        ):
            _fail("sid_depth_shape_mismatch", "depth, codebooks, and offsets must agree")
        if position_disjoint is None or model_vocabulary_size is None:
            _fail("missing_vocabulary_binding", "fully_bound requires vocabulary semantics")
        if unbound_fields:
            _fail("unexpected_unbound_fields", "fully_bound must have no unbound_fields")
        if dedup == "legacy_unspecified" or collision == "legacy_unspecified":
            _fail("legacy_resolution_in_fully_bound", "fully_bound requires resolution semantics")

        ranges = [
            (offset, offset + size - 1)
            for offset, size in zip(position_offsets, codebook_sizes)
        ]
        if position_disjoint:
            for index, (lower, upper) in enumerate(ranges):
                for other_lower, other_upper in ranges[index + 1 :]:
                    if max(lower, other_lower) <= min(upper, other_upper):
                        _fail("overlapping_position_vocabulary", str(ranges))
        maximum_token = max((upper for _, upper in ranges), default=-1)
        declared_tokens = [token for token in special_tokens.values() if token is not None]
        if len(declared_tokens) != len(set(declared_tokens)):
            _fail("duplicate_special_token", str(special_tokens))
        for token in declared_tokens:
            if any(lower <= token <= upper for lower, upper in ranges):
                _fail("special_token_collision", str(token))
        if maximum_token >= model_vocabulary_size:
            _fail("model_vocabulary_too_small", str(model_vocabulary_size))
        nonnegative_special = [token for token in declared_tokens if token >= 0]
        if nonnegative_special and max(nonnegative_special) >= model_vocabulary_size:
            _fail("special_token_out_of_vocabulary", str(max(nonnegative_special)))
    else:
        if codebook_sizes or position_offsets or position_disjoint is not None:
            _fail("legacy_partial_vocabulary_claim", "partial identity cannot claim vocabulary")
        if model_vocabulary_size is not None or any(
            token is not None for token in special_tokens.values()
        ):
            _fail("legacy_partial_token_claim", "partial identity cannot claim model tokens")
        if unbound_fields != LEGACY_UNBOUND_FIELDS:
            _fail("legacy_unbound_fields_mismatch", "legacy partial fields are fixed")

    content_sha256 = _sha(value.get("content_sha256"), "content_sha256")
    if not verify_content_sha256(value):
        _fail("content_hash_mismatch", "content_sha256 does not bind the canonical payload")
    return SIDSpaceIdentity(
        SID_SPACE_IDENTITY_SCHEMA,
        SID_SPACE_IDENTITY_SCHEMA_REVISION,
        sid_space_id,
        producer,
        structure,
        vocabulary,
        tokenizer,
        resolution,
        status,
        unbound_fields,
        content_sha256,
    )


def load_sid_space_identity(path: Path) -> SIDSpaceIdentity:
    from .json_io import load_json
    value = load_json(path)
    if not isinstance(value, Mapping):
        _fail("invalid_type", f"{path} must contain a JSON object")
    return validate_sid_space_identity(value)


def sid_space_identity_schema_path() -> Path:
    return Path(
        resources.files("sidinspector.schemas").joinpath("sid_space_identity.v1.schema.json")
    )


def from_legacy_adapter_manifest(manifest: Mapping[str, Any]) -> SIDSpaceIdentity:
    """Preserve known SID depth/artifact identity and expose every missing semantic."""

    if manifest.get("schema_version") != "sidscope.adapter_manifest.v1":
        _fail("legacy_schema_mismatch", "expected sidscope.adapter_manifest.v1")
    dataset = manifest.get("dataset")
    hashes = manifest.get("input_sha256")
    if not isinstance(dataset, Mapping) or not isinstance(hashes, Mapping):
        _fail("legacy_missing_sid_identity", "dataset and input_sha256 are required")
    depth = dataset.get("sid_depth")
    if isinstance(depth, bool) or not isinstance(depth, int) or depth <= 0:
        _fail("invalid_sid_depth", str(depth))
    artifact_sha256 = _sha(hashes.get("sid_assignments"), "input_sha256.sid_assignments")
    artifact_id = _text(manifest.get("artifact_id"), "artifact_id")
    configuration = _text(manifest.get("configuration"), "configuration")
    document = {
        "schema": SID_SPACE_IDENTITY_SCHEMA,
        "schema_revision": SID_SPACE_IDENTITY_SCHEMA_REVISION,
        "sid_space_id": f"legacy:{artifact_id}",
        "producer": {
            "name": "sidinspector.conformance",
            "version": "sidscope.adapter_manifest.v1",
        },
        "structure": {
            "tuple_kind": "legacy_unspecified",
            "length_kind": "fixed",
            "depth": depth,
            "hierarchy": "legacy_unspecified",
        },
        "vocabulary": {
            "semantic_code_min": 0,
            "codebook_sizes": [],
            "position_offsets": [],
            "position_disjoint": None,
            "model_vocabulary_size": None,
            "special_tokens": {name: None for name in SPECIAL_TOKEN_FIELDS},
        },
        "tokenizer": {
            "kind": "legacy_adapter_manifest",
            "tokenizer_factor": "legacy_unspecified",
            "configuration_sha256": canonical_sha256(configuration),
            "artifact_sha256": artifact_sha256,
        },
        "resolution": {
            "dedup_semantics": "legacy_unspecified",
            "collision_semantics": "legacy_unspecified",
        },
        "identity_status": "legacy_partial",
        "unbound_fields": list(LEGACY_UNBOUND_FIELDS),
    }
    return validate_sid_space_identity(with_content_sha256(document))
