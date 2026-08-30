# ADR-0002: Use a Local-First Modular Platform with Adapter Plugins

## Status

Accepted on 2026-08-30.

## Context

After accepting the product boundary in ADR-0001, SIDScope needs a runtime and
repository topology. The current project is a Python package and deterministic
file-based resource verifier maintained by a small group. It has no measured
need for independently deployed services, online writes, multi-tenancy or a
continuous availability target.

The architecture must isolate optional upstream dependencies, support external
adapters, preserve offline verification and provide an evidence registry without
making a mutable database the source of truth.

## Decision Drivers

| Priority | Driver | Measurement |
| ---: | --- | --- |
| 1 | Semantic and release safety | Existing adapter fixtures and archives retain exact behavior. |
| 2 | Operational simplicity | No always-on service or new on-call surface through 2.0. |
| 3 | Plugin isolation | Core verification succeeds with the producing plugin absent. |
| 4 | Rebuildability | Registry projections reproduce from immutable bundles. |
| 5 | Compatibility | `sidinspector` remains usable while `sidscope` becomes the CLI facade. |

## Options Considered

| Option | Advantages | Disadvantages | Reversibility |
| --- | --- | --- | --- |
| Keep adding scripts without shared modules | Lowest immediate change. | Duplicated contracts, difficult dependency direction and manual status drift. | Easy short term, increasingly costly later. |
| Modular monolith with external plugin entry points | Clear boundaries in one install; simple transactions; easy CPU testing; later extraction remains possible. | Requires import discipline and staged compatibility wrappers. | High when module contracts stay clean. |
| Microservices and hosted registry | Independent scaling and central collaboration. | Unjustified auth, tenancy, network, deployment and on-call complexity; larger failure surface. | Medium to hard after public API adoption. |

## Decision

Through 2.0, SIDScope will be one local-first Python distribution with six
internal modules and a thin CLI. Optional adapters use
`importlib.metadata.entry_points` under `sidscope.adapters`. Upstream runtimes
may produce contracts through Python APIs or explicit files, but core bundle
verification never imports the plugin.

Evidence uses SHA-256-addressed immutable objects. Standard-library SQLite is a
local projection for lookup and comparison; it is rebuildable from bundle
manifests. Public registry views are deterministic static exports. No hosted
control plane, queue, service mesh or distributed database is introduced.

## Architecture Impact

- Canonical artifacts use versioned JSON Schema and deterministic JSON hashing.
- Dependencies flow inward from CLI/adapters to contracts and verification
  interfaces; architecture tests reject cycles.
- Route-specific tools coexist until the shared path passes exact regression.
- Registry corrections create superseding bundles rather than row mutation.
- Architecture, schema, profile and release surfaces receive explicit ownership.

## Failure Modes and Controls

- A plugin importing GPU dependencies into core fails clean-import and G8.
- A shared verifier changing historical meaning fails route parity and retains
  the legacy profile.
- SQLite loss is recovered by rebuilding from immutable objects.
- Public-content leakage blocks bundle admission and export.
- A demand for hosted collaboration requires a new ADR after 2.0 with measured
  users, trust, availability, cost and ownership requirements.

## Rollout, Validation and Rollback

The modular core is introduced entity by entity and route by route. Legacy and
shared commands coexist until parity. Plugin discovery is added only after core
contract boundaries are stable. Registry adoption follows deterministic bundle
construction.

Rollback disables the new facade, plugin or derived index and returns to the
previous versioned path. Immutable evidence is never rolled back by mutation.

## Consequences

Positive:

- simplest topology satisfies current requirements;
- one release and CPU test matrix remain authoritative;
- adapter ecosystems can grow without converting every integration into core;
- public evidence remains usable offline.

Negative and tradeoffs:

- no shared online registry or collaborative write API through 2.0;
- a single package release coordinates core module changes;
- import-boundary and compatibility tests become mandatory engineering work;
- very large future workloads may require a later service extraction.
