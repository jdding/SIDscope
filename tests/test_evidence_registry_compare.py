from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sidinspector.contracts import canonical_json_bytes, with_content_sha256
from sidinspector.evidence.bundle import build_evidence_bundle
from sidinspector.evidence.comparison import compare_evidence_bundles
from sidinspector.evidence.registry import EvidenceRegistry, EvidenceRegistryError


SHA = {
    "source": "01" * 32,
    "data": "02" * 32,
    "sid": "03" * 32,
    "run": "04" * 32,
    "checkpoint": "05" * 32,
    "trace": "06" * 32,
    "diagnostics": "07" * 32,
    "conformance": "08" * 32,
    "dataset": "09" * 32,
    "universe": "0a" * 32,
}
ROLES = (
    "source",
    "data",
    "sid",
    "run",
    "checkpoint",
    "trace",
    "diagnostics",
    "conformance",
)


def evidence_bundle(
    *,
    bundle_id: str = "fixture-a",
    adapter_id: str = "adapter-a",
    profile_id: str = "trained-trace",
    profile_revision: str = "1.0.0",
    dataset_hash: str = SHA["dataset"],
    universe_hash: str = SHA["universe"],
    cutoff: int = 10,
    depth: int = 100,
    rank_semantics: str = "exact_with_censoring",
    hit: float = 0.2,
    ndcg: float = 0.1,
    failures: int = 3,
    calls: int = 50,
    exact_count: int = 2,
    censored_count: int = 3,
    exact_ranks: tuple[int, ...] | None = None,
    supersedes: tuple[str, ...] = (),
):
    artifacts = [
        {
            "artifact_id": f"a{index:02d}-{role}",
            "role": role,
            "schema_id": f"fixture.{role}.v1",
            "schema_revision": "1.0.0",
            "content_sha256": SHA[role],
            "object_sha256": ("1" + SHA[role][1:]),
            "size_bytes": index + 1,
            "media_type": "application/json",
            "availability": "hash_reference_only",
        }
        for index, role in enumerate(ROLES)
    ]
    edges = [
        {
            "from_artifact": artifacts[index]["artifact_id"],
            "to_artifact": artifacts[index + 1]["artifact_id"],
            "relation": "binds",
        }
        for index in range(len(artifacts) - 1)
    ]
    return build_evidence_bundle(
        bundle_id=bundle_id,
        producer={"name": "fixture", "version": "1.4.0.dev0"},
        profile_binding={
            "profile_id": profile_id,
            "profile_revision": profile_revision,
            "conformance_report_sha256": SHA["conformance"],
        },
        subject={"adapter_id": adapter_id, "method_family": "parallel_graph"},
        compatibility={
            "dataset_identity_sha256": dataset_hash,
            "target_universe_sha256": universe_hash,
            "evaluation_cutoff": cutoff,
            "publication_depth": depth,
            "rank_semantics": rank_semantics,
        },
        artifacts=artifacts,
        provenance_edges=edges,
        result_card={
            "overall_metrics": {"hit_at_10": hit, "ndcg_at_10": ndcg},
            "slice_metrics": {"gap_gt_365d": {"hit_at_10": hit / 2}},
            "failure_counts": {"generation_search_miss": failures},
            "compute": {"forward_calls": calls},
            "rank_observations": {
                "exact_count": exact_count,
                "censored_count": censored_count,
                "exact_ranks": list(
                    exact_ranks
                    if exact_ranks is not None
                    else tuple(range(1, exact_count + 1))
                ),
            },
        },
        supersedes=supersedes,
    )


