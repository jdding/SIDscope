# Conformance Profile Governance

Status: active policy for SIDScope 1.5

Conformance profiles are versioned policy, not aliases for an adapter or a
paper. A profile states which evidence gates apply, their dependency order,
which status labels can be derived, and how the definition evolves. Method and
training behavior remain upstream.

## Required Definition

Every active profile must declare:

- a stable profile ID and semantic revision;
- one profile owner role;
- its kind: static mapping, generator, overlay or release;
- ordered gates with typed failure codes and dependencies;
- allowed derived status labels;
- one positive fixture and registered negative fixtures;
- a migration policy, deprecation state and prior-compatible revision where
  applicable;
- the DatasetProfileDescriptor and artifact roles it requires.

A profile with a missing owner, fixture, migration policy or status policy is
not active and cannot admit evidence.

## Semantic Versioning

- Patch: fixes an implementation or fixture bug without changing accepted
  inputs, gate meaning, status meaning or privacy boundary.
- Minor: adds optional evidence or a new compatible status/gate path. Existing
  passing reports retain their meaning.
- Major: changes a required gate, denominator, status meaning, privacy rule or
  compatibility boundary. Existing reports remain bound to the old major.

Profile revisions are independent of the package version. Published reports
bind the exact profile definition hash and are never reinterpreted by a later
revision.

## Review and Activation

Activation requires profile-owner review, positive and typed-negative fixture
coverage, deterministic report reproduction, compatibility classification and
a documented rollback. Security/privacy review is mandatory when artifact
roles, path handling, identity fields or redistribution boundaries change.

Source license state is required metadata. `NOASSERTION`, missing repository
license or author clarification can constrain execution or redistribution, but
the marker alone does not falsify technical conformance. A profile must keep
technical, execution and redistribution decisions separate.

## Status Derivation

An active status label comes only from a passing, hash-bound
ProfileConformanceReport under a label allowed by its profile. Registry rows,
Markdown and CSV views are generated projections; editing them cannot promote
or demote an adapter. Partial and failed reports remain evidence and use only
the profile's registered non-passing labels.

## Migration and Deprecation

A new revision includes one of:

- exact compatibility with the prior revision;
- a deterministic migration or replay path;
- an immutable historical disposition stating why replay is impossible.

Deprecation leaves the prior definition readable and verifiable for at least
one released minor line. Retirement blocks new admissions but does not delete
old definitions, reports or bundles. The rollback for a faulty revision is to
pin the prior active profile and quarantine only newly invalid submissions.

## Ownership Separation

Profile approval, adapter maintenance, evidence admission and release approval
are separate decisions even when one maintainer holds all roles. The path
mapping is documented in `CODE_OWNERSHIP.md` and `.github/CODEOWNERS`.
