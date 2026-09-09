# SIDScope Adapter SDK Alpha (historical)

Status: superseded by Adapter SDK `1.0.0`; retained as pre-2.0 migration history

The Adapter SDK is the method-facing boundary for declaring capabilities and
returning registered artifacts. It does not train models, import optional
upstream runtimes during core startup, or grant conformance status.

SDK `0.2.0` introduced the versioned `sidscope.adapter_capabilities.v1` descriptor.
It declares an SDK compatibility interval, adapter and producer identities,
one native method family and payload schema, canonical contract types,
supported and unavailable telemetry, external-runtime boundary, and explicit
runtime requirements. Unknown families/contracts, overlapping telemetry,
payload-family mismatches, or incompatible SDK ranges fail with typed errors.

The 1.3 plugin API uses Python package entry points under
`sidscope.adapters`. Listing is lazy and reads metadata only; explicit
preflight loads one selected plugin, validates its API version and protocol,
then validates both its capability descriptor and native payload. Plugin load
or compatibility failure remains outside core import and bundle verification.

```bash
sidscope adapter preflight \
  --descriptor examples/native_trace_payload_fixtures/adapter_capabilities.v1.json
sidscope plugin list
sidscope plugin preflight --name reference-parallel
```

The external reference package in `examples/reference_adapter_plugin/` proves
installation and discovery without placing adapter code in the trusted core.
It is a contract example, not a named-method adapter or scientific result.

For current publisher instructions see `ADAPTER_SDK.md`. Legacy
`sidscope.adapter_capabilities.alpha.v1` / SDK `0.1.0` descriptors
remain accepted during the 1.x coexistence period. They do not declare a
registered native payload schema and therefore cannot serve as a 1.3 plugin
capability descriptor. Rollback disables a plugin package or entry point;
canonical contracts, legacy adapters, and already produced files remain valid.
