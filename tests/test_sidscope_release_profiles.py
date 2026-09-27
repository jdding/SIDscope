from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_sidscope_release_candidate_archive import build_archive
from tools.sidscope_release_profiles import (
    DEFAULT_PROFILE_REGISTRY,
    PROFILE_IDS,
    PROFILE_RECEIPT_PATH,
    ReleaseProfileError,
    load_release_profiles,
    resolve_release_profile,
    validate_profile_receipt,
)
from tools.smoke_sidscope_release_candidate_archive import read_archive_profile
from tools.verify_sidscope_resource_package import (
    ROOT,
    expand_public_manifest_paths,
    tracked_files,
)


MANIFEST = ROOT / "docs" / "reproducibility" / "sidscope_release_candidate_manifest.csv"


class SIDScopeReleaseProfileTest(unittest.TestCase):
    def test_registry_has_one_default_and_three_ordered_profiles(self) -> None:
        default, profiles = load_release_profiles()

        self.assertEqual(default, "runtime")
        self.assertEqual(tuple(profiles), PROFILE_IDS)

    def test_profiles_are_strict_additive_public_manifest_subsets(self) -> None:
        public_paths = expand_public_manifest_paths(MANIFEST, tracked_files())
        resolved = {
            profile_id: set(
                resolve_release_profile(profile_id, public_paths=public_paths)[1]
            )
            for profile_id in PROFILE_IDS
        }

        self.assertLess(resolved["runtime"], resolved["conformance"])
        self.assertLess(resolved["conformance"], resolved["evidence-full"])
        self.assertFalse(any(path.startswith("examples/") for path in resolved["runtime"]))
        for suffix in (".json", "-prompt.md", ".png"):
            figure = "docs/figures/sidscope-current-architecture" + suffix
            self.assertNotIn(figure, resolved["runtime"])
            self.assertIn(figure, resolved["conformance"])
            self.assertIn(figure, resolved["evidence-full"])
        self.assertEqual(
            [path for path in resolved["runtime"] if path.startswith("docs/reproducibility/")],
            ["docs/reproducibility/sidscope_release_profiles.v1.json"],
        )
        self.assertNotIn(
            "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json",
            resolved["conformance"],
        )
        self.assertIn(
            "examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json",
            resolved["evidence-full"],
        )

    def test_release_archive_is_deterministic_and_receipt_bound(self) -> None:
        # E03: independent double-build determinism must hold for every
        # additive profile, not only the default runtime one.
        for profile_id in PROFILE_IDS:
            with self.subTest(profile=profile_id):
                with tempfile.TemporaryDirectory() as tmp:
                    first_path = Path(tmp) / "first.zip"
                    second_path = Path(tmp) / "second.zip"
                    first = build_archive(manifest_path=MANIFEST, output_path=first_path, profile_id=profile_id)
                    second = build_archive(manifest_path=MANIFEST, output_path=second_path, profile_id=profile_id)
                    with zipfile.ZipFile(first_path) as archive:
                        names = sorted(archive.namelist())
                        receipt = json.loads(archive.read(PROFILE_RECEIPT_PATH))
                        hashes = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in names if name != PROFILE_RECEIPT_PATH}

                    self.assertEqual(first["profile_id"], profile_id)
                    self.assertEqual(first["archive_sha256"], second["archive_sha256"])
                    self.assertEqual(
                        validate_profile_receipt(
                            receipt,
                            content_paths=[name for name in names if name != PROFILE_RECEIPT_PATH],
                            content_hashes=hashes,
                        ),
                        profile_id,
                    )

    def test_receipt_path_tamper_fails_closed(self) -> None:
        value = {
            "schema": "sidscope.release_profile_receipt.v1",
            "profile_id": "runtime",
            "product_version": "1.7.0.dev0",
            "smoke_suite": "runtime",
            "content_file_count": 1,
            "content_paths_sha256": "0" * 64,
            "profile_registry_sha256": "1" * 64,
            "source_manifest_sha256": "2" * 64,
        }

        with self.assertRaisesRegex(ReleaseProfileError, "profile_path_binding_mismatch") as caught:
            validate_profile_receipt(value, content_paths=["README.md"])

        self.assertEqual(caught.exception.code, "profile_path_binding_mismatch")

    def test_same_paths_changed_bytes_fail_before_archive_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.zip"
            changed = Path(tmp) / "changed.zip"
            build_archive(manifest_path=MANIFEST, output_path=original)
            with zipfile.ZipFile(original) as source, zipfile.ZipFile(changed, "w") as dest:
                for entry in source.infolist():
                    data = b"modified license\n" if entry.filename == "LICENSE" else source.read(entry)
                    dest.writestr(entry, data)
            with self.assertRaisesRegex(ReleaseProfileError, "profile_content_binding_mismatch"):
                read_archive_profile(changed)

    def test_unknown_profile_fails_closed(self) -> None:
        with self.assertRaisesRegex(ReleaseProfileError, "unknown_release_profile") as caught:
            resolve_release_profile("paper-bundle", public_paths=["README.md"])

        self.assertEqual(caught.exception.code, "unknown_release_profile")

    def test_expected_profile_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "runtime.zip"
            build_archive(manifest_path=MANIFEST, output_path=archive_path)

            with self.assertRaisesRegex(ReleaseProfileError, "unexpected_release_profile") as caught:
                read_archive_profile(archive_path, expected_profile="conformance")

        self.assertEqual(caught.exception.code, "unexpected_release_profile")

    def test_registry_rejects_noncanonical_path_order(self) -> None:
        value = json.loads(DEFAULT_PROFILE_REGISTRY.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(value)
        mutated["profiles"][0]["required_paths"] = list(
            reversed(mutated["profiles"][0]["required_paths"])
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ReleaseProfileError, "noncanonical_profile_paths"):
                load_release_profiles(path)


if __name__ == "__main__":
    unittest.main()
