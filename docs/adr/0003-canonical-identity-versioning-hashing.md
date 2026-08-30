# ADR-0003: Canonical Identity, Version Axes, and Non-Self-Referential Hashing

## Status

Accepted on 2026-08-30.

## Context

SIDScope 1.1 routes use many versioned JSON dialects and several local
`canonical_hash` implementations. The 1.2 Contract Layer needs one identity and
hashing rule before shared models are introduced. A hash embedded in the object
it hashes is self-referential; silently excluding arbitrary nested fields would
also make evidence identity ambiguous.

## Goals

- give canonical artifacts portable and deterministic identities;
- separate product, SDK, schema, profile, and bundle compatibility;
- preserve every supported 1.1 artifact without silent reinterpretation;
- make self-reference and unsupported migration fail closed.

## Non-Goals

- rewriting historical 1.1 evidence under new schemas;
- selecting a binary serialization format;
- assigning one product version to every independently versioned contract.

## Constraints

- Python 3.9+ and the standard library remain sufficient for core validation;
- canonical artifacts must remain inspectable JSON;
- public verification must work without upstream runtimes or private assets;
- accepted bundles and release tags are immutable.

## Decision Drivers

| Priority | Driver | Measurement |
| ---: | --- | --- |
| 1 | Unambiguous identity | The same JSON value has one canonical byte sequence and hash. |
| 2 | Fail-closed compatibility | Unknown major schemas and unsupported revisions are rejected. |
| 3 | Historical continuity | Legacy artifacts retain their original bytes, IDs, and verifier authority. |
| 4 | Independent evolution | Package, SDK, schema, profile, and bundle versions can change separately. |

## Options Considered

| Option | Advantages | Disadvantages | Reversibility |
| --- | --- | --- | --- |
| Hash complete files including their hash field | Appears simple. | Self-referential and impossible to stabilize. | Rejected. |
| Let each route define hashing and versioning | No migration work. | Preserves drift and makes shared verification ambiguous. | Easy short term, costly later. |
| One canonical JSON rule with an explicit top-level hash exclusion and independent version axes | Deterministic, inspectable, and compatible with staged migration. | Requires shared helpers and explicit registries. | High through new schema majors. |

## Decision

Canonical JSON v1 uses UTF-8, sorted object keys, compact separators,
`ensure_ascii=false`, and rejects NaN or infinity. `canonical_sha256(value)`
hashes the exact JSON value. A canonical artifact with `content_sha256` hashes a
shallow copy with exactly that top-level field removed. No nested field and no
other hash-looking field is excluded implicitly.

Canonical artifacts include:

- a stable schema major ID such as `sidscope.source_identity.v1`;
- a semantic `schema_revision`, initially `1.0.0`;
- an explicit producer name and version;
- an externally reproducible `content_sha256` calculated by the rule above.

SIDScope tracks five independent compatibility axes:

1. product/package version;
2. Adapter SDK version;
3. schema major ID and schema revision;
4. conformance-profile version;
5. evidence-bundle format version.

Schema IDs change only for incompatible meaning. Compatible additive revisions
increment `schema_revision`; a verifier declares the revision range it accepts.
An old major is never silently upgraded. Migration creates a new artifact with
an explicit dependency on the old artifact or requires regeneration.

## Architecture Impact

- `sidinspector.contracts.hashing` is the canonical implementation.
- Route-local hash functions remain compatibility authorities until migrated.
- Release manifests or bundle indexes bind verifier-file hashes; a verifier
  never validates a hash embedded in its own source.
- `docs/COMPATIBILITY.md` records supported version combinations.
- The first vertical slice is `SourceIdentity v1`; later entities reuse the
  same envelope and hashing rule after parity tests.

## Rollout, Validation, and Rollback

The shared hash implementation is introduced beside legacy functions. Each
route migrates only after byte, hash, outcome, and typed-failure parity for its
declared domain. A mismatch keeps the legacy path authoritative. Rollback
removes shared dispatch for that entity; no old artifact is rewritten.

Validation includes canonical-order independence, Unicode, NaN rejection,
content-hash mismatch, unknown-field, and legacy-field parity tests.

## Consequences

Positive:

- content identity is deterministic and non-self-referential;
- compatibility decisions are explicit rather than inferred from package
  versions;
- future registries can address artifacts by a stable payload hash.

Negative and tradeoffs:

- artifact producers must normalize ordering for semantically unordered lists;
- five version axes require a maintained compatibility matrix;
- legacy schemas remain visible during coexistence instead of disappearing in
  one refactor.
