"""Filesystem content-addressed storage for immutable EvidenceBundle objects."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Union

from sidinspector.contracts import SHA256_PATTERN, canonical_json_bytes, loads_json, JSONInputError

from .bundle import (
    EvidenceBundle,
    EvidenceBundleValidationError,
    load_evidence_bundle,
    scan_evidence_content,
    validate_evidence_bundle,
)


ArtifactSource = Union[Path, bytes, bytearray]


def _fail(code: str, detail: str) -> None:
    raise EvidenceBundleValidationError(code, detail)


def _require_sha256(value: str, field: str = "content_sha256") -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail("invalid_sha256", field)
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_source(source: ArtifactSource, content_sha256: str) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, bytearray):
        return bytes(source)
    if isinstance(source, Path):
        try:
            return source.read_bytes()
        except OSError as exc:
            _fail("artifact_read_failed", f"{content_sha256}: {exc}")
    _fail("invalid_artifact_source", content_sha256)


def _scan_public_artifact(payload: bytes, media_type: str, content_sha256: str) -> None:
    if "json" in media_type.casefold():
        try:
            value = loads_json(payload, max_bytes=None)
        except JSONInputError as exc:
            _fail("invalid_public_json", f"{content_sha256}: {exc.code}")
        scan_evidence_content(value, location=f"artifact:{content_sha256}")
        return
    try:
        text = payload.decode("utf-8")
    except UnicodeError:
        return
    scan_evidence_content(text, location=f"artifact:{content_sha256}")


class ObjectStore:
    """Local immutable CAS whose SQLite/index consumers are always derived."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def bundle_path(self, content_sha256: str) -> Path:
        digest = _require_sha256(content_sha256)
        return self.root / "bundles" / "sha256" / digest[:2] / f"{digest}.json"

    def object_path(self, content_sha256: str) -> Path:
        digest = _require_sha256(content_sha256)
        return self.root / "objects" / "sha256" / digest[:2] / digest

    def quarantine_path(self, content_sha256: str) -> Path:
        digest = _require_sha256(content_sha256)
        return self.root / "quarantine" / "sha256" / digest[:2] / f"{digest}.json"

    @staticmethod
    def _atomic_write(path: Path, payload: bytes, *, kind: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                observed = path.read_bytes()
            except OSError as exc:
                _fail("stored_object_read_failed", f"{path}: {exc}")
            if observed != payload:
                _fail(f"{kind}_collision_or_tamper", str(path))
            return
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            # A competing writer can only publish identical content at this
            # digest. Recheck immediately before replace to fail closed.
            if path.exists():
                observed = path.read_bytes()
                if observed != payload:
                    _fail(f"{kind}_collision_or_tamper", str(path))
                temporary.unlink()
                return
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _bundle_bytes(bundle: EvidenceBundle) -> bytes:
        return canonical_json_bytes(bundle.to_dict()) + b"\n"

    def admit_bundle(
        self,
        bundle: EvidenceBundle | Mapping[str, Any],
        public_artifacts: Mapping[str, ArtifactSource] | None = None,
    ) -> Path:
        """Validate and atomically admit public objects, then their bundle.

        A ``hash_reference_only`` artifact is deliberately never copied into
        the store. An ``embedded_public`` artifact must be supplied or already
        exist under its exact-byte object hash.
        """

        validated = validate_evidence_bundle(
            bundle.to_dict() if isinstance(bundle, EvidenceBundle) else bundle
        )
        missing_predecessors = sorted(
            digest
            for digest in validated.supersedes
            if not self.bundle_path(digest).is_file()
            and not self.quarantine_path(digest).is_file()
        )
        if missing_predecessors:
            _fail("missing_superseded_bundle", ",".join(missing_predecessors))
        supplied = dict(public_artifacts or {})
        for digest in supplied:
            _require_sha256(digest, "public_artifacts key")

        artifact_by_hash: dict[str, Mapping[str, Any]] = {}
        embedded_hashes: set[str] = set()
        for row in validated.artifacts:
            digest = str(row["object_sha256"])
            previous = artifact_by_hash.get(digest)
            if previous is not None and (
                previous["content_sha256"] != row["content_sha256"]
                or previous["schema_id"] != row["schema_id"]
                or previous["schema_revision"] != row["schema_revision"]
                or previous["size_bytes"] != row["size_bytes"]
                or previous["media_type"] != row["media_type"]
                or previous["availability"] != row["availability"]
            ):
                _fail("conflicting_artifact_metadata", digest)
            artifact_by_hash[digest] = row
            if row["availability"] == "embedded_public":
                embedded_hashes.add(digest)

        unexpected = sorted(set(supplied) - embedded_hashes)
        if unexpected:
            _fail("unexpected_public_artifact", ",".join(unexpected))

        object_payloads: dict[str, bytes] = {}
        for digest in sorted(embedded_hashes):
            row = artifact_by_hash[digest]
            if digest in supplied:
                payload = _read_source(supplied[digest], digest)
            else:
                existing = self.object_path(digest)
                if not existing.is_file():
                    _fail("missing_public_artifact", digest)
                try:
                    payload = existing.read_bytes()
                except OSError as exc:
                    _fail("artifact_read_failed", f"{digest}: {exc}")
            if _sha256_bytes(payload) != digest:
                _fail("artifact_hash_mismatch", digest)
            if len(payload) != row["size_bytes"]:
                _fail("artifact_size_mismatch", digest)
            _scan_public_artifact(payload, str(row["media_type"]), digest)
            object_payloads[digest] = payload

        # Publish payload objects before the bundle that references them. A
        # crash can leave an unreferenced object, never a visible incomplete bundle.
        for digest, payload in sorted(object_payloads.items()):
            self._atomic_write(self.object_path(digest), payload, kind="artifact")
        path = self.bundle_path(validated.content_sha256)
        self._atomic_write(path, self._bundle_bytes(validated), kind="bundle")
        return path

    def load_bundle(self, content_sha256: str) -> EvidenceBundle:
        digest = _require_sha256(content_sha256)
        path = self.bundle_path(digest)
        return self._load_bundle_path(path, digest)

    def _load_bundle_path(self, path: Path, digest: str) -> EvidenceBundle:
        if not path.is_file():
            _fail("bundle_not_found", digest)
        bundle = load_evidence_bundle(path)
        if bundle.content_sha256 != digest:
            _fail("bundle_path_hash_mismatch", digest)
        try:
            stored = path.read_bytes()
        except OSError as exc:
            _fail("bundle_load_failed", f"{path}: {exc}")
        if stored != self._bundle_bytes(bundle):
            _fail("noncanonical_bundle_storage", str(path))
        return bundle

    def load_quarantined_bundle(self, content_sha256: str) -> EvidenceBundle:
        digest = _require_sha256(content_sha256)
        return self._load_bundle_path(self.quarantine_path(digest), digest)

    def iter_bundles(self) -> Iterator[EvidenceBundle]:
        base = self.root / "bundles" / "sha256"
        if not base.exists():
            return
        for path in sorted(base.glob("[0-9a-f][0-9a-f]/*.json")):
            yield self.load_bundle(path.stem)

    def iter_quarantined_bundles(self) -> Iterator[EvidenceBundle]:
        base = self.root / "quarantine" / "sha256"
        if not base.exists():
            return
        for path in sorted(base.glob("[0-9a-f][0-9a-f]/*.json")):
            yield self.load_quarantined_bundle(path.stem)

    def verify_bundle(self, content_sha256: str) -> EvidenceBundle:
        bundle = self.load_bundle(content_sha256)
        for row in bundle.artifacts:
            if row["availability"] != "embedded_public":
                continue
            digest = str(row["object_sha256"])
            path = self.object_path(digest)
            if not path.is_file():
                _fail("missing_stored_artifact", digest)
            try:
                payload = path.read_bytes()
            except OSError as exc:
                _fail("stored_object_read_failed", f"{path}: {exc}")
            if _sha256_bytes(payload) != digest:
                _fail("stored_artifact_tamper", digest)
            if len(payload) != row["size_bytes"]:
                _fail("stored_artifact_size_mismatch", digest)
            _scan_public_artifact(payload, str(row["media_type"]), digest)
        return bundle

    def quarantine_bundle(self, content_sha256: str) -> Path:
        """Atomically move a suspect bundle aside without editing its bytes."""

        digest = _require_sha256(content_sha256)
        source = self.bundle_path(digest)
        if not source.is_file():
            _fail("bundle_not_found", digest)
        target = self.quarantine_path(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            _fail("quarantine_collision", digest)
        try:
            os.replace(source, target)
        except OSError as exc:
            _fail("quarantine_failed", f"{digest}: {exc}")
        return target


__all__ = ["ArtifactSource", "ObjectStore"]
