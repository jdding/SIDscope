# SIDScope 1.2 to 2.0 Product Roadmap

<!-- SIDSCOPE:CURRENT:BEGIN -->
Local development: `1.7.0.dev0`; public GitHub remains 1.1.x; 1.8/1.9 inactive.
Current diagnostic admission and comparison require input-bound recomputation; declarations alone do not pass.
Unclosed SDLC requirements: F09.
Requirement snapshot: `48d593e1151cbacde9f62ac271e8b45f61847695b31846779679ab424bb3deb3`.
Historical route decisions (not newly recomputed training): dact_tiger=named_adapter; diffgrm_www2026=named_adapter; isd=close_named_adapter; latte_psid=named_adapter; llada_rec=named_adapter; rpg_kdd2025=named_adapter.
Historical route snapshot: `cb51983ca33506c4c00f1722eda8e5eb9eb452409ce026f9810a76fe1cf02a92`.
Independent user acceptance is not established by automated tests. No push, tag, public release or TOIS mutation is authorized.
<!-- SIDSCOPE:CURRENT:END -->

Status: approved development direction

Regression baseline: `1.1.1.dev0`; active development: `1.7.0.dev0`

Architecture authority: `SIDSCOPE_SYSTEM_ARCHITECTURE.md`

Current implementation diagram and code map are at the top of that document.
The numbered milestone sections below describe the staged plan, not proof of
today's acceptance. Current execution status is in `SIDSCOPE_NEXT_DEVELOPMENT_PLAN.md`
and the requirement ledger: N02-N08 engineering scope is verified, including the
bounded 100-episode N08 gate and N07 refresh diagnostics; Adapter SDK 1.0 and the
candidate surface are frozen. N01/F09 independent actual use remains the sole
certification blocker. N09/N10 are explicitly deferred.

Publication topology: GitHub `sidscope/main` remains on 1.1.x. Milestones
1.2--1.9 and the 2.0 target are developed only in the local `SIDScope-v2`
worktree until explicitly authorized for publication. The TOIS repository is
an independent frozen authority; a future revision may select a reviewed 1.x
software ref but does not inherit this local 2.x line.

## 1. Goal and Sequencing

By 2.0, SIDScope will be a stable, local-first conformance and observability
platform for Semantic-ID and generative recommender systems. It will not become
a training framework, model zoo or hosted service. Upstream methods stay
external; SIDScope owns the pipeline from adapter integration through immutable
evidence.

```text
1.1.1 regression authority
        -> 1.2 canonical contracts and CLI facade
        -> 1.3 adapter plugins and native trace families
        -> 1.4 immutable evidence and local registry
        -> 1.5 conformance/submission ecosystem
        -> 1.6 compatibility, migration and adoption hardening
        -> 1.7 contract and public-surface stabilization
        -> 1.8-1.9 reserved optional pre-2.0 development slots
        -> 2.0 stable public platform contract
```

Every milestone preserves the verified 1.1.1 adapters and passes the full CPU
package, deterministic archive and isolated-environment gates. New GPU evidence
is required only when a method, data, checkpoint or configuration identity
changes, not for shared-core refactoring.

### Architecture Sprint 0 implementation status

The 1.1.1 development line now contains the first executable transition
slice: a machine-readable architecture inventory, canonical hashing/version
rules, an enforced module-dependency matrix, the `sidscope` CLI facade, and
the `sidscope.source_identity.v1` model/schema/validator with positive,
typed-negative, and legacy-adapter parity tests. This starts 1.2 delivery but
does not declare 1.2 released or imply that the remaining canonical entities
already exist.

After this sprint is committed, implementation from 1.2 through 2.0 moves to
the dedicated `SIDScope-v2` worktree and `codex/sidscope-v2` branch. The
`SIDScope-v1.1` worktree remains the 1.1.x maintenance surface, and the frozen
TOIS repository remains an independent, non-merge target. This development
branch is local-only: a closed milestone or clean commit is not authorization
to push it to GitHub.

### Sprint 1 implementation status

Sprint 1 closes the registry and DatasetIdentity vertical slice on the
dedicated `SIDScope-v2` worktree. The bundled `sidscope.contract_registry.v1`
is now the discovery and CLI-dispatch authority for SourceIdentity and
DatasetIdentity. It binds owner, schema revision, compatibility, JSON Schema
2020-12 resource, canonical fixture, typed negative fixtures and dependencies,
and fails closed on unknown/cyclic/incompatible declarations.

