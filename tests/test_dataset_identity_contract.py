from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main
from sidinspector.contracts import (
    DatasetIdentityValidationError,
    canonical_artifact_sha256,
    dataset_identity_from_legacy_adapter_manifest,
    dataset_identity_schema_path,
    load_dataset_identity,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "dataset_identity_fixture"


class DatasetIdentityContractTest(unittest.TestCase):
    def test_positive_fixture_round_trips_and_hashes(self) -> None:
        identity = load_dataset_identity(FIXTURE / "dataset_identity.json")

        self.assertEqual(identity.schema, "sidscope.dataset_identity.v1")
        self.assertEqual(identity.identity_status, "fully_bound")
        self.assertEqual([split.role for split in identity.splits], ["train", "validation", "test"])
        self.assertEqual(identity.content_sha256, canonical_artifact_sha256(identity.to_dict()))

    def test_typed_negative_fixtures_fail_closed(self) -> None:
        cases = {
            "expected_failure_content_hash_mismatch.json": "content_hash_mismatch",
            "expected_failure_split_order.json": "noncanonical_split_order",
        }
        for name, expected in cases.items():
            with self.subTest(name=name), self.assertRaises(DatasetIdentityValidationError) as captured:
                load_dataset_identity(FIXTURE / name)
            self.assertEqual(captured.exception.code, expected)

    def test_all_legacy_adapter_manifests_preserve_dataset_fields(self) -> None:
        manifests = sorted(
            (ROOT / "docs" / "reproducibility" / "conformance").glob("*_manifest.json")
        )
        self.assertGreaterEqual(len(manifests), 9)
        for path in manifests:
            legacy = json.loads(path.read_text(encoding="utf-8"))
            if legacy.get("schema_version") != "sidscope.adapter_manifest.v1":
                continue
            with self.subTest(path=path.name):
                migration = dataset_identity_from_legacy_adapter_manifest(legacy)
                dataset = legacy["dataset"]
                identity = migration.identity
                self.assertEqual(identity.dataset.name, dataset["name"])
                self.assertEqual(
                    identity.dataset.normalized_name,
                    dataset.get("normalized_name", dataset["name"]),
                )
                self.assertEqual(identity.catalog.item_count, dataset["expected_items"])
                self.assertEqual(identity.target_universe.item_count, dataset["expected_items"])
                self.assertEqual(migration.deferred_sid_depth, dataset["sid_depth"])
                self.assertEqual(identity.identity_status, "legacy_partial")
                self.assertEqual(identity.splits, ())

    def test_schema_is_bundled_with_package(self) -> None:
        schema = json.loads(dataset_identity_schema_path().read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["properties"]["schema"]["const"],
            "sidscope.dataset_identity.v1",
        )

    def test_cli_lists_shows_and_validates_registered_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            with contextlib.redirect_stdout(io.StringIO()):
                listed = cli_main(["contract", "list", "--result-json", str(result_path)])
            listing = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(listed, 0)
            self.assertEqual(listing["contract_count"], 11)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                shown = cli_main(["contract", "show", "--type", "dataset-identity"])
            show = json.loads(stdout.getvalue())
            self.assertEqual(shown, 0)
            self.assertEqual(show["contract"]["schema_id"], "sidscope.dataset_identity.v1")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                validated = cli_main(
                    [
                        "contract", "validate", "--type", "dataset-identity",
                        "--input", str(FIXTURE / "dataset_identity.json"),
                    ]
                )
            validation = json.loads(stdout.getvalue())
            self.assertEqual(validated, 0)
            self.assertEqual(validation["dataset_id"], "synthetic-rpg.fixture-v1")

    def test_cli_unknown_type_and_typed_negative_fail(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            unknown = cli_main(["contract", "show", "--type", "not-registered"])
        self.assertEqual(unknown, 2)
        self.assertEqual(json.loads(stdout.getvalue())["failure"]["code"], "unknown_contract_type")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            negative = cli_main(
                [
                    "contract", "validate", "--type", "dataset-identity",
                    "--input", str(FIXTURE / "expected_failure_split_order.json"),
                ]
            )
        self.assertEqual(negative, 2)
        self.assertEqual(
            json.loads(stdout.getvalue())["failure"]["code"],
            "noncanonical_split_order",
        )


if __name__ == "__main__":
    unittest.main()
