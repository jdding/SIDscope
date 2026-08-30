# ADR-0011: Govern evidence admission through versioned profiles and reports

## Status

Accepted on 2026-08-30.

## Context

SIDScope 1.4 made immutable EvidenceBundle objects authoritative and the local
SQLite registry disposable. Adapter status, however, still spans legacy
ledgers, route-specific verifiers and prose. A third-party submission therefore
cannot yet prove, using one public workflow, which profile was applied, why a
status label was assigned, or whether its result can enter a public index.

The 1.5 milestone must close that gap without executing untrusted method code,
absorbing upstream training, mutating historical bundles, or creating a hosted
review service.

## Decision Drivers

- One fail-closed verification path for static mapping, generator, overlay and
  release profiles.
- Status labels derived from hash-bound reports rather than edited registry
  rows.
- Dataset, evaluation and privacy boundaries explicit before evidence review.
- Offline third-party submissions that are safe to inspect on CPU.
- Deterministic public views that can be deleted and rebuilt.
- Profile evolution with owners, semantic versions, fixtures and rollback.

## Options Considered

| Option | Advantage | Cost | Reversibility |
| --- | --- | --- | --- |
| Keep route-specific admission | Minimal short-term work. | Continues verifier edits and manual status drift. | Low. |
| Treat EvidenceBundle presence as conformance | Reuses the 1.4 object store. | Confuses packaging with scientific/profile validation. | Low. |
| Profile-governed report plus independent submission checker | Keeps contracts, conformance and evidence roles separate; supports offline review. | Adds two versioned contracts and migration reports. | High. |
| Hosted submission service | Central workflow. | Adds auth, tenancy, availability and untrusted execution scope. | Medium. |

## Decision

Introduce two independent public contracts:

1. `DatasetProfileDescriptor v1` binds split identities, catalog, target
   universe, evaluation cutoff, publication depth, slices and privacy policy.
2. `ProfileConformanceReport v1` binds a semantic profile revision, descriptor,
   artifacts, ordered gate outcomes and a status label allowed by that profile.

A versioned profile catalog defines static-mapping, generator, overlay and
release profiles. Every active definition has an owner, semantic revision,
positive fixture, registered negatives, migration policy, deprecation state and
allowed status-label policy. The shared engine validates reports against those
definitions and derives the decision; callers cannot assert an unregistered
label.

An `EvidenceSubmission v1` is a path-safe, hash-bound package index. The
submission checker validates structure, completeness, descriptor/report/bundle
compatibility, rank claims and privacy without importing an adapter or upstream
runtime. Passing a submission permits admission; it does not change or replace
the immutable identities of contained artifacts.

Status and result indexes are deterministic projections of passing reports and
admitted bundles. They contain no timestamps or local paths and are never a
write API. Legacy ledgers remain read-only parity inputs until 1.6 migration or
archival proves that the generated views can replace them.

## Architecture Impact

`conformance_core` owns profile definitions, descriptor/report validation and
gate decisions. `submission` is an application-service module that may depend
on contracts, conformance and evidence public APIs but none of those modules may
depend on it. The CLI orchestrates both. This is still one local Python package
and one CPU process; it does not add a seventh product layer or a deployable
service.

Profile schemas and bundle schemas remain independently versioned. A new
profile revision cannot reinterpret an existing passing report. A corrected
report or bundle receives a new content hash and an explicit supersession or
migration record.

## Security and Privacy

Submission members must use root-contained relative paths. Absolute paths,
path traversal, credentials, private identity fields, checkpoint payloads and
unsupported exact-rank claims fail closed before admission. The checker reads
declared JSON evidence only and never runs packaged commands or plugins.

## Rollout and Validation

- Keep existing 1.3 profile composition and 1.4 bundle APIs compatible.
- Register the four 1.5 profile classes with positive and typed-negative
  fixtures.
- Prove one separately packaged reference adapter submission without core
  verifier edits.
- Generate status/result views and compare them with read-only legacy ledgers.
- Exercise all registered negative packages, full CPU tests, resource checks,
  archive smoke and isolated installation.

## Rollback

Disable admission under the faulty profile revision and pin the prior passing
profile/CLI combination. Delete and rebuild derived indexes. Preserve submitted
packages, reports, bundles and historical ledgers unchanged for audit. A fix
uses a new profile revision or artifact hash; it never edits prior evidence.

## Consequences

Positive consequences are reproducible status decisions, independent
third-party checking and a clean boundary between verification and evidence
storage. The main tradeoff is stricter onboarding: a producer must describe its
dataset/evaluation/privacy boundary and supply complete hash-bound artifacts
before it can be admitted.

## Links

- `docs/V1_2_TO_V2_ROADMAP.md`
- `docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md`
- `docs/EVIDENCE_BUNDLES_AND_REGISTRY.md`
- ADR-0008 and ADR-0009
