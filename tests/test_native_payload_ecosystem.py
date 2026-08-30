from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from sidinspector.adapters_core import (
    AdapterPluginError,
    discover_adapter_plugins,
    preflight_adapter_plugin,
    run_fixture_manifest,
)
from sidinspector.cli import main as cli_main
from sidinspector.contracts import with_content_sha256
from sidinspector.conformance_core import ProfileCompositionError, compose_profiles
from sidinspector.sdk import probe_optional_backend
from sidinspector.trace import (
    NativePayloadValidationError,
    load_native_payload,
    load_native_payload_registry,
    validate_native_payload,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/native_trace_payload_fixtures"


class _Dist:
    name = "fake-adapter-dist"


class _EntryPoint:
    def __init__(self, name: str, loaded: object) -> None:
        self.name = name
        self.value = "fake.module:Plugin"
        self.dist = _Dist()
        self.loaded = loaded
        self.load_count = 0

    def load(self) -> object:
        self.load_count += 1
        return self.loaded


class _GoodPlugin:
    plugin_api_version = "1.0"

    def get_capabilities(self):
        return json.loads((FIXTURE / "adapter_capabilities.v1.json").read_text())

    def get_payload_fixture(self):
        return json.loads((FIXTURE / "parallel_graph_token_set.json").read_text())


class _BadVersionPlugin(_GoodPlugin):
    plugin_api_version = "9.0"


class NativePayloadEcosystemTest(unittest.TestCase):
    def test_all_native_payload_families_and_fixture_harness(self) -> None:
        registry = load_native_payload_registry()
        self.assertEqual(len(registry), 5)
        self.assertEqual(
            {item.method_family for item in registry},
            {
                "autoregressive_prefix",
                "parallel_graph_token_set",
                "masked_diffusion",
                "latent_retry",
                "decoder_overlay",
            },
        )
        for descriptor in registry:
            payload = load_native_payload(ROOT / descriptor.canonical_fixture)
            self.assertEqual(payload.schema, descriptor.schema_id)
        results = run_fixture_manifest(FIXTURE / "fixture_manifest.json")
        self.assertEqual(len(results), 12)
        self.assertEqual(sum(item.observed_status == "fail" for item in results), 7)

    def test_profile_composition_is_deterministic_and_fail_closed(self) -> None:
        profile = compose_profiles(["family.masked_diffusion.v1"])
        self.assertEqual(profile.profile_ids, ("common.generator.v1", "family.masked_diffusion.v1"))
        self.assertEqual(profile.gates[0].gate_id, "binding_integrity")
        self.assertEqual(profile.gates[-1].gate_id, "unmask_transition")
        with self.assertRaises(ProfileCompositionError) as captured:
            compose_profiles(["missing.profile"])
        self.assertEqual(captured.exception.code, "unknown_profile")
        with self.assertRaises(ProfileCompositionError) as captured:
            compose_profiles(
                ["family.autoregressive_prefix.v1", "family.masked_diffusion.v1"]
            )
        self.assertEqual(captured.exception.code, "conflicting_method_families")

    def test_decoder_overlay_cannot_insert_provider_only_items(self) -> None:
        value = json.loads((FIXTURE / "decoder_overlay.json").read_text())
        changed = copy.deepcopy(value)
        changed["episodes"][0]["fused_ranked_items"][1]["normalized_item_id"] = 99
        with self.assertRaises(NativePayloadValidationError) as captured:
            validate_native_payload(with_content_sha256(changed))
        self.assertEqual(captured.exception.code, "provider_only_item_insertion")

    def test_discovery_does_not_load_and_preflight_loads_one_plugin(self) -> None:
        entry = _EntryPoint("good", _GoodPlugin)
        with mock.patch("sidinspector.adapters_core.plugins._entry_points", return_value=[entry]):
            records = discover_adapter_plugins()
            self.assertEqual(records[0].name, "good")
            self.assertEqual(entry.load_count, 0)
            preflight = preflight_adapter_plugin("good")
        self.assertEqual(entry.load_count, 1)
        self.assertEqual(preflight.payload.method_family, "parallel_graph_token_set")

    def test_incompatible_plugin_is_typed_not_import_time_failure(self) -> None:
        entry = _EntryPoint("bad", _BadVersionPlugin)
        with mock.patch("sidinspector.adapters_core.plugins._entry_points", return_value=[entry]):
            with self.assertRaises(AdapterPluginError) as captured:
                preflight_adapter_plugin("bad")
        self.assertEqual(captured.exception.code, "plugin_api_incompatible")

    def test_cli_payload_and_profile_paths(self) -> None:
        cases = (
            ["trace", "payload", "list"],
            ["trace", "payload", "validate", "--input", str(FIXTURE / "masked_diffusion.json")],
            ["profile", "list"],
            ["profile", "compose", "--profile", "family.decoder_overlay.v1"],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = cli_main(argv)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(stdout.getvalue())["status"], "pass")

    def test_optional_recbole_probe_never_imports_backend(self) -> None:
        probe = probe_optional_backend("recbole", "definitely_absent_recbole_fixture")
        self.assertFalse(probe.available)
        self.assertFalse(probe.import_attempted)


if __name__ == "__main__":
    unittest.main()
