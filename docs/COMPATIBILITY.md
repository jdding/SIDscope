# SIDScope Compatibility Matrix

The local `1.7.0.dev0` engineering candidate is frozen by ADR-0024. N03-N08
technical scope is verified; independent_user_actual_use is excluded from
current gates by ADR-0025 and the fact stays not verified, while certification
additionally requires same-source delivery evidence. This does not create an
RC, public 2.0 compatibility promise or release authorization.

Adapter SDK `1.0.0` is the stable extension boundary with plugin API `1.0`.
The runtime preserves exact interval-based 0.2 replay and historical SDK 0.1
descriptors; it does not silently reinterpret their claims. The 39-symbol
curated facade remains unchanged. Approved new workflows are opt-in modules,
including mapping preflight, native admission, paired regression, diagnostic
review and SID refresh.

Local workflow policy (ADR-0018) keeps trusted input budgets caller-configured.
Untrusted submission and canonical loader safeguards remain bounded and typed.
N07 requires explicit ordered-prefix, parallel-position or unordered-set
semantics and never changes native SIDs. N08 evidence applies only to the two
measured 100-episode routes; it is not a production SLO.

<!-- SIDSCOPE:CURRENT:BEGIN -->
Local development: `1.7.0.dev0`; public GitHub remains 1.1.x; 1.8/1.9 inactive.
Current diagnostic admission and comparison require input-bound recomputation; declarations alone do not pass.
Unclosed SDLC requirements: F09.
Requirement snapshot: `d84f1b924e203550bd953ad5254467d09079fc49aee229ed85e189e890ac0e2c`.
Acceptance scope: `docs/reproducibility/sidscope_acceptance_scope.v1.json` revision 2 snapshot `fc0ab4a29822290d43eb190364443c5afbc7d288de57ed30988f0269f26db9db`.
Acceptance scope decision: independent_user_actual_use excluded from current gates (2026-09-27, docs/adr/0025-remove-independent-user-acceptance-gate.md); the adoption fact stays not_verified.
Historical route decisions (not newly recomputed training): dact_tiger=named_adapter; diffgrm_www2026=named_adapter; isd=close_named_adapter; latte_psid=named_adapter; llada_rec=named_adapter; rpg_kdd2025=named_adapter.
Historical route snapshot: `cb51983ca33506c4c00f1722eda8e5eb9eb452409ce026f9810a76fe1cf02a92`.
Independent user actual use is excluded from current certification, RC and delivery gates by acceptance scope policy revision 2; it remains not verified and is not a current prerequisite. No push, tag, public release or TOIS mutation is authorized.
<!-- SIDSCOPE:CURRENT:END -->

Status: SIDScope 1.7 contract/public-surface stabilization baseline

Current local safety exception (ADR-0016): new submission admission and default
indexes require protocol-bound diagnostic recomputation. Missing inputs fail
with `independent_gate_verification_required` or a typed input error. Explicit
historical replay remains available but is not new admission. Profile CLI
verification exposes `structure_only`/`unverified`; standard metric ranges and
target-state invariants reject previously accepted contradictory documents.
No immutable artifact is rewritten. Release receipt v2 verifies member bytes;
legacy receipts require rebuilding for current delivery verification. These
pre-stable restrictions remain in `1.7.0.dev0` and do not alter released 1.1.x.

The existing `verify` command additionally accepts `--diagnostic`, `--trace`
and `--selection` together for CPU recomputation. Its output distinguishes
`diagnostics_from_supplied_trace` from `structure_only` and never equates either
with training authenticity. The no-recomputation path reports
`verification_performed=false`. No human sign-off path is supported.

## Product and Entry Points

| Product line | Distribution | Python import | Product CLI | Status |
| --- | --- | --- | --- | --- |
| 1.0.2 | `sidinspector` | `sidinspector` | route-specific commands | Immutable historical release associated with the submitted TOIS snapshot; not a permanent TOIS revision constraint |
| 1.1.0 | `sidinspector` | `sidinspector` | route-specific commands | Published maintenance release |
| 1.1.1.dev0 | `sidinspector` | `sidinspector` | `sidscope` facade plus legacy commands | Frozen regression authority |
| 1.2.0.dev0 | `sidinspector` | `sidinspector` | registry-backed `sidscope` facade plus legacy commands | Sprint 1--4 development closed; public release not implied |
| 1.3.0.dev0 | `sidinspector` | `sidinspector` | facade plus lazy `sidscope.adapters` plugins | Adapter/native-trace ecosystem development closed; public release not implied |
| 1.4.0.dev0 | `sidinspector` | `sidinspector` | facade plus evidence bundle and registry commands | Immutable evidence-system development closed; public release not implied |
| 1.5.0.dev0 | `sidinspector` | `sidinspector` | facade plus profile, submission and generated-view commands | Conformance/submission ecosystem development closed locally; public release not implied |
| 1.6.0.dev0 | `sidinspector` | `sidinspector` | frozen candidate facade plus compatibility/migration verification | Compatibility, migration and external-adoption hardening closed locally; public release not implied |
| 1.7.0.dev0 | `sidinspector` | `sidinspector` and curated `sidscope` | previous facade plus `schema list` and two-stage `schema validate` | Contract and public-surface stabilization active; public release not implied |

