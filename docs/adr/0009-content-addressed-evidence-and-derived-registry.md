# ADR-0009: Make immutable evidence objects authoritative and SQLite derived

Status: Accepted

Date: 2026-08-30

## 1. Context

SIDScope 1.2 made evidence dependencies explicit, and 1.3 made adapter and
native-trace semantics extensible. Those releases can verify individual files,
but they do not yet provide an authoritative, correction-safe evidence system.
The 1.4 milestone must package a complete result without embedding restricted
assets, support deterministic local queries, and distinguish scientific
differences from incompatible evaluation contracts.

The implementation remains a local-first modular monolith. The expected load is
research-scale and single-writer; no availability or throughput requirement
justifies a hosted service, distributed database, message bus, CQRS service
split, or event-sourcing framework.

## 2. Decision Drivers

- Immutable, reproducible evidence identity independent of a mutable database.
- Fresh-CPU verification and deterministic reconstruction from public objects.
- Fail-closed privacy, provenance, rank-censoring, and comparison behavior.
- Corrections that preserve the original record and make supersession explicit.
- Restricted assets represented by declared hashes and counts, not copied data.
- A rollback that cannot destroy the authoritative evidence surface.

## 3. Options Considered

| Option | Benefit | Cost | Reversibility |
| --- | --- | --- | --- |
| SQLite as source of truth | Familiar queries and transactions. | Database bytes and migrations become evidence identity; deletion risks loss. | Low. |
| Append-only event store plus projections | Rich temporal reconstruction. | Adds event semantics and operational complexity not required by the workflow. | Medium. |
| Immutable JSON objects plus SQLite projection | Portable authority, deterministic rebuild, simple local queries. | Requires strict admission and projection parity tests. | High. |
| Hosted registry service | Central discovery. | Adds availability, authentication, deployment, and privacy scope before 2.0. | Medium. |

## 4. Decision

Use canonical `EvidenceBundle v1` JSON objects as the source of truth. Their
top-level `content_sha256` follows SIDScope canonical JSON v1 and excludes only
that top-level field, avoiding self-reference. Store admitted bundles under
`bundles/sha256/<prefix>/<content_sha256>.json`; public artifact bytes use the
parallel `objects/sha256` layout keyed by exact-byte `object_sha256`. Artifact
records retain canonical artifact `content_sha256` separately. Writes are atomic and idempotent, and an
existing object with different content is a collision, not an update.

Use standard-library SQLite only as a disposable query projection. It stores
bundle, artifact, metric, and supersession rows, all recoverable from immutable
objects. Static exports are canonical, sorted JSON without local paths or
timestamps. A correction is a new bundle whose `supersedes` edge names the old
bundle; old objects are never updated. Quarantine changes admission/query state,
not object identity.

Keep `EvidenceIndex v1` unchanged as the 1.2 dependency inventory.
`EvidenceBundle v1` is the independently versioned 1.4 packaging and registry
format, not a silent reinterpretation of an EvidenceIndex.

## 5. Architecture Impact

### Boundaries and contracts

- `evidence.bundle` owns bundle validation, result cards, provenance, privacy,
  and supersession declarations.
- `evidence.object_store` owns content-addressed paths, atomic admission,
  verification, enumeration, and quarantine.
- `evidence.registry` owns the SQLite projection and deterministic static view.
- `evidence.comparison` owns compatibility checks and metric deltas.
- `cli` orchestrates those public APIs but owns no evidence semantics.

The public bundle contract is exact at
`sidscope.evidence_bundle.v1@1.0.0`. Additive compatible changes require a
declared supported revision; changed meaning, privacy rules, comparison
denominators, or censoring semantics require a new schema major.

### Data and consistency

The object directory is authoritative and strongly consistent for local atomic
writes. SQLite is an eventually reconstructed projection. Admission verifies
hashes, provenance, privacy, and available public objects before indexing.
Hash-only restricted references require no private source bytes.

### Failure modes and resilience

- Partial writes remain temporary and are never admitted as objects.
- Hash collision, object tampering, broken provenance, privacy leakage, missing
  embedded artifacts, and invalid rank claims fail closed with typed errors.
- A deleted or corrupt SQLite database is rebuilt from immutable bundles.
- An invalid bundle is quarantined and superseded; it is never repaired in
  place.

### Security and privacy

Admission and export scan structured keys and text for raw identities, private
absolute paths, checkpoint payloads, credentials, and secrets. The scanner does
not treat the required false-valued privacy declarations themselves as leaks.
SIDScope stores no credential material and does not need upstream restricted
assets to verify hash-only references.

## 6. Rollout, Validation, and Rollback

Roll out additively beside existing EvidenceIndex and route-specific evidence.
Validation covers deterministic build, tamper/collision rejection, provenance
DAG checks, privacy negatives, hash-only assets, add/list/show, compatible and
incompatible comparisons, supersession, database deletion/rebuild parity,
static export parity, CLI round trips, full CPU tests, resource verification,
archive smoke, and G8 fresh installation.

Rollback removes the derived SQLite database and 1.4 CLI routes. Existing 1.1
authorities, canonical 1.2 contracts, and 1.3 plugins remain unchanged. Admitted
objects are retained; a bad object is quarantined and superseded rather than
deleted or rewritten.

## 7. Consequences

SIDScope gains an auditable evidence authority without taking ownership of
training or operating a service. Registry queries are reproducible and local,
and correction history becomes explicit. The tradeoff is stricter admission:
producers must provide complete compatibility, provenance, privacy, and rank
semantics before their result can enter the registry.

## 8. Links

- `docs/EVIDENCE_BUNDLES_AND_REGISTRY.md`
- `docs/V1_2_TO_V2_ROADMAP.md`
- ADR-0003, ADR-0007, and ADR-0008
