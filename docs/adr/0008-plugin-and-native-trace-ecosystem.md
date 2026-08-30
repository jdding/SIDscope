# ADR-0008: Add lazy adapter plugins and registered native trace families

Status: Accepted

Date: 2026-08-30

## 1. Context

SIDScope 1.2 completed the common contract envelope but intentionally left
plugin discovery and native payload definitions open. Continuing to add
method-specific imports to core would couple verification to upstream runtime
stacks. Conversely, flattening AR, graph, masked, retry, and overlay execution
into one event model would change their semantics.

## 2. Decision Drivers

- Add integrations without editing or importing the trusted core at startup.
- Preserve native execution semantics and reject synthetic telemetry.
- Keep plugin failure typed and local to explicit preflight.
- Verify already produced artifacts when their plugin is absent.
- Retain 1.1 route authorities and SDK 0.1 descriptors during migration.
- Avoid introducing 1.4 storage concerns into the plugin cut.

## 3. Options Considered

| Option | Benefit | Cost | Reversibility |
| --- | --- | --- | --- |
| Built-in adapter imports only | Simple packaging. | Core dependency growth and optional-runtime import risk. | Medium. |
| One flattened trace event schema | One apparent API. | Falsifies native semantics and unsupported ancestry. | Low. |
| Lazy entry points plus family payload registry | External integration with semantic contracts and isolated failures. | Requires capability, payload, fixture, and profile versioning. | High. |
| Hosted adapter registry | Central discovery. | Adds service/availability scope before local contracts stabilize. | Medium. |

## 4. Decision

Use `importlib.metadata` entry points under `sidscope.adapters`. Discovery reads
metadata without loading code. Explicit preflight loads one plugin conforming
to plugin API `1.0`, Adapter SDK `0.2.0`, and
`sidscope.adapter_capabilities.v1`.

Register five independent payload families: autoregressive prefix, parallel
graph/token-set, masked diffusion, latent retry, and decoder overlay. Each has
its own semantic validator and JSON Schema resource. A hash-bound registry maps
method family to payload schema and fixtures. Versioned profiles compose common
gates with one native-family gate. `adapters_core` owns discovery and fixture
harnessing; SDK owns declarations; Trace owns payload semantics.

## 5. Consequences

External adapters can install without core edits, and core verification remains
usable when no plugin is present. Incompatible or broken plugins become typed
preflight failures rather than import-time product failures. The additional
registries and schema axes require explicit compatibility documentation.

Passing plugin preflight proves interface conformance only. It does not execute
training, grant a license, promote a named adapter, or admit evidence.

## 6. Migration and Validation

Legacy SDK 0.1 descriptors remain accepted. Built-in route adapters and their
verifiers remain unchanged. The reference plugin is packaged outside core and
installed in a temporary environment after a no-plugin core check. Validation
includes five positive payload round trips, seven typed failures, deterministic
profile composition, plugin API incompatibility, architecture dependency tests,
full CPU tests, resource/package verification, archive smoke, and G8.

## 7. Rollback

Uninstall or disable the plugin entry point and route the integration through
its existing built-in or legacy verifier. The payload and profile registries
are additive; produced files and historical evidence are not rewritten. If the
SDK 0.2 surface is withdrawn, SDK 0.1 descriptor validation remains available.
