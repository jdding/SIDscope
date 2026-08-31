# ADR-0014: Publish Additive Runtime, Conformance, and Evidence Profiles

- Status: Accepted
- Date: 2026-08-31
- Scope: SIDScope 1.7 release engineering
- Owner: SIDScope maintainers

## Context

The 1.7 reviewer archive mixed the installable product, adapter-development
fixtures, historical tests, paper-oriented tables, and complete trained-smoke
traces. Its compressed size was modest, but the single surface exposed 541
files and made the product appear to require the entire audit corpus.

The repository and evidence authority must remain intact. The decision is about
release views, not source deletion, method behavior, evidence weakening, or a
new product version.

## Decision drivers

1. The default download must communicate the product boundary clearly.
2. Complete evidence must remain immutable, hash-bound, and independently
   downloadable.
3. Adapter authors need compact positive/negative fixtures without trained
   traces.
4. Existing 1.7 evidence-full behavior must remain reproducible and reversible.
5. Every view must be selected from the same public manifest authority.

## Options considered

| Option | Result |
|---|---|
| Keep one full archive | Rejected: simplest implementation but conflates three audiences and makes evidence volume look like runtime complexity. |
| Move evidence to a new repository immediately | Rejected: adds repository/version/ownership coordination before the release boundary is proven. |
| Publish three additive profiles from one repository and manifest | Accepted: smallest reversible change with explicit audience boundaries. |

## Decision

SIDScope 1.7 defines `runtime`, `conformance`, and `evidence-full` profiles. The
default is `runtime`; the profiles form strict subsets. A machine-readable
registry defines selection, and every archive receives a generated deterministic
receipt binding the registry, source manifest, version, and selected path set.

The topology remains one local-first modular monolith and one repository. No
service, data store, external artifact registry, or second development branch is
introduced.

## Compatibility and failure behavior

- `evidence-full` preserves the old public-manifest selection.
- Commands that require the former full reviewer surface must pass
  `--profile evidence-full` explicitly.
- Smoke and G8 discover and verify the embedded profile receipt.
- Unknown profiles, missing required paths, path-set tampering, profile/smoke
  mismatch, and trained-trace leakage fail closed with typed errors.
- Product, SDK, schema, conformance-profile, and evidence-bundle versions do not
  change.

## Rollout and validation

1. Add the registry, resolver, receipt, and profile-aware builder.
2. Add profile-specific smoke suites and make G8 validate `runtime` by default.
3. Prove strict subset relationships and deterministic double builds.
4. Retain `evidence-full` smoke as the complete resource-package replay.
5. Publish separately named assets only after tag authorization.

Success means the runtime asset contains no tests, examples, tracked evidence,
or trained traces; all three profiles pass their own smoke; runtime passes an
isolated install; and evidence-full preserves the complete resource verifier.

## Rollback

The previous behavior is recovered by building `--profile evidence-full` and
publishing only that asset. The profile registry and smaller assets can be
ignored without modifying evidence or contracts.

## Consequences

The release process produces more than one asset and must report each hash.
That small operational cost buys a clear default product surface while keeping
the complete audit package available. Profile proliferation beyond these three
is explicitly out of scope for 1.7.
