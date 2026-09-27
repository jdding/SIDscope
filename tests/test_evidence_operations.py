from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main
from sidinspector.evidence import (
    EvidenceRegistryError,
    ObjectStore,
    compare_active_bundles,
    load_evidence_bundle,
    quarantine_bundle,
    rebuild_registry,
    register_bundles,
    supersede_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "evidence_system_fixture"


def invoke(argv: list[str]) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = cli_main(argv)
    return code, json.loads(output.getvalue())


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvidenceOperationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.public = FIXTURE / "public_conformance_summary.json"
        self.public_digest = digest_of(self.public)
        self.baseline_path = FIXTURE / "baseline_bundle.json"
        self.correction_path = FIXTURE / "correction_bundle.json"
        self.baseline_sha = json.loads(self.baseline_path.read_text(encoding="utf-8"))["content_sha256"]
        self.correction_sha = json.loads(self.correction_path.read_text(encoding="utf-8"))["content_sha256"]

    def _api_store(self, root: Path) -> tuple[ObjectStore, object]:
        store = ObjectStore(root)
        from sidinspector.evidence import EvidenceRegistry

        registry = EvidenceRegistry(root / "registry.sqlite3")
        return store, registry

    def test_api_and_cli_produce_identical_business_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            api_store, api_registry = self._api_store(Path(tmp) / "api")
            baseline = load_evidence_bundle(self.baseline_path)
            correction = load_evidence_bundle(self.correction_path)
            register_bundles(api_store, api_registry, [baseline], {self.public_digest: self.public}, operation="add")
            supersede_bundle(api_store, api_registry, correction, self.baseline_sha, {})
            api_comparison = compare_active_bundles(api_store, api_registry, self.baseline_sha, self.correction_sha)

            cli_store = Path(tmp) / "cli"
            code, added = invoke(["registry", "add", "--store", str(cli_store),
                                  "--bundle", str(self.baseline_path), "--artifact", f"{self.public_digest}={self.public}"])
            self.assertEqual((code, added["bundle_sha256s"]), (0, [self.baseline_sha]))
            code, superseded = invoke(["registry", "supersede", "--store", str(cli_store),
                                       "--prior", self.baseline_sha, "--bundle", str(self.correction_path)])
            self.assertEqual(code, 0)
            cli_store_object, cli_registry = self._api_store(cli_store)
            cli_comparison = compare_active_bundles(cli_store_object, cli_registry, self.baseline_sha, self.correction_sha)
            self.assertEqual(api_comparison, cli_comparison)
            self.assertEqual(api_comparison["status"], "incompatible")

            code, listed = invoke(["registry", "list", "--store", str(cli_store)])
            self.assertEqual(code, 0)
            self.assertEqual(sorted(row["content_sha256"] for row in listed["bundles"]),
                             sorted([self.baseline_sha, self.correction_sha]))

    def test_compare_rejects_quarantined_and_projection_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store, registry = self._api_store(Path(tmp) / "store")
            baseline = load_evidence_bundle(self.baseline_path)
            register_bundles(store, registry, [baseline], {self.public_digest: self.public}, operation="add")
            quarantine_bundle(store, registry, self.baseline_sha, "safety drill")
            with self.assertRaisesRegex(EvidenceRegistryError, "bundle_quarantined"):
                compare_active_bundles(store, registry, self.baseline_sha, self.baseline_sha)
            counts = rebuild_registry(store, registry)
            self.assertEqual(counts["quarantined_bundle_count"], 1)
            connection = sqlite3.connect(Path(tmp) / "store" / "registry.sqlite3")
            row = connection.execute(
                "SELECT bundle_json FROM bundles WHERE content_sha256=?", (self.baseline_sha,)).fetchone()
            document = json.loads(row[0])
            document["profile_binding"]["profile_id"] = "tampered_profile"
            connection.execute(
                "UPDATE bundles SET status='active', bundle_json=? WHERE content_sha256=?",
                (json.dumps(document), self.baseline_sha))
            connection.commit()
            connection.close()
            # Move the quarantined object back into the live CAS area so the
            # stale projection is the first inconsistency the comparison hits.
            quarantined_object = store.quarantine_path(self.baseline_sha)
            quarantined_object.parent.mkdir(parents=True, exist_ok=True)
            restored = store.bundle_path(self.baseline_sha)
            restored.parent.mkdir(parents=True, exist_ok=True)
            quarantined_object.rename(restored)
            with self.assertRaisesRegex(EvidenceRegistryError, "registry_projection_mismatch"):
                compare_active_bundles(store, registry, self.baseline_sha, self.baseline_sha)

    def test_invalid_quarantine_reason_is_side_effect_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            store, registry = self._api_store(root)
            baseline = load_evidence_bundle(self.baseline_path)
            register_bundles(store, registry, [baseline], {self.public_digest: self.public}, operation="add")
            before_objects = sorted(str(path) for path in root.rglob("*"))
            before_db = (root / "registry.sqlite3").read_bytes()
            with self.assertRaisesRegex(EvidenceRegistryError, "invalid_quarantine_reason"):
                quarantine_bundle(store, registry, self.baseline_sha, "   ")
            self.assertEqual(sorted(str(path) for path in root.rglob("*")), before_objects)
            self.assertEqual((root / "registry.sqlite3").read_bytes(), before_db)

    def test_interrupted_index_update_keeps_cas_quarantined_until_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            store, registry = self._api_store(root)
            baseline = load_evidence_bundle(self.baseline_path)
            register_bundles(store, registry, [baseline], {self.public_digest: self.public}, operation="add")
            original_quarantine = registry.quarantine

            def failing_index_update(content_sha256: str, *, reason: str) -> None:
                raise sqlite3.OperationalError("interrupted")

            registry.quarantine = failing_index_update
            with self.assertRaisesRegex(EvidenceRegistryError, "quarantine_index_update_failed"):
                quarantine_bundle(store, registry, self.baseline_sha, "safety drill")
            registry.quarantine = original_quarantine
            self.assertTrue(store.quarantine_path(self.baseline_sha).exists())
            with self.assertRaisesRegex(EvidenceRegistryError, "bundle_quarantined"):
                compare_active_bundles(store, registry, self.baseline_sha, self.baseline_sha)
            counts = rebuild_registry(store, registry)
            self.assertEqual(counts, {"bundle_count": 1, "quarantined_bundle_count": 1})
            self.assertTrue(store.quarantine_path(self.baseline_sha).exists())
            with self.assertRaisesRegex(EvidenceRegistryError, "bundle_quarantined"):
                compare_active_bundles(store, registry, self.baseline_sha, self.baseline_sha)

    def test_duplicate_supersede_and_conflict_semantics_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store, registry = self._api_store(Path(tmp) / "store")
            baseline = load_evidence_bundle(self.baseline_path)
            correction = load_evidence_bundle(self.correction_path)
            cas_before = None
            register_bundles(store, registry, [baseline], {self.public_digest: self.public}, operation="add")
            register_bundles(store, registry, [baseline], {self.public_digest: self.public}, operation="add")
            listed = registry.list_bundles()
            self.assertEqual(len([row for row in listed if row["content_sha256"] == self.baseline_sha]), 1)
            with self.assertRaisesRegex(EvidenceRegistryError, "missing_supersession_declaration"):
                supersede_bundle(store, registry, correction, "f" * 64, {})
            supersede_bundle(store, registry, correction, self.baseline_sha, {})
            self.assertTrue(store.bundle_path(self.baseline_sha).exists())
            self.assertTrue(store.bundle_path(self.correction_sha).exists())
            # add remains idempotent on re-registration; the projection stays intact
            register_bundles(store, registry, [correction], {}, operation="add")
            self.assertEqual(len(registry.list_bundles()), 2)


if __name__ == "__main__":
    unittest.main()
