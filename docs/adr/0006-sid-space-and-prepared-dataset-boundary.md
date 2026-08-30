# ADR-0006: Separate SID Space Identity from Prepared Dataset Bindings

Status: Accepted

Date: 2026-08-30

## 1. Context

Legacy route contracts mix dataset identity, tokenizer/cache identity, prepared
artifacts, training configuration, and evaluation selection. This makes an
apparently compatible dataset unsafe to reuse when SID ordering, offsets,
special tokens, hierarchy, collision handling, or de-duplication differ.

## 2. Decision Drivers

- Preserve native ordered, unordered, hierarchical, and masked SID semantics.
- Make tokenizer identity an explicit experimental factor.
- Bind normalized prepared data without leaking source user/item identifiers.
- Support incremental migration without rewriting historical evidence.
- Keep canonical contracts independent from optional adapter runtimes.

## 3. Options Considered

| Option | Benefit | Cost | Reversibility |
| --- | --- | --- | --- |
| Put all fields in DatasetIdentity | One artifact. | Conflates source data and tokenizer semantics; unsafe reuse. | Low. |
| One route-specific prepared schema per method | Minimal short-term change. | Repeats validators and prevents shared conformance. | Medium. |
| Separate SIDSpaceIdentity and PreparedDataset | Explicit factorization and reusable bindings. | Adds dependency validation and migration work. | High. |

## 4. Decision

Adopt `sidscope.sid_space_identity.v1` and
`sidscope.prepared_dataset.v1` at revision `1.0.0`.

`SIDSpaceIdentity` owns tuple ordering, fixed/variable depth, hierarchy,
codebook sizes, position offsets, model vocabulary, special tokens, tokenizer
configuration/artifact hashes, collision semantics, and de-duplication.

`PreparedDataset` depends on complete `DatasetIdentity` and
`SIDSpaceIdentity` artifacts. It owns normalized pseudonymous representation,
ordered train/validation/test bindings, interaction/mapping/SID-cache artifact
hashes and counts, catalog, and target universe. It does not own training,
checkpoint, episode selection, evaluation labels, or decoder behavior.

## 5. Consequences

RPG's complete prepared bridge migrates deterministically and preserves its
unordered graph semantics. Legacy adapter manifests retain known depth/cache
hashes as `legacy_partial`. DiffGRM and LLaDA prepared v1 artifacts lack enough
counts or artifact bindings and must be regenerated; the migration layer must
not infer them.

## 6. Migration and Validation

The two schemas are registered with canonical and typed-negative fixtures.
`PreparedDataset` declares exact dependencies on DatasetIdentity v1 and
SIDSpaceIdentity v1. The verifier checks content hashes, dependency hashes,
split/catalog/universe parity, SID-cache binding, privacy, RPG migration
parity, and typed regeneration of incomplete legacy routes.

Legacy route verifiers remain authoritative during coexistence. New canonical
artifacts do not alter old evidence or model execution.

## 7. Rollback

Remove the two registry entries and generic CLI dispatch, then route consumers
back to the unchanged legacy prepared-data validators. Generated canonical
fixtures may be discarded because their RPG source fixture is unchanged.
