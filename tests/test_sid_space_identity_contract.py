from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main
from sidinspector.contracts import (
    SIDSpaceIdentityValidationError,
    canonical_artifact_sha256,
    load_sid_space_identity,
    sid_space_identity_from_legacy_adapter_manifest,
    sid_space_identity_schema_path,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "prepared_dataset_fixture"


class SIDSpaceIdentityContractTest(unittest.TestCase):
    def test_positive_fixture_round_trips_and_hashes(self) -> None:
        identity = load_sid_space_identity(FIXTURE / "sid_space_identity.json")

        self.assertEqual(identity.schema, "sidscope.sid_space_identity.v1")
        self.assertEqual(identity.structure.tuple_kind, "unordered_set")
        self.assertEqual(identity.structure.depth, 2)
        self.assertTrue(identity.vocabulary.position_disjoint)
        self.assertEqual(identity.content_sha256, canonical_artifact_sha256(identity.to_dict()))

    def test_overlapping_position_vocabulary_fails_closed(self) -> None:
        with self.assertRaises(SIDSpaceIdentityValidationError) as captured:
            load_sid_space_identity(
                FIXTURE / "expected_failure_overlapping_position_vocabulary.json"
            )
        self.assertEqual(captured.exception.code, "overlapping_position_vocabulary")

    def test_legacy_adapter_manifests_preserve_depth_and_cache_hash(self) -> None:
        checked = 0
        for path in sorted(
            (ROOT / "docs/reproducibility/conformance").glob("*_manifest.json")
        ):
            legacy = json.loads(path.read_text(encoding="utf-8"))
            if legacy.get("schema_version") != "sidscope.adapter_manifest.v1":
                continue
            identity = sid_space_identity_from_legacy_adapter_manifest(legacy)
            self.assertEqual(identity.identity_status, "legacy_partial")
            self.assertEqual(identity.structure.depth, legacy["dataset"]["sid_depth"])
            self.assertEqual(
                identity.tokenizer.artifact_sha256,
                legacy["input_sha256"]["sid_assignments"],
            )
            checked += 1
        self.assertGreaterEqual(checked, 9)

    def test_schema_and_cli_are_bundled(self) -> None:
        schema = json.loads(sid_space_identity_schema_path().read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema"]["const"], "sidscope.sid_space_identity.v1")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "contract", "validate", "--type", "sid-space-identity",
                    "--input", str(FIXTURE / "sid_space_identity.json"),
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["sid_space_id"], "rpg:rpg-prepared-fixture")


if __name__ == "__main__":
    unittest.main()