`sidscope.dataset_identity.v1` implements complete split/catalog/target-universe
identity plus an explicit `legacy_partial` migration that never fabricates
missing legacy hashes. SID depth is deferred to Sprint 2's SIDSpaceIdentity.
Focused, full package, archive and isolated-install gates close the sprint; the
remaining 1.2 canonical entities stay planned.

### Sprint 2 implementation status

Sprint 2 closes SIDSpaceIdentity and PreparedDataset. SID structure,
vocabulary, offsets, special tokens, tokenizer/cache identity, collisions and
de-duplication are now a separate registered identity. PreparedDataset depends
on complete DatasetIdentity and SIDSpaceIdentity artifacts and binds normalized
splits, artifacts, catalog, target universe and privacy without absorbing
training, checkpoint or episode-selection concerns.

The RPG prepared bridge migrates with exact canonical fixture parity while
preserving parallel/unordered semantics. Incomplete DiffGRM and LLaDA legacy
prepared contracts fail with a typed regeneration requirement. Focused, full
package, archive and isolated-install gates close the sprint; EpisodeSelection
is the next 1.2 vertical slice.

### Sprint 3 and Sprint 4 implementation status

Sprint 3 closes EpisodeSelection, RunIdentity, CheckpointBinding, and
TraceEnvelope. The envelope binds a method-family-native payload by schema and
SHA instead of converting heterogeneous decoding into a false common ancestry.
Checkpoint state is typed as complete-resumable or inference-only; SIDScope
validates provenance but does not own training.

Sprint 4 closes DiagnosticReport, ConformanceReport, EvidenceIndex, Adapter SDK
`0.1.0-alpha`, and the shared CLI. The complete eleven-contract dependency DAG
is registered and validated. RPG supplies the canonical end-to-end fixture;
the fifteen-route migration matrix preserves every legacy authority and records
typed regeneration where canonical artifacts do not yet exist. Six shared
commands have a measured CPU baseline and a 20% review policy.

Together Sprints 1--4 close the planned 1.2 development scope. This is a
development closure, not a public tag or release declaration. Plugin discovery,
registered native payload families, immutable EvidenceBundle storage, and
SQLite projections remain assigned to 1.3 and 1.4.

### 1.3 implementation status

The 1.3 Adapter and Native-Trace Ecosystem is development-closed. Lazy
`importlib.metadata` discovery under `sidscope.adapters` does not import plugin
code until one named plugin is explicitly preflighted. SDK `1.0.0`
capabilities bind method family to one of five registered native payload
schemas while legacy SDK 0.1 descriptors remain accepted.

Autoregressive prefix, parallel graph/token-set, masked diffusion, latent
retry, and decoder-overlay payloads now have independent semantic validators,
hash-bound registries, positive fixtures, and typed negative fixtures. Shared
and family profiles compose deterministically. An external reference package
installs without core edits; isolated verification proves core payload
validation still works with no plugin installed. RecBole availability is
probed without import or core dependency.

This closes the 1.3 deliverables and exit gates without changing existing
named-adapter evidence. Immutable EvidenceBundle storage, SQLite projections,
admission, comparison, and supersession remain exclusively assigned to 1.4.

### 1.4 implementation status

The 1.4 Evidence Bundles, Registry and Comparison milestone is
development-closed. EvidenceBundle v1 binds profile, method family, dataset,
target universe, evaluation depth, provenance, result card, rank censoring,
privacy, and supersession under one canonical non-self-referential SHA-256.
Public bytes use an atomic content-addressed object layout; restricted assets
remain hash-only references.

Standard-library SQLite is a derived projection with add, list, show, compare,
supersede, import, export, quarantine, and rebuild. Deleting it and rebuilding
from immutable active and quarantined objects reproduces the deterministic
static view. Comparison emits metric deltas only when profile, dataset,
universe, cutoff, publication depth, and rank semantics match; unsupported
exact-rank claims fail closed.

Positive, supersession, incompatibility, privacy, provenance-cycle, and rank
fixtures close the CPU verifier. Six new command families have a measured CPU
baseline and the existing 20% review policy. No upstream training, adapter
status, historical EvidenceIndex, 1.1 evidence, or frozen TOIS artifact changes
as part of this milestone.

## 2. State Transition

### Historical starting state (1.1.1, before the local shared-contract work)

The 1.1.1 tree is a proven but route-oriented evidence package. Method-specific
CLIs and verifiers are authoritative, while common concepts are documented but
not uniformly registered or dispatched.

### Interim State

