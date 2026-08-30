# SIDScope Compatibility Matrix

Status: SIDScope 1.2 development closure baseline

## Product and Entry Points

| Product line | Distribution | Python import | Product CLI | Status |
| --- | --- | --- | --- | --- |
| 1.0.2 | `sidinspector` | `sidinspector` | route-specific commands | Frozen TOIS-bound release |
| 1.1.0 | `sidinspector` | `sidinspector` | route-specific commands | Published maintenance release |
| 1.1.1.dev0 | `sidinspector` | `sidinspector` | `sidscope` facade plus legacy commands | Frozen regression authority |
| 1.2.0.dev0 | `sidinspector` | `sidinspector` | registry-backed `sidscope` facade plus legacy commands | Sprint 1--4 development closed; public release not implied |

No import or distribution rename is planned during 1.x. The facade validates
all eleven canonical 1.2 contracts and provides adapter preflight, trace
validation, deterministic evaluation, conformance-report verification, and
evidence-index packaging. Legacy route commands remain public and authoritative
during migration.

## Version-Axis Baseline

| Axis | Current value | Compatibility rule |
| --- | --- | --- |
| Product/package | `1.2.0.dev0` | PEP 440 development version; not a public 1.2.0 release. |
| Adapter SDK | `0.1.0-alpha` | Capability descriptor and harness are usable; plugin discovery and stable compatibility begin later. |
| Canonical schemas | Eleven registry entries from SourceIdentity v1 through EvidenceIndex v1, each at revision `1.0.0` | Registry-declared exact major and supported revision required. |
| Conformance profiles | legacy C0--C5 and G0--G5 authorities | Existing route verifiers remain authoritative until exact parity migration. |
| Evidence bundle | deterministic EvidenceIndex v1 plus route-specific 1.1 authorities | Indexes are reproducible; immutable object storage remains a 1.4 feature. |

The canonical schema IDs are `sidscope.source_identity.v1`,
`sidscope.dataset_identity.v1`, `sidscope.sid_space_identity.v1`,
`sidscope.prepared_dataset.v1`, `sidscope.episode_selection.v1`,
`sidscope.run_identity.v1`, `sidscope.checkpoint_binding.v1`,
`sidscope.trace_envelope.v1`, `sidscope.diagnostic_report.v1`,
`sidscope.conformance_report.v1`, and `sidscope.evidence_index.v1`.

## Schema Compatibility

- A schema ID suffix `vN` is the semantic major.
- `schema_revision` is semantic within that major.
- Compatible additive revisions require verifier-declared support.
- Removed fields, changed meaning, denominator changes, altered censoring, or
  new required semantics require a new major schema/profile.
- Unknown majors, unknown required dependencies, and unsupported revisions fail
  closed.
- Historical evidence is replayed by its original verifier or migrated into a
  new artifact with an explicit dependency; it is never rewritten in place.

## SourceIdentity v1 Migration

`sidscope.adapter_manifest.v1` remains a legacy authority. The shared converter
maps its source fields into `sidscope.source_identity.v1` and parity tests require
exact preservation of repository URL/revision, license marker/identifier,
redistribution policy, derivation, artifact name, source ID, and paper label.
The converter does not invent a paper URL, notices, or patches.

Rollback removes the shared dispatch and leaves the legacy manifest and report
unchanged.

## DatasetIdentity v1 Migration

`DatasetIdentity v1` distinguishes `fully_bound` from `legacy_partial`.
Complete identities require ordered train/validation/test IDs, counts and
hashes, category/profile, catalog and target-universe hashes, and a public
pseudonymous item-identity policy. The adapter-manifest converter preserves
name, normalized name and expected item count but explicitly records missing
bindings. `sid_depth` is returned separately for the later SIDSpace migration.

The authoritative registry is `sidscope.contract_registry.v1` revision
`1.0.0`; it rejects unknown/cyclic dependencies and unsupported revisions.
Rollback removes the shared registry entry without rewriting legacy evidence.

## SIDSpaceIdentity and PreparedDataset v1 Migration

SIDSpaceIdentity keeps tokenizer/SID structure separate from dataset identity.
Legacy adapter manifests retain only proven depth and SID-cache hash and are
typed `legacy_partial`. PreparedDataset requires fully bound DatasetIdentity
and SIDSpaceIdentity content hashes plus exact split, artifact, catalog and
target-universe parity.

The complete RPG prepared fixture migrates deterministically. Current
DiffGRM/LLaDA prepared v1 artifacts require regeneration because canonical
split counts or artifact bindings are absent. No historical evidence is
rewritten. Rollback removes the two registry entries and resumes the unchanged
route-specific validators.

## Execution, Report, SDK, and CLI Compatibility

EpisodeSelection, RunIdentity, CheckpointBinding, TraceEnvelope,
DiagnosticReport, ConformanceReport, and EvidenceIndex use schema major v1 and
revision `1.0.0`. TraceEnvelope's native `payload_schema` is independently
versioned: compatibility of the common envelope never implies compatibility of
AR, parallel graph, masked diffusion, retry, or overlay payload semantics.

Adapter SDK `0.1.0-alpha` is deliberately narrower than the future plugin API.
The distribution and import remain `sidinspector`; the product command is
`sidscope`. Legacy CLIs and evidence remain unchanged. The migration matrix
covers all six generator and nine static-mapping routes. RPG has exact
canonical fixture parity; other routes receive a typed regeneration disposition
and retain legacy status authority. An incomplete migration cannot promote an
adapter or rewrite historical evidence.
