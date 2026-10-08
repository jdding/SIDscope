from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from verify_sidscope_1_6_hardening import (
    verify,
    verify_adoption,
    verify_api,
    verify_comparison,
    verify_compatibility,
    verify_migration,
)


class SIDScope16HardeningTest(unittest.TestCase):
    def test_release_versions_replay_the_unchanged_historical_matrix(self):
        for version in ("2.0.0rc1", "2.0.0"):
            with self.subTest(version=version), patch("verify_sidscope_1_6_hardening.verify_release_metadata", return_value={"package_version": version}):
                self.assertEqual(verify_compatibility()["axis_count"], 6)

    def test_unreviewed_release_versions_fail_closed(self):
        for version in ("2.0.0rc0", "2.0.1", "3.0.0"):
            with self.subTest(version=version), patch("verify_sidscope_1_6_hardening.verify_release_metadata", return_value={"package_version": version}):
                with self.assertRaisesRegex(AssertionError, "unsupported"):
                    verify_compatibility()

    def test_compatibility_matrix_positive_and_typed_negative_cases(self) -> None:
        result = verify_compatibility()
        self.assertEqual(result["axis_count"], 6)
        self.assertEqual(result["typed_negative_count"], 6)

    def test_all_legacy_routes_have_replay_or_immutable_record(self) -> None:
        result = verify_migration()
        self.assertEqual(result["record_count"], 15)
        self.assertEqual(
            result["canonical_replay_count"]
            + result["immutable_historical_record_count"],
            15,
        )
        self.assertEqual(result["legacy_status_parity"], "pass")

    def test_cross_family_comparison_uses_one_compatible_contract(self) -> None:
        result = verify_comparison()
        self.assertEqual(result["status"], "compatible")
        self.assertNotEqual(result["left_family"], result["right_family"])

    def test_candidate_api_and_every_wrapper_are_owned(self) -> None:
        result = verify_api()
        self.assertEqual(result["public_module_count"], 8)
        self.assertEqual(result["owned_wrapper_count"], 7)

    def test_external_plugin_replays_without_core_edit(self) -> None:
        result = verify_adoption()
        self.assertEqual(result["public_documentation_replay"], "pass")
        self.assertEqual(result["core_sha256_before"], result["core_sha256_after"])

    def test_gate_dispatch_is_cpu_only(self) -> None:
        result = verify("api")
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["gpu_required"])


if __name__ == "__main__":
    unittest.main()