Versions 1.2 through the final active 1.x milestone run shared and legacy paths
side by side. Each adapter migrates independently after outcome, metric,
binding, hash and typed-failure parity. Compatibility wrappers are temporary,
owned and reversible. Version 1.7 is active as `1.7.0.dev0`; 1.8--1.9 remain
optional inactive slots. The SDLC hardening ledger now gates current readiness;
historical milestone closure does not discharge its open trust and user gates.

### Target State

At 2.0, external or built-in adapters emit registered contracts; a shared
evaluator and verifier produce profile-bound reports; immutable bundles are the
source of truth; SQLite and public indexes are rebuildable projections.

## 3. Migration-Wave Controls

| Wave | Release | Cutover unit | Coexistence rule | Validation evidence | Rollback | Exit or retirement trigger |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.1.1 | Current architecture and evidence baseline | All existing verifiers remain authoritative. | Full tests, resource verifier, archive smoke and G8. | Revert architecture-only change without touching frozen evidence. | Schema, verifier and evidence inventory is complete. |
| 1 | 1.2 | One canonical entity or one CLI command at a time | Shared facade may call legacy verifier; legacy CLI remains public. | Exact positive/negative outcome and report parity. | Route command back to legacy implementation. | All public fixtures pass through the facade; every wrapper has an owner. |
| 2 | 1.3 | One adapter and trace family at a time | Built-in and plugin adapter forms may coexist. | Serialization round-trip, semantic fixture and isolated import tests. | Disable plugin descriptor and retain built-in adapter. | External reference plugin passes without core edits. |
| 3 | 1.4 | One evidence-bundle family at a time | Existing evidence files remain authoritative until bundled and verified. | Hash parity, provenance DAG, registry rebuild and privacy scan. | Discard derived SQLite index and rebuild from immutable bundles. | All active evidence types have deterministic bundles and registry entries. |
| 4 | 1.5 | One conformance profile at a time | Legacy status ledger stays read-only while generated view is compared. | Profile replay, submission checker and generated-ledger parity. | Keep previous profile version active; reject new admissions. | All active status labels derive from versioned reports. |
| 5 | 1.6 | One supported compatibility interval or legacy route at a time | 1.5 profiles and commands stay active while migration, external-plugin and cross-family parity are hardened. | Multi-version CI, migration replay, external onboarding, cross-family comparison and wrapper-owner audit. | Pin the last passing 1.5 profile/CLI combination and defer 2.0; immutable bundles are never rewritten. | Every supported interval is tested and every wrapper is retired or explicitly archived. |
| 6 | 1.7 | Contract, public-surface and release-view stabilization | The passing 1.6 surface, producer identities and artifacts remain valid while schema/CLI/Python authority and release audiences become explicit. | Unified schema catalog, ordered structural/semantic validation, CLI result envelope, curated `sidscope` facade, strict runtime/conformance/evidence-full profiles, stronger architecture tests and 1.6 replay. | Pin 1.6 or publish only evidence-full; immutable evidence is not rewritten. | Every public schema/result/API entry and release profile is inventoried and fail-closed; complete release gates pass. |
| 7 | 1.8--1.9 (optional) | One approved additive or hardening workstream per activated minor release | The last passing 1.x remains supported while the new slice proves parity; unused reserved versions are skipped. | A scoped design record, positive/negative tests, compatibility delta, full release gates and a repeat of all still-applicable hardening checks. | Pin the previous passing 1.x release and deactivate only the new slice. | Activated scope closes with no unowned migration or compatibility debt; the final active 1.x repeats the complete pre-2.0 hardening suite. |
| 7 | 2.0 | Stable public interfaces | Only interfaces proven by the final passing pre-2.0 1.x baseline enter the stable support contract; historical CLIs remain replay-only where documented. | Complete architecture criteria, compatibility matrix and public release gates. | Pin the final passing 1.x release candidate; immutable bundles require no rollback mutation. | Stable public contract is declared without carrying an unresolved migration backlog. |

No wave moves two independently risky boundaries at once. A schema migration,
verifier migration and public status promotion are separate cutover units.

## 4. Release Milestones

### 1.1.1: Freeze the Regression Authority

Purpose: finish the current maintenance line and establish the evidence against
which shared-core changes are judged.

Deliverables:

- publish the system architecture, version roadmap and accepted ADRs;
- complete any already-authorized evidence intake and release regression;
- inventory every schema ID, producer, verifier, profile and evidence edge;
- retain current C0--C5 and G0--G5 positive and typed-negative authorities;
- mark source-watch-only history as non-adapter state;
- keep license status independent from execution and conformance status.