The table records compatibility, not publication. GitHub `main` remains on
1.1.x, while 1.2--1.7 and the planned 2.0 contract are local-only development.
The frozen TOIS package selects software by an exact reviewed ref; a later
authorized revision may select a compatible 1.x ref, but never inherits local
2.x merely because its development version is newer.

No import or distribution rename is planned during 1.x. The facade validates
all eleven canonical 1.2 contracts and provides adapter preflight, trace
validation, deterministic evaluation, conformance-report verification, and
evidence-index packaging. Legacy route commands remain public and authoritative
during migration.

## Version-Axis Baseline

| Axis | Current value | Compatibility rule |
| --- | --- | --- |
| Product/package | `1.7.0.dev0` | PEP 440 development version; not a public 1.7.0 release. |
| Adapter SDK | `1.0.0` | Stable capability descriptor and lazy plugin API 1.0; SDK 0.1 descriptors remain accepted for historical replay. |
| Canonical schemas | Eleven registry entries from SourceIdentity v1 through EvidenceIndex v1, each at revision `1.0.0` | Registry-declared exact major and supported revision required. |
| Conformance profiles | governed `static_mapping_c0_c5`, `generator_g0_g5`, `overlay_g0_g5`, `release_local` at `1.0.0`; legacy `common.generator.v1` and five family profiles remain supported | Profile reports bind the exact catalog hash; legacy-only routes retain read-only authority until migration. |
| Evidence bundle | `sidscope.evidence_bundle.v1@1.0.0` | Immutable canonical JSON; SHA-256 object directory authoritative; SQLite and static views are derived. |
| Submission | `sidscope.evidence_submission.v1@1.0.0` and `sidscope.submission_check_report.v1@1.0.0` | Root-relative canonical package; unknown roles revisions bindings or claims fail closed. |
| Public schema catalog | 46 schema IDs across 28 bundled Draft 2020-12 resources | `sidscope schema validate` runs the selected JSON Schema before the owning Python semantic validator. |
| CLI result envelope | 19 result schema IDs in `cli_result.v1.schema.json` | Every CLI envelope requires recognized schema, pass/fail status, and status-consistent failure state; domain artifacts retain their own schema/status semantics. |

The executable matrix is
`docs/reproducibility/sidscope_1_6_compatibility_matrix.json`. Every axis has a
positive case and a typed negative. The matrix distinguishes frozen historical
replay, released historical replay, the 1.1.1 migration baseline, and the
pre-stable canonical development interval; development milestones are not
retroactively represented as public releases.

The canonical schema IDs are `sidscope.source_identity.v1`,
`sidscope.dataset_identity.v1`, `sidscope.sid_space_identity.v1`,
`sidscope.prepared_dataset.v1`, `sidscope.episode_selection.v1`,
`sidscope.run_identity.v1`, `sidscope.checkpoint_binding.v1`,
`sidscope.trace_envelope.v1`, `sidscope.diagnostic_report.v1`,
`sidscope.conformance_report.v1`, and `sidscope.evidence_index.v1`.

## Pre-2.0 Stabilization Boundary

The planned version sequence separates feature completion from the stable
compatibility declaration:

