# SIDScope Adapter SDK Alpha

Status: `0.1.0-alpha` in `1.2.0.dev0`

The alpha SDK is the adapter-facing boundary for declaring capabilities and
returning registered artifacts. It does not discover plugins, import optional
upstream runtimes, train models, or grant conformance status.

An adapter capability descriptor declares adapter identity and native method
family, canonical contract types, supported and explicitly unavailable
telemetry, the external runtime boundary and native payload schema, and the SDK
compatibility range.

Supported and unavailable telemetry are disjoint. Unknown method families,
undeclared contracts, missing runtime boundaries, or incompatible SDK versions
fail closed. `AdapterHarness` validates every produced artifact through the
bundled contract registry; a producer cannot bypass the canonical validator.

```bash
sidscope adapter preflight \
  --descriptor examples/canonical_pipeline_fixture/adapter_capabilities.json
```

The canonical fixture uses RPG's synthetic non-AR bridge solely to prove the
SDK and common pipeline. Its `fixture_pass` result is scoped to contract
behavior and does not alter any adapter admission decision. Plugin entry-point
discovery and external reference plugins begin in 1.3.
