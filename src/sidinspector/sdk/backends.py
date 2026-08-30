"""Dependency-free availability probes for optional adapter backends."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True)
class OptionalBackendProbe:
    backend_id: str
    module_name: str
    available: bool
    import_attempted: bool = False


def probe_optional_backend(backend_id: str, module_name: str) -> OptionalBackendProbe:
    """Check discoverability without importing the optional backend."""

    return OptionalBackendProbe(
        backend_id=backend_id,
        module_name=module_name,
        available=find_spec(module_name) is not None,
        import_attempted=False,
    )
