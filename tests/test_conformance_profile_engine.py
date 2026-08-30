from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from sidinspector.contracts import with_content_sha256
from sidinspector.conformance_core import (
    ProfileCompositionError,
    ProfileEngineError,
    build_profile_conformance_report,
    compose_profiles,
    get_profile_definition,
    load_dataset_profile_descriptor,
    load_profile_catalog,
    load_profile_conformance_report,
    profile_catalog_content_sha256,
    validate_dataset_profile_descriptor,
    validate_profile_conformance_report,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/conformance_ecosystem_fixture/profile"


def load_json(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


class SharedProfileCatalogTest(unittest.TestCase):
    def test_catalog_covers_four_owned_versioned_profile_kinds(self) -> None:
        profiles = load_profile_catalog()
        self.assertEqual(len(profiles), 4)
        self.assertEqual(
            {profile.profile_kind for profile in profiles},
            {"static_mapping", "generator", "overlay", "release"},
        )
        expected_gates = {
            "static_mapping_c0_c5": tuple(f"C{index}" for index in range(6)),
            "generator_g0_g5": tuple(f"G{index}" for index in range(6)),
            "overlay_g0_g5": tuple(f"G{index}" for index in range(6)),
            "release_local": tuple(f"L{index}" for index in range(6)),
        }
        for profile in profiles:
            with self.subTest(profile=profile.profile_id):
                self.assertEqual(profile.revision, "1.0.0")
                self.assertTrue(profile.owner)
                self.assertEqual(
                    tuple(gate.gate_id for gate in profile.gates),
                    expected_gates[profile.profile_id],
                )
                self.assertEqual(profile.lifecycle["status"], "active")
                self.assertTrue(profile.lifecycle["migration_policy"])
                self.assertTrue(profile.lifecycle["deprecation_policy"])
                self.assertTrue((ROOT / profile.fixture["positive"]).is_file())
                self.assertTrue(all((ROOT / path).is_file() for path in profile.fixture["negatives"]))
        self.assertEqual(len(profile_catalog_content_sha256()), 64)

    def test_legacy_registry_and_compose_api_remain_unchanged(self) -> None:
        composed = compose_profiles(["family.masked_diffusion.v1"])
        self.assertEqual(
            composed.profile_ids,
            ("common.generator.v1", "family.masked_diffusion.v1"),
        )
        self.assertEqual(composed.gates[0].gate_id, "binding_integrity")
        self.assertEqual(composed.gates[-1].gate_id, "unmask_transition")
        with self.assertRaises(ProfileCompositionError) as captured:
            compose_profiles(["missing.profile"])
        self.assertEqual(captured.exception.code, "unknown_profile")

    def test_unknown_shared_profile_and_revision_fail_closed(self) -> None:
        for profile_id, revision, expected in (
            ("missing.profile", None, "unknown_profile"),
            ("generator_g0_g5", "2.0.0", "profile_revision_mismatch"),
        ):
            with self.subTest(profile_id=profile_id), self.assertRaises(
                ProfileEngineError
            ) as captured:
                get_profile_definition(profile_id, revision=revision)
            self.assertEqual(captured.exception.code, expected)


class DatasetProfileDescriptorTest(unittest.TestCase):
    def test_descriptor_binds_data_evaluation_slices_and_privacy(self) -> None:
        descriptor = load_dataset_profile_descriptor(FIXTURE / "dataset_profile_descriptor.json")
        document = descriptor.to_dict()
        self.assertEqual(descriptor.descriptor_id, "vg-dormant-profile-v1")
        self.assertEqual(
            [row["role"] for row in document["split_bindings"]],
            ["train", "validation", "test"],
        )
        self.assertEqual(document["evaluation"]["cutoff"], 10)
        self.assertEqual(document["evaluation"]["publication_depth"], 100)
        self.assertTrue(all(value is False for key, value in document["privacy"].items() if key.endswith("exported")))

    def test_descriptor_hash_privacy_depth_and_strict_fields_fail_closed(self) -> None:
        base = load_json("dataset_profile_descriptor.json")
        cases = []

        hash_tamper = copy.deepcopy(base)
        hash_tamper["descriptor_id"] = "tampered"
        cases.append((hash_tamper, "content_hash_mismatch"))

        privacy = copy.deepcopy(base)
        privacy["privacy"]["source_item_ids_exported"] = True
        cases.append((with_content_sha256(privacy), "privacy_boundary_violation"))

        depth = copy.deepcopy(base)
        depth["evaluation"]["publication_depth"] = 5
        cases.append((with_content_sha256(depth), "invalid_evaluation_depth"))

        unknown = copy.deepcopy(base)
        unknown["unexpected"] = "field"
        cases.append((with_content_sha256(unknown), "unknown_field"))

        split_order = copy.deepcopy(base)
        split_order["split_bindings"][0], split_order["split_bindings"][1] = (
            split_order["split_bindings"][1],
            split_order["split_bindings"][0],
        )
        cases.append((with_content_sha256(split_order), "noncanonical_split_order"))

        for value, expected in cases:
            with self.subTest(expected=expected), self.assertRaises(
                ProfileEngineError
            ) as captured:
                validate_dataset_profile_descriptor(value)
            self.assertEqual(captured.exception.code, expected)


class ProfileConformanceReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.descriptor = load_dataset_profile_descriptor(
            FIXTURE / "dataset_profile_descriptor.json"
        )

    def test_all_registered_positive_fixtures_derive_public_status_labels(self) -> None:
        expected = {
            "generator_report.json": "named_adapter",
            "overlay_report.json": "named_overlay_adapter",
            "release_report.json": "local_release_ready",
            "static_mapping_report.json": "c0_c5_pass",
        }
        for name, label in expected.items():
            with self.subTest(name=name):
                report = load_profile_conformance_report(
                    FIXTURE / name, descriptor=self.descriptor
                )
                self.assertEqual(report.decision_status, "pass")
                self.assertEqual(report.status_label, label)

    def test_builder_derives_partial_generator_and_static_mapping_labels(self) -> None:
        descriptor_artifact = {
            "artifact_id": "dataset-profile-descriptor",
            "role": "dataset_profile_descriptor",
            "schema_id": self.descriptor.schema,
            "schema_revision": self.descriptor.schema_revision,
            "content_sha256": self.descriptor.content_sha256,
        }
        cases = (
            ("generator_g0_g5", "close_named_adapter"),
            (
                "static_mapping_c0_c5",
                "auditable_snapshot_not_fully_regenerable",
            ),
        )
        for profile_id, expected_label in cases:
            profile = get_profile_definition(profile_id)
            gate_results = [
                {"gate_id": gate.gate_id, "status": "pass", "failure": None}
                for gate in profile.gates
            ]
            last = profile.gates[-1]
            gate_results[-1] = {
                "gate_id": last.gate_id,
                "status": "partial",
                "failure": {"code": last.failure_code, "detail": "fixture partial"},
            }
            report = build_profile_conformance_report(
                report_id=f"partial-{profile_id}",
                producer={"name": "test", "version": "1"},
                profile_id=profile_id,
                descriptor=self.descriptor,
                artifacts=[descriptor_artifact],
                gate_results=gate_results,
            )
            self.assertEqual(report.decision_status, "partial")
            self.assertEqual(report.status_label, expected_label)

    def test_unknown_profile_gate_order_and_dependency_fail_closed(self) -> None:
        base = load_json("generator_report.json")

        unknown_profile = copy.deepcopy(base)
        unknown_profile["profile_binding"]["profile_id"] = "missing.profile"
        unknown_profile = with_content_sha256(unknown_profile)
        with self.assertRaises(ProfileEngineError) as captured:
            validate_profile_conformance_report(unknown_profile, descriptor=self.descriptor)
        self.assertEqual(captured.exception.code, "unknown_profile")

        wrong_order = copy.deepcopy(base)
        wrong_order["gates"][1], wrong_order["gates"][2] = (
            wrong_order["gates"][2],
            wrong_order["gates"][1],
        )
        wrong_order = with_content_sha256(wrong_order)
        with self.assertRaises(ProfileEngineError) as captured:
            validate_profile_conformance_report(wrong_order, descriptor=self.descriptor)
        self.assertEqual(captured.exception.code, "noncanonical_gate_order")

        dependency = copy.deepcopy(base)
        dependency["gates"][0] = {
            "gate_id": "G0",
            "status": "fail",
            "failure": {
                "code": "source_identity_failure",
                "detail": "fixture source failure",
            },
        }
        dependency["decision"] = {
            "status": "fail",
            "status_label": "generator_rejected",
        }
        dependency = with_content_sha256(dependency)
        with self.assertRaises(ProfileEngineError) as captured:
            validate_profile_conformance_report(dependency, descriptor=self.descriptor)
        self.assertEqual(captured.exception.code, "gate_dependency_status_mismatch")

    def test_binding_hash_and_status_label_fail_closed(self) -> None:
        base = load_json("generator_report.json")
        binding = copy.deepcopy(base)
        binding["descriptor_binding"]["content_sha256"] = "ff" * 32
        binding = with_content_sha256(binding)
        with self.assertRaises(ProfileEngineError) as captured:
            validate_profile_conformance_report(binding, descriptor=self.descriptor)
        self.assertEqual(captured.exception.code, "descriptor_binding_mismatch")

        hash_tamper = copy.deepcopy(base)
        hash_tamper["report_id"] = "tampered-report"
        with self.assertRaises(ProfileEngineError) as captured:
            validate_profile_conformance_report(hash_tamper, descriptor=self.descriptor)
        self.assertEqual(captured.exception.code, "content_hash_mismatch")

        label = copy.deepcopy(base)
        label["decision"]["status_label"] = "caller_selected_label"
        label = with_content_sha256(label)
        with self.assertRaises(ProfileEngineError) as captured:
            validate_profile_conformance_report(label, descriptor=self.descriptor)
        self.assertEqual(captured.exception.code, "unsupported_status_label")

    def test_negative_fixture_inventory_matches_typed_regressions(self) -> None:
        inventory = load_json("expected_failures.json")
        self.assertEqual(
            {row["expected_code"] for row in inventory["cases"]},
            {
                "unknown_profile",
                "noncanonical_gate_order",
                "gate_dependency_status_mismatch",
                "descriptor_binding_mismatch",
                "content_hash_mismatch",
                "unsupported_status_label",
                "privacy_boundary_violation",
                "invalid_evaluation_depth",
            },
        )


if __name__ == "__main__":
    unittest.main()
