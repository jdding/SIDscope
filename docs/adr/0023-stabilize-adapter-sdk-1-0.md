# ADR-0023: Stabilize the Adapter SDK at 1.0

Status: accepted local implementation scope, 2026-09-09. Product remains
`1.7.0.dev0`; no tag, push or public release is authorized.

## Decision

Promote the Adapter SDK version from pre-stable 0.2 to `1.0.0`. Keep plugin API
`1.0`, `sidscope.adapter_capabilities.v1`, `AdapterCapabilities`,
`AdapterHarness` and typed failures unchanged. Current descriptors declare
`>=1.0.0,<2.0.0`. The validator continues to honor declared intervals exactly.

The runtime explicitly supports API levels `0.2.0` and `1.0.0`; a descriptor
passes only when its declared half-open interval contains at least one supported
level. This preserves honest 0.2 replay without ignoring an upper bound.

The historical implementation filename `sdk/alpha.py` is retained to avoid an
unnecessary import-path break, but the public import remains
`sidinspector.sdk`. Historical SDK 0.1 descriptors remain readable for replay;
they are not silently upgraded. Pre-stable 0.2 descriptors are regenerated only
when their publisher adopts the stable compatibility claim.

## Alternatives and consequences

Leaving the SDK at 0.2 would contradict the planned stable 2.0 extension
contract. Excluding the SDK from 2.0 was rejected by the product owner. Ignoring
old upper bounds was rejected because it would make compatibility declarations
meaningless. No new service, dependency, training API or payload is introduced.

Positive and typed-negative capability tests, external package installation,
zero-core-edit plugin preflight, installed consumers, compatibility replay and
release metadata must pass. Rollback pins the previous package and its original
descriptor bytes; evidence, tags and TOIS materials are never rewritten.
