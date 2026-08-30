from __future__ import annotations

import contextlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main
from sidinspector.contracts import (
    SourceIdentityValidationError,
    canonical_artifact_sha256,
    canonical_json_bytes,
    from_legacy_adapter_manifest,
    load_source_identity,
    source_identity_schema_path,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "source_identity_fixture"


class SourceIdentityContractTest(unittest.TestCase):
    def test_canonical_json_is_order_independent_and_rejects_nonfinite_numbers(self) -> None:
        self.assertEqual(
            canonical_json_bytes({"b": 2, "a": 1}),
            canonical_json_bytes({"a": 1, "b": 2}),
        )
        with self.assertRaises(ValueError):
            canonical_json_bytes({"value": math.nan})

    def test_positive_fixture_round_trips_and_hashes(self) -> None:
        identity = load_source_identity(FIXTURE / "source_identity.json")
        document = identity.to_dict()

        self.assertEqual(identity.schema, "sidscope.source_identity.v1")
        self.assertEqual(identity.schema_revision, "1.0.0")
        self.assertEqual(identity.content_sha256, canonical_artifact_sha256(document))
        self.assertEqual(load_source_identity(FIXTURE / "source_identity.json"), identity)

    def test_expected_failure_is_typed_hash_mismatch(self) -> None:
        with self.assertRaises(SourceIdentityValidationError) as captured:
            load_source_identity(FIXTURE / "expected_failure_content_hash_mismatch.json")

        self.assertEqual(captured.exception.code, "content_hash_mismatch")

    def test_legacy_adapter_manifest_preserves_source_fields(self) -> None:
        path = (
            ROOT
            / "docs"
            / "reproducibility"
            / "conformance"
            / "resot_instruments_manifest.json"
        )
        legacy = json.loads(path.read_text(encoding="utf-8"))
        identity = from_legacy_adapter_manifest(legacy)
        source = legacy["source"]

        self.assertEqual(identity.source_id, legacy["artifact_id"])
        self.assertEqual(identity.paper.title, legacy["paper_label"])
        self.assertEqual(identity.repository.url, source["url"])
        self.assertEqual(identity.repository.revision, source["revision"])
        self.assertEqual(identity.license.status, source["license_status"])
        self.assertEqual(identity.license.identifier, source["license_identifier"])
        self.assertEqual(
            identity.license.redistribution_policy,
            source["redistribution_policy"],
        )
        self.assertEqual(identity.derivation, source["derivation"])
        self.assertEqual(identity.artifact_name, source["artifact_name"])

    def test_schema_is_bundled_with_package(self) -> None:
        schema = json.loads(source_identity_schema_path().read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["properties"]["schema"]["const"],
            "sidscope.source_identity.v1",
        )

    def test_cli_positive_and_negative_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                positive = cli_main(
                    [
                        "contract",
                        "validate",
                        "--type",
                        "source-identity",
                        "--input",
                        str(FIXTURE / "source_identity.json"),
                        "--result-json",
                        str(result_path),
                    ]
                )
            result = json.loads(result_path.read_text(encoding="utf-8"))

            self.assertEqual(positive, 0)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["failure"], None)
            self.assertIn('"status": "pass"', stdout.getvalue())

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                negative = cli_main(
                    [
                        "contract",
                        "validate",
                        "--type",
                        "source-identity",
                        "--input",
                        str(FIXTURE / "expected_failure_content_hash_mismatch.json"),
                    ]
                )
            failure = json.loads(stdout.getvalue())

        self.assertEqual(negative, 2)
        self.assertEqual(failure["status"], "fail")
        self.assertEqual(failure["failure"]["code"], "content_hash_mismatch")


if __name__ == "__main__":
    unittest.main()