Exit gates:

- clean worktree and version-consistent metadata;
- full tests, resource verifier, deterministic archive smoke and isolated G8;
- every named adapter has positive and typed-negative regression coverage;
- schema/verifier inventory has no unowned active entry;
- frozen TOIS submission remains unchanged.

### 1.2.0: Canonical Contracts and CLI Facade

Purpose: establish the stable vocabulary and entry points used by later layers.

Deliverables:

- canonical models for source, dataset, SID space, prepared data, selection,
  run, checkpoint, trace envelope, diagnostics, conformance and evidence index;
- JSON Schema 2020-12 registry with owner, version, compatibility, canonical
  fixture and negative-fixture metadata;
- Adapter SDK alpha for capabilities and artifact producers;
- `sidscope` CLI for adapter preflight, contract/trace validation, evaluation,
  verification and evidence packaging;
- compatibility preservation for the `sidinspector` import and current CLIs;
- explicit migrations or regeneration requirements for supported 1.1 schemas;
- architecture import tests that reject cycles and illegal dependency direction;
- measured CPU baseline for each shared command.

Exit gates:

- every current public fixture verifies through legacy and shared paths with
  equivalent status, metrics, bindings and typed failures;
- registry validation rejects unknown, cyclic and incompatible dependencies;
- core import does not load another method's optional runtime;
- no approved command has an unreviewed CPU regression above 20%;
- clean Python 3.9+ install passes the complete package gate.

Rollback: the shared CLI dispatches the affected route back to its frozen
legacy verifier; no evidence bundle is rewritten.

### 1.3.0: Adapter and Native-Trace Ecosystem

Purpose: allow integrations without editing the trusted core.

Deliverables:

- `importlib.metadata` plugin discovery under `sidscope.adapters`;
- versioned adapter capability descriptor;
- registered payload contracts for autoregressive, parallel graph/token-set,
  masked/diffusion, latent-retry and decoder-overlay observation;
- adapter scaffolding and a reference plugin outside core module paths;
- reusable fixture harnesses for binding, privacy, ancestry, censoring,
  resolution, termination and capability failures;
- profile composition over shared gates;
- optional RecBole backend proof without making RecBole a core dependency.

Exit gates:

- the external reference plugin installs and passes without core edits;
- each trace family round-trips without semantic flattening;
- plugin incompatibility is a typed error, not import-time core failure;
- core bundle verification succeeds when the producing plugin is absent;
- named-adapter regressions remain unchanged unless an explicit migration is
  admitted.

Rollback: disable the plugin descriptor and use the built-in or legacy adapter;
core contracts and already produced bundles remain valid.

### 1.4.0: Evidence Bundles, Registry and Comparison

Purpose: turn passing reports into an authoritative evidence system.

Deliverables:

- content-addressed `EvidenceBundle` and deterministic package builder;
- SHA-256 object layout plus standard-library SQLite projection;
- registry add, list, show, compare, supersede, import, export and rebuild;
- provenance graph across source, data, SID, run, checkpoint, trace,
  diagnostics and conformance;
- standard result cards with overall/slice metrics, typed failure decomposition,
  compute and rank censoring;
- comparison that rejects incompatible profiles, target universes, cutoffs,
  publication depths and unsupported exact-rank claims;
- privacy and forbidden-content scanning at bundle admission and export.

Exit gates:

- a fresh CPU environment verifies a bundle and rebuilds its registry record;
- deleting the SQLite index and rebuilding produces the same static export;
- a correction creates a new bundle with a supersession edge;
- restricted assets are not needed beyond declared hashes and counts;
- compare reports distinguish method differences from contract incompatibility.

Rollback: remove and rebuild the derived index from immutable objects. A bad
bundle is quarantined and superseded, never edited in place.

### 1.5.0: Conformance and Submission Ecosystem

Purpose: make profiles and third-party evidence submissions governable.

Deliverables:

- versioned static-mapping, generator, overlay and release profiles on the
  shared verifier engine;
- dataset/profile descriptors binding split, catalog, target universe, cutoff,
  publication depth, slices and privacy policy;
- submission checker for structure, completeness, compatibility and claims;
- status and result indexes generated from registry data;
- contributor guide, profile review, deprecation, security and privacy process;
- CI matrices for supported Python, schemas, profiles, plugins, archives and
  backward compatibility;
- explicit code ownership for contracts, profiles, adapters and releases.

