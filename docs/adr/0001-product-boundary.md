# ADR-0001: Own Conformance and Observability, Not Upstream Methods

## Status

Accepted on 2026-08-30.

## Context

SIDScope 1.1 began as an artifact-level diagnostic resource and expanded into
configuration-bound generator adapters, native traces, fail-closed G0--G5
verification and compact evidence packaging. Continued route-by-route growth
needs a clear product boundary before shared APIs are introduced.

The decision must preserve official method semantics, external training
runtimes, private-data boundaries, CPU-only public verification and immutable
TOIS evidence while allowing SIDScope to become a coherent system.

## Goals

- make heterogeneous generative recommenders independently auditable;
- provide stable contracts from adapter integration through evidence;
- support comparison without erasing method-family semantics;
- keep verification portable, deterministic and fail closed.

## Non-Goals

- implementing or training recommendation models;
- replacing official repositories, RecBole or production serving stacks;
- redistributing private or unlicensed third-party assets;
- rewriting frozen paper evidence.

## Decision Drivers

| Priority | Driver | Measurement |
| ---: | --- | --- |
| 1 | Evidence integrity | Every promoted status is replayable under a versioned profile. |
| 2 | Method fidelity | Native trace fixtures reject fabricated or flattened semantics. |
| 3 | Upstream isolation | Core verification imports no method runtime or GPU dependency. |
| 4 | Extensibility | A third-party adapter needs no core edits. |
| 5 | Release continuity | Supported 1.x evidence retains parity or an explicit migration record. |

## Options Considered

| Option | Advantages | Disadvantages | Reversibility |
| --- | --- | --- | --- |
| Become a Semantic-ID model/training framework | One place to run methods; familiar model-zoo story. | Duplicates upstream frameworks, expands GPU/runtime ownership, weakens evidence focus. | Hard after users depend on training APIs. |
| Own conformance and observability from Adapter SDK through Evidence | Builds on proven G0--G5 strengths; framework-neutral; compact verification. | Requires disciplined contracts and adapter boundaries. | Medium; interfaces can evolve through versioning. |
| Remain only a static evidence archive | Minimal maintenance and operational scope. | Cannot standardize new adapters, traces or independent verification. | Easy but does not meet the system goal. |

## Decision

SIDScope will own six layers: Integration, Contract, Observation, Evaluation,
Conformance and Evidence. Upstream method implementation, training, checkpoint
production and serving remain external.

RecBole may be an adapter backend, OpenTelemetry informs the trace-envelope
shape, and MLPerf informs profile/checker governance. SIDScope remains its own
framework-neutral product rather than cloning any of them.

## Consequences

Positive:

- product scope aligns with existing evidence engineering;
- official and downstream methods keep their native environments;
- CPU-only reviewers can verify bounded bundles;
- new method families extend payloads rather than redefine the core.

Negative and tradeoffs:

- SIDScope cannot promise one-command training or model reproduction;
- evidence producers must implement exporters and identity bindings;
- comparisons are rejected when profiles or target universes are incompatible;
- some full artifacts remain externally hash-bound rather than redistributed.

## Migration and Validation

The 1.1.1 route-specific verifiers remain regression authorities while shared
contracts and profiles are introduced. Each route migrates only after positive,
negative, metric, binding and hash parity. Rollback selects the previous
versioned verifier path and never mutates admitted evidence.

This ADR is implemented by `SIDSCOPE_SYSTEM_ARCHITECTURE.md` and staged through
`V1_2_TO_V2_ROADMAP.md`.
