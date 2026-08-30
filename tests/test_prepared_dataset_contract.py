from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main
from sidinspector.contracts import (
    PreparedDatasetValidationError,
    from_rpg_prepared_dataset,
    load_dataset_identity,
    load_prepared_dataset,
    load_sid_space_identity,
    prepared_dataset_schema_path,
    require_regeneration_for_legacy_prepared,
    validate_prepared_dataset,
    validate_prepared_dataset_bindings,
    with_content_sha256,
)
from tools.verify_sidscope_sprint2_contracts import verify_sprint2_contracts


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "prepared_dataset_fixture"


class PreparedDatasetContractTest(unittest.TestCase):
    def load_triplet(self):
        return (
            load_dataset_identity(FIXTURE / "dataset_identity.json"),
            load_sid_space_identity(FIXTURE / "sid_space_identity.json"),
            load_prepared_dataset(FIXTURE / "prepared_dataset.json"),
        )

    def test_positive_fixture_has_exact_dependency_bindings(self) -> None:
        dataset, sid_space, prepared = self.load_triplet()
        validate_prepared_dataset_bindings(prepared, dataset, sid_space)
        self.assertEqual(prepared.catalog.scope, "train_only")
        self.assertFalse(prepared.normalization["source_item_ids_exported"])

    def test_rpg_bridge_migrates_with_exact_fixture_parity(self) -> None:
        legacy = json.loads(
            (ROOT / "examples/rpg_non_ar_bridge_fixture/prepared_dataset.json").read_text(
                encoding="utf-8"
            )
        )
        migration = from_rpg_prepared_dataset(legacy)
        dataset, sid_space, prepared = self.load_triplet()
        self.assertEqual(migration.dataset_identity, dataset)
        self.assertEqual(migration.sid_space_identity, sid_space)
        self.assertEqual(migration.prepared_dataset, prepared)

    def test_privacy_negative_and_binding_mismatch_fail_closed(self) -> None:
        with self.assertRaises(PreparedDatasetValidationError) as captured:
            load_prepared_dataset(FIXTURE / "expected_failure_source_item_ids_exported.json")
        self.assertEqual(captured.exception.code, "normalization_or_privacy_mismatch")

        dataset, sid_space, prepared = self.load_triplet()
        document = prepared.to_dict()
        document["sid_space_binding"]["content_sha256"] = "0" * 64
        rebound = validate_prepared_dataset(with_content_sha256(document))
        with self.assertRaises(PreparedDatasetValidationError) as captured:
            validate_prepared_dataset_bindings(rebound, dataset, sid_space)
        self.assertEqual(captured.exception.code, "sid_space_binding_mismatch")

    def test_incomplete_legacy_prepared_routes_require_regeneration(self) -> None:
        for rel_path in (
            "examples/diffgrm_masked_diffusion_fixture/prepared_dataset.json",
            "examples/llada_rec_trained_trace_fixture/prepared_dataset.json",
        ):
            value = json.loads((ROOT / rel_path).read_text(encoding="utf-8"))
            with self.subTest(schema=value["schema"]), self.assertRaises(
                PreparedDatasetValidationError
            ) as captured:
                require_regeneration_for_legacy_prepared(value)
            self.assertEqual(captured.exception.code, "legacy_prepared_regeneration_required")

    def test_schema_cli_and_sprint_verifier_pass(self) -> None:
        schema = json.loads(prepared_dataset_schema_path().read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema"]["const"], "sidscope.prepared_dataset.v1")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "contract", "validate", "--type", "prepared-dataset",
                    "--input", str(FIXTURE / "prepared_dataset.json"),
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["prepared_dataset_id"], "rpg:rpg-prepared-fixture")
        self.assertTrue(verify_sprint2_contracts()["rpg_migration_parity"])


if __name__ == "__main__":
    unittest.main()
