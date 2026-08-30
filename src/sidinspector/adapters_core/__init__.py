"""Trusted adapter-plugin discovery and preflight facade."""

from .plugins import (
    AdapterPluginError,
    DiscoveredPlugin,
    PluginPreflight,
    discover_adapter_plugins,
    load_adapter_plugin,
    preflight_adapter_plugin,
)
from .fixtures import FixtureHarnessError, FixtureResult, run_fixture_manifest

__all__ = [
    "AdapterPluginError",
    "DiscoveredPlugin",
    "PluginPreflight",
    "discover_adapter_plugins",
    "load_adapter_plugin",
    "preflight_adapter_plugin",
    "FixtureHarnessError",
    "FixtureResult",
    "run_fixture_manifest",
]