Exit gates:

- a third party can complete one adapter onboarding from public documentation
  without project-specific verifier edits;
- all status labels admitted to the 1.5 generated indexes derive from
  conformance reports; legacy-only rows remain visibly outside that authority;
- profiles have owners, semantic versions, fixtures and migration policy;
- generated registry views match the read-only legacy ledger for every route
  migrated in 1.5; complete 1.1.1 route migration or immutable archival remains
  the explicit 1.6 hardening gate;
- submission checker rejects every registered negative package.

Rollback: keep the prior profile active and block admissions under the new
profile until corrected; existing bundle identities remain unchanged.

### 1.6.0: Compatibility, Migration and Adoption Hardening

Implementation status: development-closed on `1.6.0.dev0`. The executable
matrix, migration records/status projection, candidate API inventory,
cross-family fixtures, isolated external-plugin replay, migration guide, CI
gates and release rehearsal are present. This does not create a public tag.

Purpose: prove that the 1.5 product surface can support external adoption and
historical evidence before SIDScope makes a stable 2.0 compatibility promise.
This is a hardening and migration release, not a new product-layer expansion.

Deliverables:

- a tested compatibility matrix spanning supported 1.x package, SDK, schema,
  profile, payload and EvidenceBundle intervals;
- immutable migration records or replay paths for every active 1.1.1 adapter
  status and evidence family;
- registry/profile-derived status and result views with legacy-ledger parity;
- at least one independently packaged external adapter onboarding completed
  from public documentation without core edits;
- at least one compatible-profile comparison spanning generator families;
- a frozen candidate `sidscope` CLI and Python API surface with documented
  deprecations, ownership and retirement state for every compatibility wrapper;
- multi-version CI and release rehearsal across supported Python versions,
  schemas, profiles, plugins, archives and fresh environments;
- a complete 1.x-to-2.0 migration guide and release-candidate checklist.

Exit gates:

- every supported compatibility interval has positive and typed-negative CI;
- every active adapter status is replayable from a versioned report and
  hash-bound bundle, or has an immutable historical migration record;
- external plugin onboarding and cross-family comparison pass independently;
- no compatibility wrapper lacks an owner, support interval and retirement or
  archived-history decision;
- deleting derived state and replaying the supported evidence set reproduces
  the same public indexes;
- the proposed 2.0 CLI, Python API, SDK, schemas and profiles have no unresolved
  breaking change or undocumented migration action.

Rollback: retain the last passing 1.5 profile/CLI combination, quarantine only
new invalid bundles, and defer 2.0. Existing immutable objects, historical
verifiers and released tags are never mutated to force a hardening gate.

### 1.7.0: Contract and Public-Surface Stabilization

Implementation status: code and local release verification complete on
`1.7.0.dev0`; no tag or public release is implied.

Purpose: close the contract-authority, candidate-API and undifferentiated
release-surface risks found by the
post-1.6 architecture review without changing method semantics or historical
evidence. The slice adds a catalog for every bundled public schema ID, ordered
Draft 2020-12 then Python semantic validation, one validated CLI result
envelope, a curated `sidscope` Python facade, centralized semantic producer
versions, relative/private import fitness checks, and three additive release
profiles under the same `1.7.0.dev0` product version.

Admission requires the deterministic 1.7 public-surface and release-profile
records, positive and
typed-negative tests, exact 1.6 historical replay, full tests, resource
verification, all profile smokes and runtime G8. The change is additive: no 1.6 command,
historical symbol, schema ID/revision or artifact byte may be removed or
rewritten.

Rollback: pin 1.6 and remove only additive 1.7 catalog/facade/command code. Do
not modify immutable evidence, adapter status, released tags or frozen TOIS
assets.

### 1.8.0--1.9.0: Reserved Optional Pre-2.0 Development Slots

Purpose: preserve room for evidence-backed additive development discovered
after 1.7 without hiding it inside the 2.0 release candidate. These are version
reservations, not pre-approved features or a requirement to publish every minor
version.

Activation rules:

- each minor release is activated only by an explicit user-approved scope and
  synchronized roadmap/compatibility update;
- the scope names one primary additive or hardening workstream, its owner,
  compatibility impact, fixtures, migration, rollback and measurable exit
  gates;
- unused version numbers may be skipped; placeholder versions never receive an
  empty tag or synthetic release record;
- new work must remain inside SIDScope's six owned layers and cannot absorb
  upstream model/training implementation;
