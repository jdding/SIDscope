# ADR-0005: Make the Contract Registry Authoritative and Bound Dataset Identity Explicitly

## Status

Accepted on 2026-08-30.

## Context

SourceIdentity proved the canonical hashing and validation pattern, but CLI
dispatch still hard-coded one type. Dataset descriptions were duplicated
across adapter manifests and prepared-data formats, and older manifests lacked
split, catalog, and target-universe hashes. Treating those older fields as a
complete dataset identity would invent evidence; putting SID depth in the new
dataset model would also collapse the Dataset and SIDSpace boundaries.

## Goals

- provide one machine-readable authority for contract discovery and dispatch;
- reject unknown, cyclic, or revision-incompatible dependencies;
- bind datasets, splits, catalog, target universe, and public identity policy;
- preserve legacy dataset fields without fabricating missing provenance;
- keep tokenizer/SID-space semantics outside DatasetIdentity.

## Non-Goals

- migrate prepared-data or SID-space contracts in this sprint;
- rewrite historical route evidence;
- infer train/validation/test hashes from unrelated legacy input artifacts;
- create a hosted registry service.

## Options Considered

| Option | Advantages | Disadvantages | Reversibility |
| --- | --- | --- | --- |
| Continue hard-coded CLI choices | Minimal code. | No owner/version/fixture authority; drift grows per contract. | Easy now, costly later. |
| Treat every legacy manifest as fully bound | Simple migration label. | Invents split and universe identity and mixes SID depth into data identity. | Unsafe because claims become ambiguous. |
| Bundled registry plus explicit full/partial DatasetIdentity states | Local-first, inspectable, fail-closed, and preserves old evidence honestly. | Requires registry governance and partial-state handling. | High; dispatch can return to legacy paths. |

## Decision

The packaged `sidscope.contract_registry.v1` is the sole canonical contract
catalog. Each entry declares a CLI type, schema major/revision, owner, bundled
JSON Schema 2020-12 resource, compatibility policy, canonical and typed-negative
fixtures, dependencies, and result identity field. Registry and contract
artifacts use ADR-0003 canonical content hashing.

`sidscope.dataset_identity.v1` owns only dataset identity: name/category/profile,
ordered train/validation/test bindings, catalog and target-universe bindings,
and pseudonymous item-identity policy. `fully_bound` requires all bindings.
Legacy adapter manifests migrate to `legacy_partial`, with missing fields
enumerated and no invented hashes. Their `sid_depth` is returned separately for
the planned SIDSpace migration.

## Architecture Impact

- `sidscope contract list/show/validate` resolves through the registry;
- contracts remain standard-library-only and do not import adapter runtimes;
- architecture inventory embeds the verified registry and evidence chain;
- release verification checks registry metadata, resources, fixtures, and
  typed failures;
- future contract slices extend the registry rather than add CLI choices.

## Rollout, Validation, and Rollback

SourceIdentity and DatasetIdentity run beside legacy authorities. Tests cover
canonical positives, typed negatives, unknown dependency, cycle, unsupported
revision, canonical order, installed schema resources, CLI dispatch, and every
legacy adapter-manifest dataset projection. Full CPU package, deterministic
archive, archive smoke, and G8 remain release gates.

Rollback removes the DatasetIdentity registry entry and its CLI dispatch. It
does not alter a legacy manifest, report, or evidence hash.

## Consequences

Positive: contract discovery is explicit; dataset provenance cannot silently
degrade; SID-space semantics retain a clean future boundary.

Tradeoffs: partial legacy identities require explicit handling; the checked-in
registry and compatibility matrix must change together; complete legacy route
migration waits for prepared-data evidence rather than guessed bindings.
