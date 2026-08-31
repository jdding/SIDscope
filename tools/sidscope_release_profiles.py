#!/usr/bin/env python3
"""Load and resolve the three additive SIDScope 1.7 release profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_REGISTRY = (
    ROOT / "docs" / "reproducibility" / "sidscope_release_profiles.v1.json"
)
PROFILE_RECEIPT_PATH = "sidscope-release-profile.json"
PROFILE_IDS = ("runtime", "conformance", "evidence-full")


class ReleaseProfileError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ReleaseProfile:
    profile_id: str
    description: str
    include_roots: tuple[str, ...]
    exclude_roots: tuple[str, ...]
    required_paths: tuple[str, ...]
    smoke_suite: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def path_set_sha256(paths: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(paths)) + "\n").encode("utf-8")).hexdigest()


def _strings(value: Any, *, field: str, profile_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ReleaseProfileError("invalid_profile_registry", f"{profile_id}.{field}")
    if value != sorted(set(value)):
        raise ReleaseProfileError("noncanonical_profile_paths", f"{profile_id}.{field}")
    for item in value:
        if item.startswith("/") or ".." in Path(item).parts:
            raise ReleaseProfileError("unsafe_profile_path", f"{profile_id}.{field}: {item}")
    return tuple(value)


def load_release_profiles(path: Path = DEFAULT_PROFILE_REGISTRY) -> tuple[str, dict[str, ReleaseProfile]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or value.get("schema") != "sidscope.release_profile_registry.v1":
        raise ReleaseProfileError("invalid_profile_registry", str(path))
    default_profile = value.get("default_profile")
    if default_profile != "runtime":
        raise ReleaseProfileError("invalid_default_profile", str(default_profile))
    rows = value.get("profiles")
    if not isinstance(rows, list):
        raise ReleaseProfileError("invalid_profile_registry", "profiles must be a list")
    profiles: dict[str, ReleaseProfile] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReleaseProfileError("invalid_profile_registry", "profile row must be an object")
        profile_id = row.get("profile_id")
        if profile_id not in PROFILE_IDS or profile_id in profiles:
            raise ReleaseProfileError("invalid_profile_id", str(profile_id))
        description = row.get("description")
        smoke_suite = row.get("smoke_suite")
        if not isinstance(description, str) or not description:
            raise ReleaseProfileError("invalid_profile_registry", f"{profile_id}.description")
        if smoke_suite not in PROFILE_IDS:
            raise ReleaseProfileError("invalid_smoke_suite", f"{profile_id}: {smoke_suite}")
        profiles[profile_id] = ReleaseProfile(
            profile_id=profile_id,
            description=description,
            include_roots=_strings(row.get("include_roots"), field="include_roots", profile_id=profile_id),
            exclude_roots=_strings(row.get("exclude_roots"), field="exclude_roots", profile_id=profile_id),
            required_paths=_strings(row.get("required_paths"), field="required_paths", profile_id=profile_id),
            smoke_suite=smoke_suite,
        )
    if tuple(profiles) != PROFILE_IDS:
        raise ReleaseProfileError("noncanonical_profile_order", str(tuple(profiles)))
    return default_profile, profiles


def _matches(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def resolve_release_profile(
    profile_id: str,
    *,
    public_paths: Sequence[str],
    registry_path: Path = DEFAULT_PROFILE_REGISTRY,
) -> tuple[ReleaseProfile, list[str]]:
    _, profiles = load_release_profiles(registry_path)
    try:
        profile = profiles[profile_id]
    except KeyError as exc:
        raise ReleaseProfileError("unknown_release_profile", profile_id) from exc
    public = sorted(set(public_paths))
    if profile_id == "evidence-full":
        selected = public
    else:
        selected = [
            path
            for path in public
            if any(_matches(path, root) for root in profile.include_roots)
            and not any(_matches(path, root) for root in profile.exclude_roots)
        ]
    registry_rel_path = registry_path.relative_to(ROOT).as_posix()
    if registry_rel_path not in public:
        raise ReleaseProfileError("profile_registry_not_public", registry_rel_path)
    if registry_rel_path not in selected:
        selected.append(registry_rel_path)
        selected.sort()
    missing = [path for path in profile.required_paths if path not in selected]
    if missing:
        raise ReleaseProfileError("missing_required_profile_path", f"{profile_id}: {missing}")
    if not selected:
        raise ReleaseProfileError("empty_release_profile", profile_id)
    return profile, selected


def build_profile_receipt(
    *,
    profile: ReleaseProfile,
    content_paths: Sequence[str],
    registry_path: Path,
    source_manifest_path: Path,
    product_version: str,
) -> dict[str, Any]:
    return {
        "schema": "sidscope.release_profile_receipt.v1",
        "profile_id": profile.profile_id,
        "product_version": product_version,
        "smoke_suite": profile.smoke_suite,
        "content_file_count": len(content_paths),
        "content_paths_sha256": path_set_sha256(content_paths),
        "profile_registry_sha256": file_sha256(registry_path),
        "source_manifest_sha256": file_sha256(source_manifest_path),
    }


def validate_profile_receipt(value: Mapping[str, Any], *, content_paths: Sequence[str]) -> str:
    if value.get("schema") != "sidscope.release_profile_receipt.v1":
        raise ReleaseProfileError("invalid_profile_receipt", str(value.get("schema")))
    profile_id = value.get("profile_id")
    if profile_id not in PROFILE_IDS:
        raise ReleaseProfileError("invalid_profile_receipt", str(profile_id))
    if value.get("smoke_suite") != profile_id:
        raise ReleaseProfileError("profile_smoke_mismatch", str(value.get("smoke_suite")))
    if value.get("content_file_count") != len(content_paths):
        raise ReleaseProfileError("profile_file_count_mismatch", profile_id)
    if value.get("content_paths_sha256") != path_set_sha256(content_paths):
        raise ReleaseProfileError("profile_path_binding_mismatch", profile_id)
    for field in ("profile_registry_sha256", "source_manifest_sha256"):
        digest = value.get(field)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ReleaseProfileError("invalid_profile_receipt", field)
    return profile_id
