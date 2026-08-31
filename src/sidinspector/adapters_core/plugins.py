"""Fail-closed ``importlib.metadata`` adapter plugin lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any, Mapping

from sidinspector.sdk import AdapterCapabilities, AdapterSDKError, validate_adapter_capabilities
from sidinspector.sdk import PLUGIN_API_VERSION, PLUGIN_ENTRY_POINT_GROUP
from sidinspector.trace import NativePayload, NativePayloadValidationError, validate_native_payload


class AdapterPluginError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class DiscoveredPlugin:
    name: str
    value: str
    distribution: str
    entry_point: Any


@dataclass(frozen=True)
class PluginPreflight:
    plugin: DiscoveredPlugin
    capabilities: AdapterCapabilities
    payload: NativePayload


def _fail(code: str, detail: str) -> None:
    raise AdapterPluginError(code, detail)


def _entry_points() -> list[Any]:
    discovered = metadata.entry_points()
    if hasattr(discovered, "select"):
        return list(discovered.select(group=PLUGIN_ENTRY_POINT_GROUP))
    return list(discovered.get(PLUGIN_ENTRY_POINT_GROUP, ()))


def discover_adapter_plugins() -> tuple[DiscoveredPlugin, ...]:
    records: list[DiscoveredPlugin] = []
    for entry_point in _entry_points():
        distribution = getattr(getattr(entry_point, "dist", None), "name", None) or "unknown"
        records.append(
            DiscoveredPlugin(entry_point.name, entry_point.value, distribution, entry_point)
        )
    records.sort(key=lambda item: (item.name, item.distribution, item.value))
    names = [item.name for item in records]
    if len(names) != len(set(names)):
        _fail("duplicate_plugin_name", str(names))
    return tuple(records)


def load_adapter_plugin(name: str) -> tuple[DiscoveredPlugin, Any]:
    matches = [item for item in discover_adapter_plugins() if item.name == name]
    if not matches:
        _fail("plugin_not_found", name)
    record = matches[0]
    try:
        loaded = record.entry_point.load()
        plugin = loaded() if isinstance(loaded, type) else loaded
    except Exception as exc:  # plugin failures are data, not core import failures
        _fail("plugin_load_failed", f"{name}: {type(exc).__name__}: {exc}")
    if getattr(plugin, "plugin_api_version", None) != PLUGIN_API_VERSION:
        _fail("plugin_api_incompatible", str(getattr(plugin, "plugin_api_version", None)))
    for method in ("get_capabilities", "get_payload_fixture"):
        if not callable(getattr(plugin, method, None)):
            _fail("plugin_protocol_mismatch", f"{name}.{method}")
    return record, plugin


def preflight_adapter_plugin(name: str) -> PluginPreflight:
    record, plugin = load_adapter_plugin(name)
    try:
        capabilities_value = plugin.get_capabilities()
        payload_value = plugin.get_payload_fixture()
    except Exception as exc:
        _fail("plugin_execution_failed", f"{name}: {type(exc).__name__}: {exc}")
    if not isinstance(capabilities_value, Mapping) or not isinstance(payload_value, Mapping):
        _fail("plugin_protocol_mismatch", f"{name} returned a non-object")
    try:
        capabilities = validate_adapter_capabilities(capabilities_value)
    except AdapterSDKError as exc:
        _fail("plugin_capabilities_invalid", f"{exc.code}: {exc.detail}")
    try:
        payload = validate_native_payload(payload_value)
    except NativePayloadValidationError as exc:
        _fail("plugin_payload_invalid", f"{exc.code}: {exc.detail}")
    if capabilities.method_family != payload.method_family:
        _fail("plugin_payload_family_mismatch", name)
    if capabilities.payload_schema != payload.schema:
        _fail("plugin_payload_schema_mismatch", name)
    return PluginPreflight(record, capabilities, payload)