class EvidenceRegistryTest(unittest.TestCase):
    def test_add_list_show_idempotence_and_projection_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = EvidenceRegistry(Path(tmp) / "registry.sqlite3")
            bundle = evidence_bundle()
            bundle_hash = registry.add(bundle)
            self.assertEqual(registry.add(bundle), bundle_hash)
            self.assertEqual(registry.show(bundle_hash), bundle.to_dict())
            self.assertEqual(registry.list_bundles()[0]["status"], "active")
            exported = registry.export_static()
            self.assertEqual(len(exported["bundles"]), 1)
            self.assertEqual(len(exported["artifacts"]), 8)
            self.assertEqual(len(exported["metrics"]), 5)

            connection = sqlite3.connect(str(Path(tmp) / "registry.sqlite3"))
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            connection.close()
            self.assertTrue(
                {"bundles", "artifacts", "metrics", "supersessions"}
                <= table_names
            )

    def test_rebuild_export_is_byte_equivalent_after_database_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.sqlite3"
            original = evidence_bundle()
            correction = evidence_bundle(
                bundle_id="fixture-correction",
                adapter_id="adapter-b",
                hit=0.3,
                supersedes=(original.content_sha256,),
            )
            registry = EvidenceRegistry(path)
            registry.rebuild([correction, original])
            first = canonical_json_bytes(registry.export_static())
            path.unlink()
            rebuilt = EvidenceRegistry(path)
            rebuilt.rebuild([original, correction])
            second = canonical_json_bytes(rebuilt.export_static())
            self.assertEqual(first, second)
            self.assertEqual(
                rebuilt.export_static()["supersessions"],
                [
                    {
                        "successor_sha256": correction.content_sha256,
                        "predecessor_sha256": original.content_sha256,
                    }
                ],
            )

    def test_supersession_missing_cycle_and_hash_conflict_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = EvidenceRegistry(Path(tmp) / "registry.sqlite3")
            missing = evidence_bundle(supersedes=("ff" * 32,))
            with self.assertRaises(EvidenceRegistryError) as captured:
                registry.add(missing)
            self.assertEqual(captured.exception.code, "missing_superseded_bundle")

            with self.assertRaises(EvidenceRegistryError) as captured:
                EvidenceRegistry._topological_order(
                    [
                        {"content_sha256": "aa", "supersedes": ["bb"]},
                        {"content_sha256": "bb", "supersedes": ["aa"]},
                    ]
                )
            self.assertEqual(captured.exception.code, "supersession_cycle")

            bundle = evidence_bundle()
            registry.add(bundle)
            tampered = bundle.to_dict()
            tampered["bundle_id"] = "different-content-same-claim"
            with self.assertRaises(EvidenceRegistryError) as captured:
                registry.add(tampered)
            self.assertEqual(captured.exception.code, "hash_content_conflict")

    def test_quarantine_preserves_bundle_and_projection_is_not_import_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = EvidenceRegistry(Path(tmp) / "registry.sqlite3")
            bundle = evidence_bundle()
            registry.add(bundle)
            registry.quarantine(bundle.content_sha256, reason="superseded audit")
            self.assertEqual(registry.list_bundles()[0]["status"], "quarantined")
            self.assertEqual(registry.show(bundle.content_sha256), bundle.to_dict())

            snapshot = registry.export_static()
            with self.assertRaises(Exception):
                registry.import_bundles([snapshot])
            self.assertEqual(registry.show(bundle.content_sha256), bundle.to_dict())

    def test_import_accepts_full_bundles_in_any_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = EvidenceRegistry(Path(tmp) / "registry.sqlite3")
            original = evidence_bundle()
            correction = evidence_bundle(
                bundle_id="fixture-correction",
                supersedes=(original.content_sha256,),
            )
            registry.import_bundles([correction, original])
            self.assertEqual(len(registry.list_bundles()), 2)

    def test_static_export_rescans_derived_rows_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.sqlite3"
            registry = EvidenceRegistry(path)
            bundle = evidence_bundle()
            registry.add(bundle)
            with sqlite3.connect(str(path)) as connection:
                connection.execute(
                    "UPDATE artifacts SET artifact_json = ? WHERE artifact_id = ?",
                    (
                        json.dumps({"source_item_id": "forbidden"}),
                        "a00-source",
                    ),
                )
            with self.assertRaises(EvidenceRegistryError) as captured:
                registry.export_static()
            self.assertEqual(captured.exception.code, "export_privacy_violation")


