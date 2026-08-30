"""Dependency-light SIDScope Adapter SDK alpha."""

from .alpha import (
    ADAPTER_CAPABILITIES_SCHEMA,
    ADAPTER_SDK_VERSION,
    AdapterCapabilities,
    AdapterHarness,
    AdapterSDKError,
    load_adapter_capabilities,
    validate_adapter_capabilities,
)

__all__ = [
    "ADAPTER_CAPABILITIES_SCHEMA",
    "ADAPTER_SDK_VERSION",
    "AdapterCapabilities",
    "AdapterHarness",
    "AdapterSDKError",
    "load_adapter_capabilities",
    "validate_adapter_capabilities",
]
