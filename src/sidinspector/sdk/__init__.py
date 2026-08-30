"""Dependency-light SIDScope Adapter SDK alpha."""

from .alpha import (
    ADAPTER_CAPABILITIES_SCHEMA,
    ADAPTER_SDK_VERSION,
    LEGACY_ADAPTER_CAPABILITIES_SCHEMA,
    AdapterCapabilities,
    AdapterHarness,
    AdapterSDKError,
    load_adapter_capabilities,
    validate_adapter_capabilities,
)
from .backends import OptionalBackendProbe, probe_optional_backend
from .plugin_api import AdapterPlugin, PLUGIN_API_VERSION, PLUGIN_ENTRY_POINT_GROUP

__all__ = [
    "ADAPTER_CAPABILITIES_SCHEMA",
    "ADAPTER_SDK_VERSION",
    "LEGACY_ADAPTER_CAPABILITIES_SCHEMA",
    "AdapterCapabilities",
    "AdapterHarness",
    "AdapterSDKError",
    "load_adapter_capabilities",
    "validate_adapter_capabilities",
    "OptionalBackendProbe",
    "probe_optional_backend",
    "AdapterPlugin",
    "PLUGIN_API_VERSION",
    "PLUGIN_ENTRY_POINT_GROUP",
]
