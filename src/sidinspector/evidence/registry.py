"""Rebuildable SQLite projection for immutable SIDScope evidence bundles.

The object store is authoritative.  This module deliberately keeps the SQLite
database disposable: every row can be reconstructed from validated bundles,
and no API mutates bundle content.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from sidinspector.contracts import canonical_json_bytes
from sidinspector.evidence.bundle import (
    EvidenceBundle,
    EvidenceBundleValidationError,
    scan_evidence_content,
    validate_evidence_bundle,
)


class EvidenceRegistryError(ValueError):
    """Typed failure raised while projecting evidence into the registry."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _bundle_document(bundle: EvidenceBundle | Mapping[str, Any]) -> dict[str, Any]:
    document = bundle.to_dict() if isinstance(bundle, EvidenceBundle) else dict(bundle)
    return validate_evidence_bundle(document).to_dict()


def _json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _flatten_metrics(document: Mapping[str, Any]) -> list[tuple[str, str, str, str]]:
    result_card = document.get("result_card", {})
    rows: list[tuple[str, str, str, str]] = []

    def append_mapping(section: str, slice_id: str, values: Any) -> None:
        if not isinstance(values, Mapping):
            return
        for name in sorted(values):
            rows.append((section, slice_id, str(name), _json_text(values[name])))

    append_mapping("overall_metrics", "", result_card.get("overall_metrics", {}))
    slices = result_card.get("slice_metrics", {})
    if isinstance(slices, Mapping):
        for slice_id in sorted(slices):
            append_mapping("slice_metrics", str(slice_id), slices[slice_id])
    append_mapping("failure_counts", "", result_card.get("failure_counts", {}))
    append_mapping("compute", "", result_card.get("compute", {}))
    return rows


