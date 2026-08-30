from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from sidinspector.cli import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "evidence_system_fixture"


def invoke(argv: list[str]) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = cli_main(argv)
    return code, json.loads(output.getvalue())


class EvidenceCLITest(unittest.TestCase):
    def test_bundle_build_verify_and_typed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.json"
            code, built = invoke(
                [
                    "evidence", "bundle", "build",
                    "--spec", str(FIXTURE / "baseline_bundle_spec.json"),
                    "--output", str(output),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(built["schema"], "sidscope.evidence_bundle.v1")
            code, verified = invoke(
                ["evidence", "bundle", "verify", "--input", str(output)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(verified["status"], "pass")

        code, failed = invoke(
            [
                "evidence", "bundle", "verify",
                "--input", str(FIXTURE / "expected_failure_unsupported_rank.json"),
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(failed["failure"]["code"], "unsupported_exact_rank_claim")

    def test_registry_full_command_surface(self) -> None:
        public = FIXTURE / "public_conformance_summary.json"
        digest = hashlib.sha256(public.read_bytes()).hexdigest()
        baseline = FIXTURE / "baseline_bundle.json"
        correction = FIXTURE / "correction_bundle.json"
        baseline_sha = json.loads(baseline.read_text(encoding="utf-8"))["content_sha256"]
        correction_sha = json.loads(correction.read_text(encoding="utf-8"))["content_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "store"
            code, added = invoke(
                [
                    "registry", "add", "--store", str(store),
                    "--bundle", str(baseline),
                    "--artifact", f"{digest}={public}",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(added["bundle_sha256s"], [baseline_sha])

            code, superseded = invoke(
                [
                    "registry", "supersede", "--store", str(store),
                    "--prior", baseline_sha, "--bundle", str(correction),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(superseded["replacement_bundle_sha256"], correction_sha)

            code, listing = invoke(["registry", "list", "--store", str(store)])
            self.assertEqual(code, 0)
            self.assertEqual(len(listing["bundles"]), 2)
            code, comparison = invoke(
                [
                    "registry", "compare", "--store", str(store),
                    "--left", baseline_sha, "--right", correction_sha,
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(comparison["status"], "compatible")

            code, quarantine = invoke(
                [
                    "registry", "quarantine", "--store", str(store),
                    "--sha256", baseline_sha, "--reason", "fixture audit",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(quarantine["operation"], "quarantine")

            exported = Path(tmp) / "registry.json"
            code, export = invoke(
                ["registry", "export", "--store", str(store), "--output", str(exported)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(export["schema"], "sidscope.evidence_registry_projection.v1")
            self.assertIn("quarantined", {row["status"] for row in export["bundles"]})
            (store / "registry.sqlite3").unlink()
            code, rebuilt = invoke(["registry", "rebuild", "--store", str(store)])
            self.assertEqual(code, 0)
            self.assertEqual(rebuilt["bundle_count"], 2)
            self.assertEqual(rebuilt["quarantined_bundle_count"], 1)
            rebuilt_exported = Path(tmp) / "registry-rebuilt.json"
            code, after = invoke(
                [
                    "registry", "export", "--store", str(store),
                    "--output", str(rebuilt_exported),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(after, export)


if __name__ == "__main__":
    unittest.main()
