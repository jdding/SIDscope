#!/usr/bin/env python3
"""Verify SIDScope 1.4 immutable bundles, registry recovery, and comparison."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_json_bytes
from sidinspector.evidence import (
    EvidenceBundleValidationError,
    EvidenceRegistry,
    ObjectStore,
    compare_evidence_bundles,
    load_evidence_bundle,
)


FIXTURE = ROOT / "examples" / "evidence_system_fixture"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_evidence_system() -> dict[str, object]:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    bundles = {
        name: load_evidence_bundle(FIXTURE / name)
        for name in manifest["positive"]
    }
    negative_results: dict[str, str] = {}
    for name, expected in manifest["negative"].items():
        try:
            load_evidence_bundle(FIXTURE / name)
        except EvidenceBundleValidationError as exc:
            if exc.code != expected:
                raise ValueError(f"{name}: {exc.code} != {expected}") from exc
            negative_results[name] = exc.code
        else:
            raise ValueError(f"negative fixture unexpectedly passed: {name}")

    public_path = FIXTURE / manifest["public_artifact"]
    public_sha = _sha256(public_path)
    baseline = bundles["baseline_bundle.json"]
    correction = bundles["correction_bundle.json"]
    incompatible = bundles["incompatible_bundle.json"]

    with tempfile.TemporaryDirectory(prefix="sidscope-evidence-1-4-") as tmp:
        store_root = Path(tmp) / "store"
        store = ObjectStore(store_root)
        database = store_root / "registry.sqlite3"
        registry = EvidenceRegistry(database)

        store.admit_bundle(baseline, {public_sha: public_path})
        registry.add(baseline)
        store.verify_bundle(baseline.content_sha256)

        # The shared embedded object is already present; correction admission is
        # still complete without re-supplying it.
        store.admit_bundle(correction)
        registry.add(correction)
        store.admit_bundle(incompatible)
        registry.add(incompatible)

        compatible = compare_evidence_bundles(baseline, correction)
        if compatible["status"] != "compatible":
            raise ValueError(f"compatible comparison rejected: {compatible}")
        hit_delta = compatible["method_difference"]["overall_metrics"]["hit_at_10"]["delta"]
        if abs(hit_delta - 0.1) > 1e-12:
            raise ValueError(f"metric delta mismatch: {hit_delta}")

        rejected = compare_evidence_bundles(baseline, incompatible)
        if rejected["status"] != "incompatible":
            raise ValueError(f"incompatible comparison passed: {rejected}")
        reason_codes = {
            row["code"] for row in rejected["contract_compatibility"]["reasons"]
        }
        if "target_universe_mismatch" not in reason_codes:
            raise ValueError(f"missing target-universe rejection: {reason_codes}")

        store.quarantine_bundle(baseline.content_sha256)
        registry.quarantine(baseline.content_sha256, reason="superseded fixture audit")
        before = registry.export_static()
        before_bytes = canonical_json_bytes(before)
        if not database.is_file():
            raise ValueError("SQLite projection was not created")
        database.unlink()
        rebuilt = EvidenceRegistry(database)
        active = list(store.iter_bundles())
        quarantined = list(store.iter_quarantined_bundles())
        rebuilt.rebuild([*active, *quarantined])
        for bundle in quarantined:
            rebuilt.quarantine(bundle.content_sha256, reason="object_store_quarantine")
        after = rebuilt.export_static()
        if canonical_json_bytes(after) != before_bytes:
            raise ValueError("registry static export changed after delete/rebuild")

        shown = rebuilt.show(correction.content_sha256)
        if baseline.content_sha256 not in shown["supersedes"]:
            raise ValueError("correction lost its supersession edge")
        hash_only_count = sum(
            row["availability"] == "hash_reference_only"
            for row in baseline.artifacts
        )
        if hash_only_count != 7:
            raise ValueError(f"restricted/hash-only count mismatch: {hash_only_count}")

    return {
        "schema": "sidscope.release_1_4_evidence_system_verification.v1",
        "status": "pass",
        "bundle_schema": baseline.schema,
        "bundle_schema_revision": baseline.schema_revision,
        "positive_bundle_count": len(bundles),
        "typed_negative_count": len(negative_results),
        "embedded_public_artifact_count": 1,
        "hash_reference_only_artifact_count": 7,
        "supersession_verified": True,
        "quarantine_rebuild_verified": True,
        "compatible_metric_delta_verified": True,
        "incompatible_contract_rejection_verified": True,
        "sqlite_delete_rebuild_static_export_parity": True,
        "gpu_required": False,
    }


def main() -> None:
    print(json.dumps(verify_evidence_system(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
