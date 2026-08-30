from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from sidinspector.adapters import (
    LATTE_TOKENIZER_OPTIONAL_DISTRIBUTIONS,
    latte_tokenizer_runtime_status,
    load_sentence_transformer,
    model_reference_kind,
)
from tools.build_sidscope_release_candidate_archive import FIXED_ZIP_TIMESTAMP, build_archive
from tools.run_sidscope_public_url_smoke import clone_command, smoke_commands
from tools.run_sidscope_g8_fresh_env_smoke import fresh_env_install_commands
from tools.run_sidscope_realistic_tutorial import run_tutorial
from tools.smoke_sidscope_release_candidate_archive import smoke_archive
from tools.verify_sidscope_claim_ledger import verify_ledger
from tools.verify_sidscope_architecture_inventory import verify_inventory
from tools.verify_sidscope_release_metadata import verify_release_metadata
from tools.verify_sidscope_resource_package import (
    ROOT,
    check_forbidden_public_content,
    check_forbidden_tracked,
    expand_public_manifest_paths,
    scanned_package_files,
    tracked_files,
    validate_release_manifest,
)


class SIDScopeResourcePackageTest(unittest.TestCase):
    def test_latte_accepts_local_sentence_t5_path_without_name_heuristic(self) -> None:
        calls: list[tuple[str, bool]] = []

        def fake_loader(model_reference: str, *, local_files_only: bool) -> object:
            calls.append((model_reference, local_files_only))
            return object()

        with tempfile.TemporaryDirectory() as tmp:
            local_model = Path(tmp) / "local_sentence_t5_checkpoint"
            local_model.mkdir()

            self.assertEqual(model_reference_kind(local_model), "local_path")
            loaded = load_sentence_transformer(local_model, loader=fake_loader)

        self.assertIsNotNone(loaded)
        self.assertEqual(calls, [(str(local_model), True)])

    def test_latte_tokenizer_extra_is_hermetic_and_datasets_free(self) -> None:
        requested_imports: list[str] = []

        def fake_finder(module_name: str) -> object:
            requested_imports.append(module_name)
            return object()

        status = latte_tokenizer_runtime_status(fake_finder)

        self.assertEqual(
            LATTE_TOKENIZER_OPTIONAL_DISTRIBUTIONS,
            ("faiss-cpu", "sentence-transformers"),
        )
        self.assertTrue(status["ready"])
        self.assertFalse(status["datasets_required"])
        self.assertEqual(requested_imports, ["faiss", "sentence_transformers"])
        self.assertNotIn("datasets", requested_imports)

        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        latte_extra = pyproject.split("[project.optional-dependencies]", 1)[1].split(
            "[project.urls]", 1
        )[0]
        self.assertIn('"faiss-cpu>=1.8,<2"', latte_extra)
        self.assertIn('"sentence-transformers>=3.0,<6"', latte_extra)
        self.assertNotIn("datasets", latte_extra)

    def test_forbidden_tracked_patterns_catch_private_artifacts(self) -> None:
        findings = check_forbidden_tracked(
            [
                "src/sidinspector/metrics.py",
                "experiments/v1_evidence_chain/autodl/returned/archive.tgz",
                "experiments/v1_evidence_chain/foo/cache.parquet",
            ]
        )
        self.assertEqual(
            findings,
            [
                "experiments/v1_evidence_chain/autodl/returned/archive.tgz",
                "experiments/v1_evidence_chain/foo/cache.parquet",
            ],
        )

    def test_sampled_regeneration_script_has_default_output_contract(self) -> None:
        from tools.run_sidscope_sampled_regeneration import DEFAULT_OUTPUT

        self.assertTrue(str(DEFAULT_OUTPUT).endswith("examples/sidscope_sampled_regeneration_output"))

    def test_release_candidate_manifest_validates(self) -> None:
        result = validate_release_manifest(
            ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"
        )

        self.assertGreaterEqual(result["public_package_rows"], 10)
        self.assertEqual(result["pending_rows"], 0)

    def test_release_candidate_manifest_expands_to_tracked_public_files(self) -> None:
        expanded = expand_public_manifest_paths(
            ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
            tracked_files(),
        )

        self.assertIn("README.md", expanded)
        self.assertIn("setup.py", expanded)
        self.assertIn("tools/verify_sidscope_resource_package.py", expanded)
        self.assertIn("tools/run_sidscope_usage_demo.py", expanded)
        self.assertIn("tools/run_sidscope_g8_fresh_env_smoke.py", expanded)
        self.assertIn("tools/run_sidscope_public_url_smoke.py", expanded)
        self.assertIn("docs/SIDSCOPE_RELEASE_CHECKLIST.md", expanded)
        self.assertIn("docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md", expanded)
        self.assertIn("docs/V1_2_TO_V2_ROADMAP.md", expanded)
        self.assertIn("docs/adr/0001-product-boundary.md", expanded)
        self.assertIn("docs/adr/0002-local-first-modular-platform.md", expanded)
        self.assertIn("docs/adr/0003-canonical-identity-versioning-hashing.md", expanded)
        self.assertIn("docs/adr/0004-module-boundaries-and-cli-identity.md", expanded)
        self.assertIn("docs/adr/0005-contract-registry-and-dataset-identity.md", expanded)
        self.assertIn("docs/adr/0006-sid-space-and-prepared-dataset-boundary.md", expanded)
        self.assertIn("docs/CONTRACT_REGISTRY.md", expanded)
        self.assertIn("examples/dataset_identity_fixture/dataset_identity.json", expanded)
        self.assertIn("examples/prepared_dataset_fixture/prepared_dataset.json", expanded)
        self.assertIn("tools/verify_sidscope_contract_registry.py", expanded)
        self.assertIn("tools/verify_sidscope_sprint2_contracts.py", expanded)
        self.assertIn("tests/test_dataset_identity_contract.py", expanded)
        self.assertIn("tests/test_sid_space_identity_contract.py", expanded)
        self.assertIn("tests/test_prepared_dataset_contract.py", expanded)
        self.assertIn(".github/workflows/ci.yml", expanded)
        self.assertIn("docs/VERSIONING.md", expanded)
        self.assertIn("docs/COMPATIBILITY.md", expanded)
        self.assertIn("docs/reproducibility/sidscope_architecture_inventory.json", expanded)
        self.assertIn("docs/SIDSCOPE_USAGE_DEMO.md", expanded)
        self.assertIn("docs/reproducibility/g14_usage_demo_decisions.csv", expanded)
        self.assertIn(
            "docs/reproducibility/latte_psid_trained_trace_evidence.json", expanded
        )
        self.assertIn(
            "docs/reproducibility/diffgrm_www2026_trained_trace_evidence.json",
            expanded,
        )
        self.assertIn("tools/run_diffgrm_resumable_training.py", expanded)
        self.assertIn("tests/test_diffgrm_dataset_bridge.py", expanded)
        self.assertIn(
            "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json",
            expanded,
        )
        self.assertIn(
            "examples/latte_psid_trained_trace_real_smoke/latte_amazon_vg_1_per_bucket_s2024.json",
            expanded,
        )
        self.assertNotIn("experiments/v1_evidence_chain/autodl/payloads", expanded)

    def test_system_architecture_and_v2_roadmap_share_one_layer_vocabulary(self) -> None:
        architecture = (ROOT / "docs" / "SIDSCOPE_SYSTEM_ARCHITECTURE.md").read_text(
            encoding="utf-8"
        )
        roadmap = (ROOT / "docs" / "V1_2_TO_V2_ROADMAP.md").read_text(
            encoding="utf-8"
        )

        owned_layers = [
            "Integration Layer",
            "Contract Layer",
            "Observation Layer",
            "Evaluation Layer",
            "Conformance Layer",
            "Evidence Layer",
        ]
        for layer in owned_layers:
            self.assertIn(layer, architecture)

        for workstream in [
            "Adapter SDK",
            "Contracts",
            "Trace Protocol",
            "Evaluation",
            "Conformance",
            "Evidence",
        ]:
            self.assertIn(f"| {workstream} |", roadmap)

        self.assertIn("does not own or reimplement upstream recommendation methods", architecture)
        self.assertIn("## 3. Options Considered", architecture)
        self.assertIn("### 4.1 Current State: 1.1.1 Baseline", architecture)
        self.assertIn("### 4.2 Interim State: 1.2 to 1.5 Coexistence", architecture)
        self.assertIn("### 4.3 Target State: 2.0", architecture)
        self.assertIn("local-first modular monolith", architecture)
        self.assertIn("## 3. Migration-Wave Controls", roadmap)
        self.assertIn("## 2.0.0: Stable Conformance and Observability Platform", roadmap)

        adr_index = (ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
        self.assertIn("0001-product-boundary.md", adr_index)
        self.assertIn("0002-local-first-modular-platform.md", adr_index)
        self.assertIn("0003-canonical-identity-versioning-hashing.md", adr_index)
        self.assertIn("0004-module-boundaries-and-cli-identity.md", adr_index)
        self.assertIn("0005-contract-registry-and-dataset-identity.md", adr_index)
        self.assertIn("0006-sid-space-and-prepared-dataset-boundary.md", adr_index)

    def test_release_metadata_and_architecture_inventory_verify(self) -> None:
        metadata = verify_release_metadata()
        inventory = verify_inventory()

        self.assertEqual(metadata["status"], "pass")
        self.assertEqual(metadata["package_version"], "1.3.0.dev0")
        self.assertEqual(inventory["canonical_contract_count"], 11)
        self.assertEqual(inventory["status"], "pass")

    def test_public_package_content_scan_is_clean(self) -> None:
        expanded = expand_public_manifest_paths(
            ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
            tracked_files(),
        )

        self.assertEqual(check_forbidden_public_content(expanded), [])

    def test_public_package_content_scan_catches_private_tokens(self) -> None:
        private_token = "/" + "Users" + "/"
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            leak_path = Path(tmp) / "private_path_leak_example.md"
            leak_path.write_text(f"local path: {private_token}example/private\n", encoding="utf-8")
            rel_path = leak_path.relative_to(ROOT).as_posix()
            findings = check_forbidden_public_content([rel_path])

        self.assertEqual(
            findings,
            [f"{rel_path}:1: forbidden public-package token {private_token!r}"],
        )

    def test_release_candidate_archive_contains_only_public_package_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "sidscope-v1-release-candidate.zip"
            result = build_archive(
                manifest_path=ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
                output_path=archive_path,
            )

            self.assertEqual(result["status"], "pass")
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())

        self.assertIn("README.md", names)
        self.assertIn("setup.py", names)
        self.assertIn("tools/build_sidscope_release_candidate_archive.py", names)
        self.assertIn("tools/run_sidscope_usage_demo.py", names)
        self.assertIn("tools/run_sidscope_g8_fresh_env_smoke.py", names)
        self.assertIn("tools/run_sidscope_public_url_smoke.py", names)
        self.assertNotIn("experiments/v1_evidence_chain/autodl/payloads", names)

    def test_release_candidate_archive_has_deterministic_zip_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_path = Path(tmp) / "first.zip"
            second_path = Path(tmp) / "second.zip"
            first = build_archive(
                manifest_path=ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
                output_path=first_path,
            )
            second = build_archive(
                manifest_path=ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
                output_path=second_path,
            )
            with zipfile.ZipFile(first_path) as archive:
                timestamps = {info.date_time for info in archive.infolist()}

        self.assertEqual(first["archive_sha256"], second["archive_sha256"])
        self.assertEqual(timestamps, {FIXED_ZIP_TIMESTAMP})

    def test_public_url_smoke_command_contract(self) -> None:
        target = Path("/tmp/sidscope-checkout")
        clone = clone_command("https://example.invalid/repo.git", "main", target)
        commands = smoke_commands(Path("/tmp/venv/bin/python"), Path("/tmp/sidscope.zip"))

        self.assertEqual(
            clone,
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                "main",
                "https://example.invalid/repo.git",
                str(target),
            ],
        )
        self.assertEqual(commands[0][-2:], ["--upgrade", "pip>=21.3"])
        self.assertEqual(commands[1][-2:], ["-e", "."])
        self.assertNotIn("--no-deps", commands[1])
        self.assertIn("tools/verify_sidscope_resource_package.py", commands[2])
        self.assertIn("tools/run_sidscope_g8_fresh_env_smoke.py", commands[5])

    def test_local_g8_upgrades_pip_before_editable_install(self) -> None:
        py = Path("/tmp/venv/bin/python")
        commands = fresh_env_install_commands(py)

        self.assertEqual(commands[0][-2:], ["--upgrade", "pip>=21.3"])
        self.assertEqual(commands[1][-2:], ["-e", "."])
        self.assertNotIn("--no-deps", commands[1])

    def test_scanned_package_files_excludes_runtime_cache(self) -> None:
        scanned = scanned_package_files()

        self.assertNotIn("__pycache__", "\n".join(scanned))
        self.assertFalse(any(path.endswith(".pyc") for path in scanned))

    def test_release_candidate_archive_smoke_runs_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "sidscope-v1-release-candidate.zip"
            build_archive(
                manifest_path=ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv",
                output_path=archive_path,
            )
            result = smoke_archive(archive_path)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["commands"]), 2)

    def test_realistic_tutorial_validator_runs_reviewer_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_tutorial(Path(tmp) / "tutorial")

        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["gpu_required"])
        self.assertGreaterEqual(result["validation"]["input_rows"]["sid_assignments"], 10)
        self.assertGreater(result["validation"]["summary_metrics"]["unique_sid"], 0)

    def test_claim_ledger_verifier_checks_supported_and_avoid_rows(self) -> None:
        result = verify_ledger(
            ROOT / "experiments" / "v1_evidence_chain" / "CLAIM_LEDGER.md",
            package_mode=True,
        )

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["package_mode"])
        self.assertGreaterEqual(result["claim_rows"], 10)
        self.assertGreaterEqual(result["avoid_rows"], 1)
        self.assertTrue(
            "experiments/v1_evidence_chain/runs/R509_sidscope_realistic_tutorial.json"
            in result["resolved_evidence_paths"]
            or "experiments/v1_evidence_chain/runs/R509_sidscope_realistic_tutorial.json"
            in result["package_omitted_evidence_paths"]
        )

    def test_claim_ledger_package_mode_tracks_non_shipped_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "CLAIM_LEDGER.md"
            ledger_path.write_text(
                "\n".join(
                    [
                        "| ID | Claim | Status | Paper placement | Evidence | Command | Current numeric support | Limitation | V0 overlap risk |",
                        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                        "| C1 | Public doc exists. | supported | main | `docs/SIDSCOPE_RESOURCE_PACKAGE.md`; `runs/R999_missing_full_repo_record.json` | n/a | doc is shipped | full record omitted from package | low |",
                        "| C9 | Do not claim generator mechanism. | avoid | future_work | No supporting artifact. | n/a | none | forbidden claim | low |",
                        "| C10 | Package is verifiable. | supported | main | `runs/R506_sidscope_release_archive_smoke.json`; `runs/R509_sidscope_realistic_tutorial.json` | n/a | records are full-repo evidence | package mode may omit full records | low |",
                        "",
                        "G7-full registry: `docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv`",
                        "",
                        "## Paper-Facing Claims Currently Blocked",
                        "- Downstream recommendation improvement",
                        "- Trained generator failure prediction",
                        "- Causal proof",
                        "- R138 as faithful GRID named coverage",
                        "- Final SIGIR-vs-TOIS venue decision before the CIKM V0 result",
                    ]
                ),
                encoding="utf-8",
            )

            result = verify_ledger(ledger_path, package_mode=True)

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["package_mode"])
        self.assertIn(
            "experiments/v1_evidence_chain/runs/R999_missing_full_repo_record.json",
            result["package_omitted_evidence_paths"],
        )


if __name__ == "__main__":
    unittest.main()
