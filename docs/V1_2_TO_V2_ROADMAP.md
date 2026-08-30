# SIDScope 1.2 to 2.0 Product Roadmap

Status: approved development direction

Baseline: `1.1.1.dev0`

Architecture authority: `SIDSCOPE_SYSTEM_ARCHITECTURE.md`

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
        -> 2.0 stable public platform contract
```

Every milestone preserves the verified 1.1.1 adapters and passes the full CPU
package, deterministic archive and isolated-environment gates. New GPU evidence
is required only when a method, data, checkpoint or configuration identity
changes, not for shared-core refactoring.

## 2. State Transition

### Current State

The 1.1.1 tree is a proven but route-oriented evidence package. Method-specific
CLIs and verifiers are authoritative, while common concepts are documented but
not uniformly registered or dispatched.

### Interim State

Versions 1.2 through 1.5 run shared and legacy paths side by side. Each adapter
migrates independently after outcome, metric, binding, hash and typed-failure
parity. Compatibility wrappers are temporary, owned and reversible.

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
| 5 | 2.0 | Stable public interfaces | Historical CLIs remain replay-only where documented. | Complete architecture criteria, compatibility matrix and public release gates. | Pin latest 1.x release; immutable bundles require no rollback mutation. | Compatibility wrappers retire or become explicitly archived history. |

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
- all active status labels derive from conformance reports;
- profiles have owners, semantic versions, fixtures and migration policy;
- generated registry views match the read-only legacy ledger before it retires;
- submission checker rejects every registered negative package.

Rollback: keep the prior profile active and block admissions under the new
profile until corrected; existing bundle identities remain unchanged.

### 2.0.0: Stable Conformance and Observability Platform

Purpose: declare the architecture and extension contract stable for external
adoption.

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
decision names the role responsible. Before 1.2, repository ownership rules
must cover core contracts, schemas, profiles and release manifests.

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