- the previous passing 1.x surface stays installable and its immutable bundles
  remain valid while the new slice is tested;
- the final active 1.x milestone, whether 1.7, 1.8 or 1.9, reruns the full
  compatibility, migration, external-adoption, wrapper and release hardening
  gates before 2.0.

Possible future work is intentionally unnamed until evidence justifies it.
Hosted services, dashboards and speculative method expansion are not implicitly
authorized by reserving these versions.

Rollback: deactivate the new additive slice and pin the previous passing 1.x
release. Do not mutate earlier schemas, profiles, bundles, tags or migration
records to preserve the appearance of a sequential release.

### 2.0.0: Stable Conformance and Observability Platform

Purpose: declare the architecture and extension contract stable for external
adoption.

2.0 is a stability declaration and final release certification over the final
passing pre-2.0 1.x baseline, which is at least 1.6 and may be a deliberately
activated 1.7, 1.8 or 1.9. It is not the place to finish unowned migrations,
introduce a new product subsystem or discover the first external-adoption path.

Required product surface:

- stable Adapter SDK and plugin lifecycle;
- stable canonical contracts and schema registry;
- method-faithful trace protocol with registered native payload families;
- deterministic evaluator and typed diagnostic decomposition;
- versioned profiles and independent submission checker;
- immutable evidence bundles, rebuildable local registry and static public
  index;
- unified CLI and documented Python API;
- compatibility and migration guarantees for supported 1.x evidence;
- deterministic release archive and fresh-environment verification.

Release gates:

1. every criterion in `SIDSCOPE_SYSTEM_ARCHITECTURE.md` section 13 passes;
2. the complete 1.1.1 adapter matrix remains verifiable or has immutable
   migration records;
3. at least one adapter is distributed and verified as an external plugin;
4. at least one comparison spans generator families under a compatible profile;
5. all public index rows derive from hash-bound bundles and verifier reports;
6. security, privacy, license-marker, compatibility and deprecation policies
   are documented and tested;
7. full tests, resource verifier, archive smoke, isolated G8 and public URL
   smoke pass on the final tag;
8. no active compatibility wrapper lacks an owner and retirement state.

## 5. Workstream Ownership

| Workstream | Owner role | Owns | Does not own |
| --- | --- | --- | --- |
| Adapter SDK | Adapter-platform maintainer | upstream boundary, capabilities, exporters and fixtures | model implementation or training algorithm |
| Contracts | Core maintainer | canonical entities, identity, hashes and schema compatibility | upstream storage layout |
| Trace Protocol | Trace-profile maintainer | common envelope and native family payloads | invented unavailable telemetry |
| Evaluation | Diagnostic maintainer | deterministic metrics, resolution, failure and compute decomposition | adapter promotion |
| Conformance | Profile maintainer | profiles, verifiers, typed failures and status transitions | manually asserted results |
| Evidence | Release/evidence maintainer | bundles, registry, comparison and static publication | redistribution of excluded assets |
| Access and governance | Core/release maintainers | CLI/API, privacy, compatibility and release policy | a second data model |

One person may currently hold several roles, but every contract and release
decision names the role responsible. Repository ownership rules cover core
contracts, schemas, profiles, adapters, evidence and release manifests in
`CODE_OWNERSHIP.md` and `.github/CODEOWNERS`.

## 6. Success Metrics

| Metric | 2.0 target |
| --- | --- |
| Core changes required for a conforming external adapter | Zero files under core module paths |
| Registered negative fixtures returning their typed failure | 100% |
| Active registry status rows derived from bundles/reports | 100% |
| Supported 1.x evidence with parity or migration record | 100% |
| Deterministic rebuild equality | Byte-identical bundle/index/archive for identical inputs |
| Core verification dependency | CPU-only; no upstream method runtime imported |
| Provenance completeness | Every required edge hash-resolved and cycle-free |
| Temporary compatibility ownership | 100% have owner and retirement/archive state |
| Performance regression | No unapproved shared-command regression above 20% from the 1.2 baseline |

## 7. Prioritization Rule

Before 2.0, work is ordered as follows:

1. compatibility, privacy or evidence-integrity defects;
2. shared contracts and verifier primitives needed by multiple adapters;
3. external adapter usability and missing native trace families;
4. immutable evidence and comparison workflow;
5. additional named methods only when they exercise a missing family or expose
   a concrete contract gap;
6. dashboards and hosted services only after 2.0 and a separate demand-backed
   architecture decision.

This keeps model-count growth from displacing the system engineering that
defines SIDScope's product position.
