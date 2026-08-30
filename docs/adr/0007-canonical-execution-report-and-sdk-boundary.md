# ADR-0007: Canonicalize execution evidence and reports without owning training

Status: Accepted

Date: 2026-08-30

## 1. Context

Sprint 2 ended at PreparedDataset. Existing generator routes then diverged into
method-specific selection, run, checkpoint, trace, metric, and report dialects.
A shared platform needs a common dependency chain, but flattening native AR,
parallel-graph, masked-diffusion, retry, or overlay semantics would invalidate
the evidence. Absorbing training would also violate SIDScope's product boundary.

## 2. Decision Drivers

- Bind every reported result to ordered episodes, source, prepared data, run,
  checkpoint, and native trace payload identities.
- Preserve method-family-native trace semantics outside the common envelope.
- Recompute metrics and failure partitions from bounded common observations.
- Keep historical route evidence immutable and legacy verifiers authoritative.
- Provide a small adapter-facing API and CLI without introducing plugin
  discovery, a database, or a training runner in 1.2.

## 3. Options Considered

| Option | Benefit | Cost | Reversibility |
| --- | --- | --- | --- |
| Continue route-specific reports | No migration work. | Divergent identities, metrics, and packaging remain. | High but does not reach the target architecture. |
| Flatten all native traces into one event model | One apparent schema. | Falsifies method semantics and loses unsupported telemetry. | Low. |
| Common envelope plus native payload binding | Shared provenance and diagnostics while retaining native behavior. | Requires two-level validation and explicit capability declarations. | High. |
| Own training and checkpoint production | Potentially uniform runs. | Duplicates upstream frameworks and expands the product beyond conformance. | Low. |

## 4. Decision

Adopt EpisodeSelection, RunIdentity, CheckpointBinding, TraceEnvelope,
DiagnosticReport, ConformanceReport, and EvidenceIndex v1. TraceEnvelope owns
only common observation summaries and binds a separate payload schema and hash.
Native ancestry, graph propagation, adaptive unmasking, retries, or overlays
remain in that payload and must not be synthesized when unavailable.

RunIdentity records source, prepared data, configuration, command, environment,
seed, and optional training-manifest identity. CheckpointBinding records either
complete resumable provenance or explicitly inference-only state. SIDScope
validates these records but does not run or redefine upstream training.

Adapter SDK `0.1.0-alpha` validates capability descriptors and producer output
against the registry. The shared CLI exposes adapter preflight, contract and
trace validation, evaluation, conformance verification, and deterministic
evidence-index packaging. Plugin discovery remains a 1.3 concern; immutable
object storage and SQLite projections remain 1.4 concerns.

## 5. Consequences

The canonical dependency graph is complete and acyclic for 1.2. Metrics,
failure decomposition, rank censoring, and compute summaries are reproducible
from the canonical fixture. A capability declaration distinguishes supported
from unavailable telemetry, so missing fields cannot silently become evidence.

EvidenceIndex is a deterministic dependency index, not the 1.4 immutable
EvidenceBundle store. A `fixture_pass` conformance decision proves contract
behavior only and cannot promote a method to named-adapter status.

## 6. Migration and Validation

RPG supplies the first end-to-end canonical fixture and retains its native
parallel/unordered payload. All other active routes keep their legacy evidence
and verifier as authority; the migration matrix records a typed regeneration
requirement rather than inferring missing canonical artifacts. Static mapping
routes explicitly do not require runtime traces.

Validation includes positive and typed-negative fixtures, dependency/hash and
privacy checks, CLI round trips, method-native payload binding, route inventory
coverage, architecture tests, a six-command CPU baseline, package verification,
deterministic archive smoke, and isolated installation.

## 7. Rollback

Remove the seven registry entries and SDK/CLI dispatch, then continue to use
the unchanged route-specific verifiers. Canonical fixtures and indexes may be
discarded; historical evidence, upstream checkpoints, and native payloads are
not modified by the rollback.
