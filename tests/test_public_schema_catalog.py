from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from sidinspector.schemas.result_contracts import CLI_RESULT_SCHEMA_IDS
from sidinspector.contracts import with_content_sha256
from sidinspector.schemas.catalog import (
    PublicSchemaValidationError,
    load_public_schema_catalog,
    validate_public_document,
)


ROOT = Path(__file__).resolve().parents[1]


class PublicSchemaCatalogTest(unittest.TestCase):
    def test_every_bundled_schema_has_one_owner_and_semantic_validator(self) -> None:
        catalog = load_public_schema_catalog()
        schema_resources = sorted(
            path.name
            for path in (ROOT / "src/sidinspector/schemas").glob("*.schema.json")
        )
        self.assertEqual(len(catalog), 46)
        self.assertEqual(
            sorted(set(item.schema_resource for item in catalog)), schema_resources
        )
        self.assertEqual(
            [item.schema_id for item in catalog],
            sorted(set(item.schema_id for item in catalog)),
        )
        self.assertTrue(
            set(CLI_RESULT_SCHEMA_IDS).issubset(item.schema_id for item in catalog)
        )
        self.assertTrue(all(item.owner and item.semantic_validator for item in catalog))

    def test_canonical_contract_passes_both_validation_layers(self) -> None:
        value = json.loads(
            (ROOT / "examples/dataset_identity_fixture/dataset_identity.json").read_text(
                encoding="utf-8"
            )
        )
        descriptor = validate_public_document(value)
        self.assertEqual(descriptor.schema_id, "sidscope.dataset_identity.v1")

    def test_shallow_native_schema_cannot_bypass_semantic_validation(self) -> None:
        value = json.loads(
            (
                ROOT
                / "examples/native_trace_payload_fixtures/masked_diffusion.json"
            ).read_text(encoding="utf-8")
        )
        changed = copy.deepcopy(value)
        del changed["episodes"][0]["steps"][0]["selected_positions"]
        changed = with_content_sha256(changed)
        with self.assertRaises(PublicSchemaValidationError) as caught:
            validate_public_document(changed)
        self.assertEqual(caught.exception.code, "invalid_fields")

    def test_structural_failure_precedes_semantic_validation(self) -> None:
        value = {
            "schema": "sidscope.dataset_identity.v1",
            "schema_revision": "1.0.0",
        }
        with self.assertRaises(PublicSchemaValidationError) as caught:
            validate_public_document(value)
        self.assertEqual(caught.exception.code, "structural_schema_violation")


if __name__ == "__main__":
    unittest.main()