class EvidenceComparisonTest(unittest.TestCase):
    def test_compatible_comparison_separates_contract_and_method_delta(self) -> None:
        left = evidence_bundle()
        right = evidence_bundle(
            bundle_id="fixture-b",
            adapter_id="adapter-b",
            hit=0.4,
            ndcg=0.25,
            failures=1,
            calls=60,
        )
        result = compare_evidence_bundles(left, right)
        self.assertEqual(result["status"], "compatible")
        self.assertEqual(result["contract_compatibility"]["status"], "compatible")
        self.assertEqual(
            result["method_difference"]["overall_metrics"]["hit_at_10"]["delta"],
            0.2,
        )
        self.assertEqual(
            result["method_difference"]["failure_counts"]
            ["generation_search_miss"]["delta"],
            -2,
        )

    def test_each_contract_axis_rejects_metric_comparison(self) -> None:
        cases = {
            "profile_id_mismatch": {"profile_id": "other-profile"},
            "profile_revision_mismatch": {"profile_revision": "2.0.0"},
            "dataset_identity_mismatch": {"dataset_hash": "11" * 32},
            "target_universe_mismatch": {"universe_hash": "12" * 32},
            "evaluation_cutoff_mismatch": {"cutoff": 20},
            "publication_depth_mismatch": {"depth": 200},
            "rank_semantics_mismatch": {
                "rank_semantics": "cutoff_only",
                "depth": 10,
                "exact_count": 0,
                "exact_ranks": (),
            },
        }
        left = evidence_bundle()
        for expected_code, overrides in cases.items():
            with self.subTest(expected_code=expected_code):
                result = compare_evidence_bundles(
                    left,
                    evidence_bundle(bundle_id=f"right-{expected_code}", **overrides),
                )
                self.assertEqual(result["status"], "incompatible")
                self.assertIsNone(result["method_difference"])
                self.assertIn(
                    expected_code,
                    {
                        reason["code"]
                        for reason in result["contract_compatibility"]["reasons"]
                    },
                )

    def test_cutoff_only_exact_claim_is_typed_rejection(self) -> None:
        cutoff_only = evidence_bundle(
            rank_semantics="cutoff_only",
            depth=10,
            exact_count=0,
            exact_ranks=(),
        ).to_dict()
        cutoff_only["result_card"]["rank_observations"].update(
            {"exact_count": 1, "exact_ranks": [1]}
        )
        cutoff_only = with_content_sha256(cutoff_only)
        result = compare_evidence_bundles(cutoff_only, cutoff_only)
        self.assertEqual(result["status"], "rejected")
        self.assertIn(
            result["contract_compatibility"]["reasons"][0]["code"],
            {"unsupported_exact_rank_claim", "invalid_bundle"},
        )

    def test_exact_rank_beyond_depth_is_typed_rejection_when_present(self) -> None:
        bundle = evidence_bundle().to_dict()
        bundle["result_card"]["rank_observations"]["exact_ranks"] = [1, 101]
        bundle["result_card"]["rank_observations"]["exact_count"] = 2
        bundle = with_content_sha256(bundle)
        result = compare_evidence_bundles(bundle, bundle)
        self.assertEqual(result["status"], "rejected")
        self.assertIn(
            result["contract_compatibility"]["reasons"][0]["code"],
            {"exact_rank_exceeds_publication_depth", "invalid_bundle"},
        )

    def test_comparison_output_is_canonical_order_independent(self) -> None:
        left = evidence_bundle()
        right = evidence_bundle(bundle_id="fixture-b", hit=0.4)
        first = canonical_json_bytes(compare_evidence_bundles(left, right))
        second = canonical_json_bytes(compare_evidence_bundles(left, right))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