class EvidenceRegistry:
    """Disposable, deterministic SQLite projection of evidence bundles."""

    PROJECTION_SCHEMA = "sidscope.evidence_registry_projection.v1"
    PROJECTION_REVISION = "1.0.0"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS bundles (
                    content_sha256 TEXT PRIMARY KEY,
                    schema_id TEXT NOT NULL,
                    schema_revision TEXT NOT NULL,
                    bundle_json TEXT NOT NULL,
                    adapter_id TEXT NOT NULL,
                    method_family TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    profile_revision TEXT NOT NULL,
                    dataset_identity_sha256 TEXT NOT NULL,
                    target_universe_sha256 TEXT NOT NULL,
                    evaluation_cutoff INTEGER NOT NULL,
                    publication_depth INTEGER NOT NULL,
                    rank_semantics TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'quarantined')),
                    quarantine_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    bundle_sha256 TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    object_sha256 TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    PRIMARY KEY (bundle_sha256, artifact_id),
                    FOREIGN KEY (bundle_sha256) REFERENCES bundles(content_sha256)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS metrics (
                    bundle_sha256 TEXT NOT NULL,
                    section TEXT NOT NULL,
                    slice_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    PRIMARY KEY (bundle_sha256, section, slice_id, metric_name),
                    FOREIGN KEY (bundle_sha256) REFERENCES bundles(content_sha256)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS supersessions (
                    successor_sha256 TEXT NOT NULL,
                    predecessor_sha256 TEXT NOT NULL,
                    PRIMARY KEY (successor_sha256, predecessor_sha256),
                    FOREIGN KEY (successor_sha256) REFERENCES bundles(content_sha256)
                        ON DELETE CASCADE,
                    FOREIGN KEY (predecessor_sha256) REFERENCES bundles(content_sha256)
                        ON DELETE RESTRICT
                );
                """
            )

    def add(self, bundle: EvidenceBundle | Mapping[str, Any]) -> str:
        """Validate and atomically project one immutable evidence bundle."""

        raw = bundle.to_dict() if isinstance(bundle, EvidenceBundle) else dict(bundle)
        claimed_hash = raw.get("content_sha256")
        if isinstance(claimed_hash, str):
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT bundle_json FROM bundles WHERE content_sha256 = ?",
                    (claimed_hash,),
                ).fetchone()
            if existing is not None:
                if existing["bundle_json"] != _json_text(raw):
                    raise EvidenceRegistryError(
                        "hash_content_conflict",
                        f"bundle {claimed_hash} already projects different content",
                    )
                return claimed_hash

        document = _bundle_document(raw)
        bundle_hash = str(document["content_sha256"])
        supersedes = [str(value) for value in document.get("supersedes", [])]
        if bundle_hash in supersedes:
            raise EvidenceRegistryError(
                "supersession_cycle", f"bundle {bundle_hash} supersedes itself"
            )

        profile = document["profile_binding"]
        subject = document["subject"]
        compatibility = document["compatibility"]
        bundle_json = _json_text(document)
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                missing = [
                    predecessor
                    for predecessor in supersedes
                    if connection.execute(
                        "SELECT 1 FROM bundles WHERE content_sha256 = ?",
                        (predecessor,),
                    ).fetchone()
                    is None
                ]
                if missing:
                    raise EvidenceRegistryError(
                        "missing_superseded_bundle", ",".join(sorted(missing))
                    )
                for predecessor in supersedes:
                    if self._would_create_cycle(connection, bundle_hash, predecessor):
                        raise EvidenceRegistryError(
                            "supersession_cycle",
                            f"{bundle_hash} -> {predecessor}",
                        )

                connection.execute(
                    """
                    INSERT INTO bundles (
                        content_sha256, schema_id, schema_revision, bundle_json,
                        adapter_id, method_family, profile_id, profile_revision,
                        dataset_identity_sha256, target_universe_sha256,
                        evaluation_cutoff, publication_depth, rank_semantics
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bundle_hash,
                        document["schema"],
                        document["schema_revision"],
                        bundle_json,
                        subject["adapter_id"],
                        subject["method_family"],
                        profile["profile_id"],
                        profile["profile_revision"],
                        compatibility["dataset_identity_sha256"],
                        compatibility["target_universe_sha256"],
                        compatibility["evaluation_cutoff"],
                        compatibility["publication_depth"],
                        compatibility["rank_semantics"],
                    ),
                )
                for artifact in document.get("artifacts", []):
                    connection.execute(
                        """
                        INSERT INTO artifacts (
                            bundle_sha256, artifact_id, role, content_sha256,
                            object_sha256, artifact_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            bundle_hash,
                            artifact["artifact_id"],
                            artifact["role"],
                            artifact["content_sha256"],
                            artifact["object_sha256"],
                            _json_text(artifact),
                        ),
                    )
                for section, slice_id, name, value_json in _flatten_metrics(document):
                    connection.execute(
                        """
                        INSERT INTO metrics (
                            bundle_sha256, section, slice_id, metric_name, value_json
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (bundle_hash, section, slice_id, name, value_json),
                    )
                for predecessor in sorted(supersedes):
                    connection.execute(
                        """
                        INSERT INTO supersessions (successor_sha256, predecessor_sha256)
                        VALUES (?, ?)
                        """,
                        (bundle_hash, predecessor),
                    )
            except sqlite3.IntegrityError as error:
                raise EvidenceRegistryError("sqlite_integrity_error", str(error)) from error
        return bundle_hash

    @staticmethod
    def _would_create_cycle(
        connection: sqlite3.Connection, successor: str, predecessor: str
    ) -> bool:
        if successor == predecessor:
            return True
        row = connection.execute(
            """
            WITH RECURSIVE ancestors(value) AS (
                SELECT predecessor_sha256
                FROM supersessions WHERE successor_sha256 = ?
                UNION
                SELECT supersessions.predecessor_sha256
                FROM supersessions JOIN ancestors
                    ON supersessions.successor_sha256 = ancestors.value
            )
            SELECT 1 FROM ancestors WHERE value = ? LIMIT 1
            """,
            (predecessor, successor),
        ).fetchone()
        return row is not None

    def list_bundles(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT content_sha256, adapter_id, method_family, profile_id,
                       profile_revision, status, quarantine_reason
                FROM bundles ORDER BY content_sha256
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def show(self, content_sha256: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT bundle_json FROM bundles WHERE content_sha256 = ?",
                (content_sha256,),
            ).fetchone()
        if row is None:
            raise EvidenceRegistryError("unknown_bundle", content_sha256)
        return json.loads(row["bundle_json"])

    def quarantine(self, content_sha256: str, *, reason: str) -> None:
        """Mark a projection quarantined without deleting its authoritative object."""

        if not reason.strip():
            raise EvidenceRegistryError("invalid_quarantine_reason", "reason is empty")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE bundles SET status = 'quarantined', quarantine_reason = ?
                WHERE content_sha256 = ?
                """,
                (reason, content_sha256),
            )
            if cursor.rowcount != 1:
                raise EvidenceRegistryError("unknown_bundle", content_sha256)

    def rebuild(
        self, bundles: Iterable[EvidenceBundle | Mapping[str, Any]]
    ) -> None:
        """Atomically replace the projection with one rebuilt from full bundles."""

        documents = [_bundle_document(bundle) for bundle in bundles]
        ordered = self._topological_order(documents)
        temporary = tempfile.NamedTemporaryFile(
            prefix=f".{self.db_path.name}.", suffix=".tmp", dir=self.db_path.parent, delete=False
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        temporary_path.unlink()
        try:
            fresh = EvidenceRegistry(temporary_path)
            for document in ordered:
                fresh.add(document)
            os.replace(temporary_path, self.db_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _topological_order(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_hash: dict[str, dict[str, Any]] = {}
        for document in documents:
            bundle_hash = str(document["content_sha256"])
            if bundle_hash in by_hash:
                if _json_text(by_hash[bundle_hash]) != _json_text(document):
                    raise EvidenceRegistryError("hash_content_conflict", bundle_hash)
                continue
            by_hash[bundle_hash] = document

        for bundle_hash, document in by_hash.items():
            missing = sorted(set(document.get("supersedes", [])) - set(by_hash))
            if missing:
                raise EvidenceRegistryError(
                    "missing_superseded_bundle",
                    f"{bundle_hash}: {','.join(missing)}",
                )

        ordered: list[dict[str, Any]] = []
        remaining = dict(by_hash)
        emitted: set[str] = set()
        while remaining:
            ready = sorted(
                bundle_hash
                for bundle_hash, document in remaining.items()
                if set(document.get("supersedes", [])) <= emitted
            )
            if not ready:
                raise EvidenceRegistryError(
                    "supersession_cycle", ",".join(sorted(remaining))
                )
            for bundle_hash in ready:
                ordered.append(remaining.pop(bundle_hash))
                emitted.add(bundle_hash)
        return ordered

    def import_bundles(
        self,
        bundles: Iterable[EvidenceBundle | Mapping[str, Any]],
        *,
        replace: bool = False,
    ) -> None:
        """Import full authoritative bundles, never a projection snapshot."""

        documents = [_bundle_document(bundle) for bundle in bundles]
        if replace:
            self.rebuild(documents)
            return
        for document in self._topological_order_for_existing(documents):
            self.add(document)

    def _topological_order_for_existing(
        self, documents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            existing = {
                str(row[0])
                for row in connection.execute("SELECT content_sha256 FROM bundles")
            }
        by_hash = {str(document["content_sha256"]): document for document in documents}
        available = set(existing)
        ordered: list[dict[str, Any]] = []
        remaining = dict(by_hash)
        while remaining:
            ready = sorted(
                bundle_hash
                for bundle_hash, document in remaining.items()
                if set(document.get("supersedes", [])) <= available
            )
            if not ready:
                all_refs = {
                    str(value)
                    for document in remaining.values()
                    for value in document.get("supersedes", [])
                }
                missing = sorted(all_refs - available - set(remaining))
                code = "missing_superseded_bundle" if missing else "supersession_cycle"
                raise EvidenceRegistryError(code, ",".join(missing or sorted(remaining)))
            for bundle_hash in ready:
                ordered.append(remaining.pop(bundle_hash))
                available.add(bundle_hash)
        return ordered

    def export_static(self) -> dict[str, Any]:
        """Return a deterministic projection snapshot with no environment metadata."""

        with self._connect() as connection:
            bundles = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT content_sha256, schema_id, schema_revision, adapter_id,
                           method_family, profile_id, profile_revision,
                           dataset_identity_sha256, target_universe_sha256,
                           evaluation_cutoff, publication_depth, rank_semantics,
                           status
                    FROM bundles ORDER BY content_sha256
                    """
                )
            ]
            artifacts = [
                {
                    **dict(row),
                    "artifact": json.loads(row["artifact_json"]),
                }
                for row in connection.execute(
                    """
                    SELECT bundle_sha256, artifact_id, role, content_sha256, object_sha256,
                           artifact_json
                    FROM artifacts ORDER BY bundle_sha256, artifact_id
                    """
                )
            ]
            for row in artifacts:
                row.pop("artifact_json")
            metrics = [
                {
                    "bundle_sha256": row["bundle_sha256"],
                    "section": row["section"],
                    "slice_id": row["slice_id"],
                    "metric_name": row["metric_name"],
                    "value": json.loads(row["value_json"]),
                }
                for row in connection.execute(
                    """
                    SELECT bundle_sha256, section, slice_id, metric_name, value_json
                    FROM metrics
                    ORDER BY bundle_sha256, section, slice_id, metric_name
                    """
                )
            ]
            supersessions = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT successor_sha256, predecessor_sha256 FROM supersessions
                    ORDER BY successor_sha256, predecessor_sha256
                    """
                )
            ]
        projection = {
            "schema": self.PROJECTION_SCHEMA,
            "schema_revision": self.PROJECTION_REVISION,
            "bundles": bundles,
            "artifacts": artifacts,
            "metrics": metrics,
            "supersessions": supersessions,
        }
        try:
            scan_evidence_content(projection)
        except EvidenceBundleValidationError as error:
            raise EvidenceRegistryError(
                "export_privacy_violation", f"{error.code}: {error.detail}"
            ) from error
        return projection


__all__ = ["EvidenceRegistry", "EvidenceRegistryError"]
