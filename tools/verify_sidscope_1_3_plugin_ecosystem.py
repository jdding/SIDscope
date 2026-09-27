#!/usr/bin/env python3
"""Verify the SIDScope 1.3 plugin, payload-family, and profile ecosystem."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.adapters_core import run_fixture_manifest
from sidinspector.conformance_core import compose_profiles, load_profile_registry
from sidinspector.sdk import ADAPTER_SDK_VERSION, load_adapter_capabilities, probe_optional_backend
from sidinspector.trace import load_native_payload, load_native_payload_registry


FIXTURES = ROOT / "examples" / "native_trace_payload_fixtures"
REFERENCE_PLUGIN = ROOT / "examples" / "reference_adapter_plugin"


def _run_json(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"command failed ({completed.returncode}): {command}; "
            f"stdout={completed.stdout[-2000:]}; stderr={completed.stderr[-2000:]}"
        )
    value = json.loads(completed.stdout)
    if value.get("status") != "pass":
        raise ValueError(f"command did not pass: {command}: {value}")
    return value


def _run_checked(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        command,
        check=False,
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"command failed ({completed.returncode}): {command}; "
            f"stdout={completed.stdout[-4000:]}; stderr={completed.stderr[-4000:]}"
        )


def _verify_external_install() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="sidscope-plugin-proof-") as temporary:
        temporary_path = Path(temporary)
        environment = temporary_path / "venv"
        core_source = temporary_path / "core-source"
        plugin_source = temporary_path / "reference-plugin-source"
        shutil.copytree(
            ROOT,
            core_source,
            # The plugin proof builds from the source package only; the ignored
            # private evidence area is neither source nor distributable.
            ignore=shutil.ignore_patterns(
                ".git", ".pytest_cache", "*.egg-info", "__pycache__", ".local_artifacts"
            ),
        )
        shutil.copytree(REFERENCE_PLUGIN, plugin_source, ignore=shutil.ignore_patterns("*.egg-info", "__pycache__"))
        # The proof remains network-free while reusing the host build backend.
        # Plugin absence is asserted before the external reference package is installed.
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
        python = environment / "bin" / "python"
        def cli(*arguments: str) -> list[str]:
            return [
                str(python),
                "-c",
                "import sys; from sidinspector.cli import main; raise SystemExit(main(sys.argv[1:]))",
                *arguments,
            ]
        install = [
            str(python), "-m", "pip", "install", "--disable-pip-version-check",
            "--no-cache-dir", "--no-deps", "--no-build-isolation",
        ]
        _run_checked([*install, str(core_source)], cwd=core_source)
        absent = _run_json(cli("plugin", "list"))
        if absent.get("plugins"):
            raise ValueError(f"isolated core unexpectedly discovered plugins: {absent['plugins']}")
        core_payload = _run_json(
            cli(
                "trace", "payload", "validate", "--input",
                str(FIXTURES / "parallel_graph_token_set.json"),
            )
        )
        _run_checked([*install, str(plugin_source)], cwd=ROOT)
        listing = _run_json(cli("plugin", "list"))
        names = [row["name"] for row in listing["plugins"]]
        if names != ["reference-parallel"]:
            raise ValueError(f"reference plugin discovery mismatch: {names}")
        preflight = _run_json(
            cli("plugin", "preflight", "--name", "reference-parallel")
        )
        return {
            "core_without_plugin": absent,
            "core_payload_without_plugin": core_payload,
            "plugin_listing": listing,
            "plugin_preflight": preflight,
        }


def verify_ecosystem() -> dict[str, object]:
    descriptors = load_native_payload_registry()
    for descriptor in descriptors:
        payload = load_native_payload(ROOT / descriptor.canonical_fixture)
        if payload.schema != descriptor.schema_id:
            raise ValueError(f"payload registry binding mismatch: {descriptor.method_family}")

    fixture_results = run_fixture_manifest(FIXTURES / "fixture_manifest.json")
    if len(fixture_results) != 12:
        raise ValueError(f"fixture count mismatch: {len(fixture_results)}")
    failures = [row for row in fixture_results if row.observed_status == "fail"]
    if len(failures) != 7:
        raise ValueError(f"negative fixture count mismatch: {len(failures)}")

    profiles = load_profile_registry()
    family_profiles = [row for row in profiles if row.method_family is not None]
    for profile in family_profiles:
        composed = compose_profiles([profile.profile_id])
        if "common.generator.v1" not in composed.profile_ids:
            raise ValueError(f"common profile missing: {profile.profile_id}")

    legacy = load_adapter_capabilities(
        ROOT / "examples" / "canonical_pipeline_fixture" / "adapter_capabilities.json"
    )
    current = load_adapter_capabilities(FIXTURES / "adapter_capabilities.v1.json")
    backend = probe_optional_backend("recbole", "recbole")
    if backend.import_attempted:
        raise ValueError("optional backend probe imported RecBole")
    isolated = _verify_external_install()

    return {
        "schema": "sidscope.release_1_3_ecosystem_verification.v1",
        "status": "pass",
        "adapter_sdk_version": ADAPTER_SDK_VERSION,
        "legacy_sdk_descriptor_accepted": legacy.schema,
        "current_sdk_descriptor": current.schema,
        "entry_point_group": isolated["plugin_listing"]["entry_point_group"],
        "external_reference_plugin": isolated["plugin_preflight"]["adapter_id"],
        "native_payload_family_count": len(descriptors),
        "conformance_profile_count": len(profiles),
        "positive_fixture_count": len(fixture_results) - len(failures),
        "typed_negative_fixture_count": len(failures),
        "core_plugin_absence_verified": isolated["core_without_plugin"]["plugins"] == [],
        "core_payload_verification_without_plugin": isolated["core_payload_without_plugin"]["status"],
        "recbole_boundary": {
            "available": backend.available,
            "import_attempted": backend.import_attempted,
        },
    }


def main() -> None:
    print(json.dumps(verify_ecosystem(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
