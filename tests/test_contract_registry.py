from __future__ import annotations

import json
import unittest
from pathlib import Path

from sidinspector.contracts import (
    ContractRegistryError,
    contract_registry_path,
    load_contract_registry,
    validate_contract_registry,
    with_content_sha256,
)


ROOT = Path(__file__).resolve().parents[1]


class ContractRegistryTest(unittest.TestCase):
    def registry_document(self) -> dict[str, object]:
        return json.loads(contract_registry_path().read_text(encoding="utf-8"))

    def assert_registry_failure(self, document: dict[str, object], code: str) -> None:
        with self.assertRaises(ContractRegistryError) as captured:
            validate_contract_registry(with_content_sha256(document))
        self.assertEqual(captured.exception.code, code)

    def test_checked_in_registry_and_resources_are_complete(self) -> None:
        registry = load_contract_registry(repository_root=ROOT)

        self.assertEqual(registry.schema, "sidscope.contract_registry.v1")
        self.assertEqual(registry.schema_revision, "1.0.0")
        self.assertEqual(
            [item.contract_type for item in registry.contracts],
            [
                "dataset-identity",
                "prepared-dataset",
                "sid-space-identity",
                "source-identity",
            ],
        )
        for descriptor in registry.contracts:
            self.assertEqual(descriptor.compatibility, "exact_major_supported_revision")
            self.assertEqual(descriptor.supported_revisions, ("1.0.0",))
            self.assertTrue(descriptor.negative_fixtures)

    def test_unknown_dependency_fails_closed(self) -> None:
        document = self.registry_document()
        document["contracts"][0]["dependencies"] = [
            {
                "schema_id": "sidscope." + "unknown.v1",
                "accepted_revisions": ["1.0.0"],
            }
        ]
        self.assert_registry_failure(document, "unknown_dependency")

    def test_dependency_cycle_fails_closed(self) -> None:
        document = self.registry_document()
        dataset = document["contracts"][0]
        source = document["contracts"][3]
        dataset["dependencies"] = [
            {"schema_id": source["schema_id"], "accepted_revisions": ["1.0.0"]}
        ]
        source["dependencies"] = [
            {"schema_id": dataset["schema_id"], "accepted_revisions": ["1.0.0"]}
        ]
        self.assert_registry_failure(document, "dependency_cycle")

    def test_incompatible_dependency_revision_fails_closed(self) -> None:
        document = self.registry_document()
        dataset = document["contracts"][0]
        source = document["contracts"][3]
        dataset["dependencies"] = [
            {"schema_id": source["schema_id"], "accepted_revisions": ["2.0.0"]}
        ]
        self.assert_registry_failure(document, "incompatible_dependency")

    def test_unsupported_revision_fails_closed(self) -> None:
        document = self.registry_document()
        document["contracts"][0]["schema_revision"] = "1.1.0"
        self.assert_registry_failure(document, "unsupported_schema_revision")

    def test_registry_canonical_order_is_enforced(self) -> None:
        document = self.registry_document()
        document["contracts"] = list(reversed(document["contracts"]))
        self.assert_registry_failure(document, "noncanonical_contract_order")


if __name__ == "__main__":
    unittest.main()