| Milestone | Compatibility purpose | Admission rule |
| --- | --- | --- |
| 1.5 | Add versioned conformance profiles, submission checking and generated registry views. | Additive development surface; legacy authorities remain available until parity passes. |
| 1.6 | Prove package/SDK/schema/profile/payload/bundle intervals, migrate or archive legacy authorities, and freeze candidate CLI/Python interfaces. | No unresolved breaking change, unowned wrapper or undocumented migration may advance to 2.0. |
| 1.7 | Unify public schema ownership and validation, validate every CLI result envelope, introduce the curated `sidscope` facade, enforce cross-module facade imports, and separate runtime/conformance/evidence-full release views. | The delta is additive; 1.6 historical replay, artifact hashes and `sidinspector` imports remain intact, while evidence-full preserves the prior reviewer surface. |
| 1.8--1.9 (reserved optional) | Hold capacity for explicitly approved additive or hardening slices discovered after 1.7. | No compatibility is implied until a version is activated with a scoped matrix delta, migration, rollback and tests; unused versions are skipped. |
| 2.0 | Declare the interfaces demonstrated by the final passing pre-2.0 1.x baseline stable. | Final release gates reverify the frozen compatibility surface; they do not complete missing migrations. |

If 1.6 hardening fails, the last passing 1.5 profile/CLI combination remains
the supported development baseline and 2.0 is deferred. Existing bundles,
historical evidence and published tags are never rewritten to manufacture
compatibility.

Every activated 1.8--1.9 minor release must preserve the previous passing 1.x
as a rollback point and rerun all still-applicable 1.6 hardening gates. Merely
reserving a version creates no supported package, SDK, schema, profile, payload
or bundle interval.

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

Adapter SDK `0.1.0-alpha` remains a supported legacy descriptor. SDK
`1.0.0` stabilizes `sidscope.adapter_capabilities.v1`, an SDK compatibility
interval, native payload schema binding, runtime requirements, and plugin API
1.0 under the `sidscope.adapters` entry-point group.
The distribution and import remain `sidinspector`; the product command is
`sidscope`. Legacy CLIs and evidence remain unchanged. The migration matrix
covers all six generator and nine static-mapping routes. RPG has exact
canonical fixture parity; other routes receive a typed regeneration disposition
and retain legacy status authority. An incomplete migration cannot promote an
adapter or rewrite historical evidence.

## Plugin and Native-Payload Compatibility

Plugin discovery is metadata-only; explicit preflight loads one selected
entry point. API mismatch, protocol mismatch, capability mismatch, payload
schema mismatch, and plugin load failure are typed. Core verification never
requires the producing plugin. Uninstalling a plugin is therefore a reversible
integration rollback, not a schema rollback.

The five payload schema majors are
`sidscope.trace_payload.autoregressive_prefix.v1`,
`sidscope.trace_payload.parallel_graph_token_set.v1`,
`sidscope.trace_payload.masked_diffusion.v1`,
`sidscope.trace_payload.latent_retry.v1`, and
`sidscope.trace_payload.decoder_overlay.v1`. Envelope compatibility does not
imply native-payload compatibility. Unknown family/schema pairs and unsupported
semantic claims fail closed. No 1.3 file is silently treated as an admitted
immutable bundle.

## EvidenceBundle and Registry Compatibility

EvidenceBundle v1 is additive to, and distinct from, EvidenceIndex v1. Bundle
admission requires exact revision `1.0.0`, a valid canonical content hash, a
complete acyclic provenance graph, false privacy-export flags, and supported
rank-censoring semantics. Restricted artifacts may be hash references and do
not need to be redistributed.

The SQLite registry is not a compatibility or identity axis. It may be deleted
and rebuilt from admitted objects, and its deterministic static export must
remain unchanged. A correction creates a new bundle with a supersession edge;
it never changes the old bundle. Comparison produces metric deltas only when
profile revision, dataset, target universe, evaluation cutoff, publication
depth, and rank semantics match. Otherwise it returns typed incompatibility.

## Profile and Submission Compatibility

DatasetProfileDescriptor v1 and ProfileConformanceReport v1 are additive to the
eleven canonical 1.2 contracts. They govern 1.5 admission and do not silently
reinterpret the older ConformanceReport v1 or 1.3 family-composition registry.
A report binds `sidscope.conformance_profile_catalog.v1` by content hash and
uses only its profile's gate order failure codes and derived status-label
policy.

EvidenceSubmission v1 binds root-relative canonical files by exact-byte SHA-256.
The checker accepts passing and registered partial/close profile decisions and
rejects failing decisions. It validates DatasetProfileDescriptor,
ProfileConformanceReport and EvidenceBundle through their public owners rather
than duplicating their semantics. Status and result indexes are deterministic
derived views; they are neither a schema authority nor an admission write API.

Rollback pins the prior profile/catalog and CLI combination and rebuilds the
views. Existing reports submissions bundles family profiles and legacy ledgers
remain immutable and independently addressable.
