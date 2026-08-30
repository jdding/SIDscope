"""Public plugin protocol for SIDScope Adapter SDK 0.2."""

from __future__ import annotations

from typing import Any, Mapping, Protocol


PLUGIN_API_VERSION = "1.0"
PLUGIN_ENTRY_POINT_GROUP = "sidscope.adapters"


class AdapterPlugin(Protocol):
    """Minimal adapter plugin boundary; upstream runtimes remain plugin-owned."""

    plugin_api_version: str

    def get_capabilities(self) -> Mapping[str, Any]:
        """Return a canonical ``sidscope.adapter_capabilities.v1`` document."""

    def get_payload_fixture(self) -> Mapping[str, Any]:
        """Return one method-native positive payload fixture."""
