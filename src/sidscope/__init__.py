"""Stable, curated SIDScope 2.0-candidate Python facade.

The historical :mod:`sidinspector` namespace remains available for replay and
compatibility. New integrations should prefer this deliberately small facade
instead of depending on implementation modules directly.
"""

from sidinspector.adapters_core import (
    AdapterPluginError,
    discover_adapter_plugins,
    preflight_adapter_plugin,
)
from sidinspector.contracts import (
    canonical_json_bytes,
    canonical_sha256,
    load_checkpoint_binding,
    load_dataset_identity,
    load_episode_selection,
    load_prepared_dataset,
    load_run_identity,
    load_sid_space_identity,
    load_source_identity,
    load_trace_envelope,
    verify_content_sha256,
    with_content_sha256,
)
from sidinspector.evidence import (
    EvidenceBundleValidationError,
    EvidenceRegistry,
    ObjectStore,
    compare_evidence_bundles,
    load_evidence_bundle,
    validate_evidence_bundle,
)
from sidinspector.sdk import (
    ADAPTER_SDK_VERSION,
    PLUGIN_API_VERSION,
    AdapterCapabilities,
    AdapterHarness,
    AdapterPlugin,
    AdapterSDKError,
    load_adapter_capabilities,
    validate_adapter_capabilities,
)
from sidinspector.schemas import (
    PublicSchemaDescriptor,
    PublicSchemaValidationError,
    get_public_schema_descriptor,
    load_public_schema_catalog,
    validate_public_document,
)
from sidinspector.submission import check_submission
from sidinspector.trace import (
    NativePayloadValidationError,
    load_native_payload,
    validate_native_payload,
)
from sidinspector.version import PRODUCT_VERSION as __version__

__all__ = [
    "ADAPTER_SDK_VERSION",
    "PLUGIN_API_VERSION",
    "AdapterCapabilities",
    "AdapterHarness",
    "AdapterPlugin",
    "AdapterPluginError",
    "AdapterSDKError",
    "EvidenceBundleValidationError",
    "EvidenceRegistry",
    "NativePayloadValidationError",
    "ObjectStore",
    "PublicSchemaDescriptor",
    "PublicSchemaValidationError",
    "canonical_json_bytes",
    "canonical_sha256",
    "check_submission",
    "compare_evidence_bundles",
    "discover_adapter_plugins",
    "get_public_schema_descriptor",
    "load_adapter_capabilities",
    "load_checkpoint_binding",
    "load_dataset_identity",
    "load_episode_selection",
    "load_evidence_bundle",
    "load_native_payload",
    "load_prepared_dataset",
    "load_public_schema_catalog",
    "load_run_identity",
    "load_sid_space_identity",
    "load_source_identity",
    "load_trace_envelope",
    "preflight_adapter_plugin",
    "validate_adapter_capabilities",
    "validate_evidence_bundle",
    "validate_native_payload",
    "validate_public_document",
    "verify_content_sha256",
    "with_content_sha256",
    "__version__",
]
