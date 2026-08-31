# SIDScope Changelog

Status: clean SIDScope official-repository changelog
Last updated: 2026-08-31

This changelog records reviewer-package changes for the standalone SIDScope
repository at `https://github.com/jdding/sidscope`. The earlier SIDInspector
repository remains reserved for the CIKM V0 surface and is not a SIDScope
release surface.
The public repository is the reviewer-visible and post-acceptance open source
package surface only; it is not the private project workspace and must not
include paper drafts, local provenance, AutoDL payloads, or large caches.

## SIDScope v1.7.0.dev0: contract and public-surface stabilization

- Added a unified catalog for all 45 public schema IDs across 27 bundled Draft
  2020-12 resources, with one owning module and Python semantic validator per
  schema.
- Added `sidscope schema list` and `sidscope schema validate`; validation is
  explicitly two-stage, so structurally permissive native-payload schemas
  cannot bypass method-specific semantic checks.
- Added one shared machine-readable CLI result envelope and fail-closed runtime
  validation for all 19 public CLI result schema IDs. Domain artifacts emitted
  by commands retain and validate their own schema/status semantics.
- Added a curated `sidscope` Python facade for new integrations while retaining
  the `sidinspector` distribution/import as historical compatibility surface.
- Centralized semantic producer versions independently from the product package
  version; unchanged 1.2 contract/evaluation/evidence bytes remain unchanged.
- Strengthened architecture fitness tests to resolve relative imports and reject
  direct cross-module implementation imports. Added ADR-0013 and deterministic
  1.7 stabilization evidence. No method, training runtime, service, tag, public
  release, or frozen TOIS artifact is added or changed.
- Added three additive 1.7 release profiles without changing the product
  version: a default installable `runtime`, an adapter-facing `conformance`, and
  the complete `evidence-full` audit surface. Each deterministic archive embeds
  a hash-bound profile receipt; smoke and G8 verify the selected profile, and
  the three large trained traces remain available only in `evidence-full`.

## SIDScope v1.6.0.dev0: compatibility, migration and adoption hardening

- Added an executable six-axis compatibility matrix for package, Adapter SDK,
  canonical schemas, profiles, native payloads, and EvidenceBundle v1, with a
  positive and typed-negative check for every axis.
- Bound all fifteen active 1.1.1 generator/static routes to immutable authority
  and verifier hashes. RPG retains canonical replay parity; routes missing
  canonical surfaces remain honest historical records with an explicit
  regeneration action rather than fabricated migration fields.
- Added a deterministic legacy status projection and verified byte-identical
  rebuild. Existing 1.5 submission status/result indexes remain report- and
  bundle-derived; historical records are not promoted into synthetic results.
- Replayed the separately packaged reference adapter from public onboarding
  documentation in an isolated CPU environment and verified zero core-file
  changes.
- Added compatible-profile comparison fixtures spanning parallel graph/token
  set and masked diffusion families, while preserving dataset, target-universe,
  cutoff, publication-depth, and rank-semantics identity.
- Froze the candidate Python exports and CLI leaf commands and assigned every
  legacy compatibility wrapper an owner, support interval, and archive decision.
- Added the 1.x-to-2.0 migration guide, ADR-0012, multi-version CI hardening
  gates, and release rehearsal. This development closure creates no tag or
  public-release claim.

## SIDScope v1.5.0.dev0: conformance and submission ecosystem

- Added a versioned shared profile catalog for static-mapping C0--C5,
  generator G0--G5, decoder-overlay G0--G5 and local-release gates, with owners,
  semantic revisions, fixtures, migration/deprecation policy and derived status
  labels.
- Added DatasetProfileDescriptor v1 and ProfileConformanceReport v1 to bind
  split, catalog, target universe, evaluation depth, slices, privacy, artifacts
  and ordered typed gate outcomes.
- Added a root-contained EvidenceSubmission v1 checker that validates
  structure, completeness, compatibility, claims and privacy without executing
  upstream code or plugins.
- Added deterministic status and result indexes derived from passing reports
  and immutable EvidenceBundles, plus a read-only legacy parity interface.
- Added public adapter-onboarding, profile-governance, security/privacy and code
  ownership documentation; CI now spans supported Python versions, schemas,
  profiles, plugins, backward compatibility and archives.
- Kept complete 1.1.1 route replay/archival and external adoption hardening in
  1.6. Existing bundles, legacy ledgers, adapter evidence and frozen TOIS assets
  remain unchanged.

## SIDScope v1.4.0.dev0: immutable evidence system

- Added exact EvidenceBundle v1 validation with canonical non-self-referential
  hashes, complete provenance DAGs, result cards, censoring, privacy, and
  hash-only restricted-asset references.
- Added atomic SHA-256 bundle/object storage. Immutable JSON objects are the
  authority; corrections create new objects with explicit supersession edges.
- Added a standard-library SQLite projection with add/list/show, deterministic
  static export, import, rebuild, quarantine, and deletion/rebuild parity.
- Added compatibility-aware comparison that refuses metric deltas across
  profile, dataset, target-universe, cutoff, publication-depth, or rank-semantic
  mismatches and rejects unsupported exact-rank claims.
- Added bundle and registry CLI commands, positive and typed-negative fixtures,
  ADR-0009, architecture inventory integration, and a CPU-only closure verifier.
- Split the post-1.5 transition into a dedicated 1.6 compatibility, migration
  and external-adoption hardening milestone before the 2.0 stability
  declaration; recorded the boundary and rollback policy in ADR-0010.
- Reserved optional 1.7--1.9 minor versions for later explicitly scoped work;
  unused versions may be skipped and the final active 1.x must rerun the full
  pre-2.0 hardening suite.
- Kept EvidenceIndex v1, route-specific evidence, adapter statuses, upstream
  training, and all frozen TOIS assets unchanged.

## SIDScope v1.3.0.dev0: adapter plugins and native trace families

- Added lazy `importlib.metadata` discovery under `sidscope.adapters`; listing
  does not load plugin code and explicit preflight converts load, API,
  capability, and payload incompatibilities into typed failures.
- Added SDK `0.2.0-alpha` and `sidscope.adapter_capabilities.v1` with exact
  method-family/payload-schema binding while preserving SDK 0.1 descriptor
  validation.
- Registered independent autoregressive-prefix, parallel-graph/token-set,
  masked-diffusion, latent-retry, and decoder-overlay payload contracts with
  semantic validators and hash-bound registry resources.
- Added composable common/family conformance profiles, five positive fixtures,
  and seven typed negative fixtures covering ancestry, privacy, termination,
  resolution, censoring, capability, and binding.
- Added a separately packaged reference plugin, a no-import RecBole boundary
  probe, ecosystem CLI commands, ADR-0008, and an isolated installation verifier.
- Kept named-adapter evidence unchanged and deferred immutable EvidenceBundle,
  SQLite projection, admission, comparison, and supersession to 1.4.

## SIDScope v1.2.0.dev0: Sprint 3/4 execution, reports, SDK alpha, and CLI closure

- Added EpisodeSelection, RunIdentity, CheckpointBinding, and TraceEnvelope v1
  with ordered selection, complete/inference-only state typing, common bounded
  observations, and independent native-payload schema/hash binding.
- Added deterministic DiagnosticReport, ConformanceReport, and EvidenceIndex v1
  with metric recomputation, failure decomposition, compute, censoring, gate
  ordering, privacy, dependency-DAG, and cycle validation.
- Added Adapter SDK `0.1.0-alpha` capability declarations and registry-enforced
  producer harness without plugin discovery or upstream runtime imports.
- Closed shared `sidscope` adapter preflight, contract/trace validation,
  evaluation, conformance verification, and evidence-index packaging commands.
- Added a twenty-file canonical pipeline fixture with eight typed failures,
  complete fifteen-route migration dispositions, a measured six-command CPU
  baseline, ADR-0007, and integrated package/CI release gates.
- Kept method training, native trace payloads, plugin discovery, immutable
  EvidenceBundle storage, and SQLite projection outside the 1.2 boundary.

## SIDScope v1.2.0.dev0: Sprint 2 SIDSpaceIdentity and PreparedDataset

- Added `sidscope.sid_space_identity.v1` for tuple structure, hierarchy,
  codebooks, offsets, special tokens, tokenizer/cache identity, collisions, and
  de-duplication without importing adapter runtimes.
- Added `sidscope.prepared_dataset.v1` with exact DatasetIdentity and
  SIDSpaceIdentity dependencies, normalized split/artifact bindings,
  train-only catalog/target-universe integrity, and privacy enforcement.
- Added deterministic RPG bridge migration with exact fixture parity and
  explicit regeneration-required failures for incomplete legacy DiffGRM and
  LLaDA prepared artifacts.
- Registered both contracts, added generic CLI dispatch, cross-binding and
  typed-negative verification, ADR-0006, architecture inventory integration,
  and focused/full release gates.

## SIDScope v1.2.0.dev0: Sprint 1 contract registry and DatasetIdentity

- Added the bundled `sidscope.contract_registry.v1` authority with owner,
  schema/revision compatibility, JSON Schema 2020-12 resource, canonical and
  typed-negative fixtures, dependencies, and generic CLI dispatch.
- Added `sidscope contract list`, `show`, and registry-backed `validate` with
  typed rejection of unknown types, unknown/cyclic dependencies, unsupported
  revisions, resource drift, and invalid contract artifacts.
- Added `sidscope.dataset_identity.v1` for dataset/category/profile, ordered
  split identities, catalog, target universe, privacy identity, and canonical
  hashing. Full identities cannot omit bindings or expose source item IDs.
- Added honest `legacy_partial` projection across existing adapter manifests;
  missing split/universe bindings are enumerated and `sid_depth` is deferred to
  SIDSpaceIdentity rather than silently moved into DatasetIdentity.
- Added registry/dataset fixtures, focused tests, a dedicated registry verifier,
  architecture inventory integration, ADR-0005, and Python 3.9/3.12 CPU CI.

## SIDScope v1.1.1.dev0: Architecture Sprint 0 and SourceIdentity slice

- Added version and compatibility policies, a reusable GitHub Release
  template, canonical hashing/version ADR, module-boundary ADR, and an
  executable dependency matrix.
- Added a deterministic machine inventory of schema IDs, producers,
  verifiers, profiles, adapter ownership, and evidence edges.
- Added `sidscope.source_identity.v1` as the first canonical vertical slice:
  JSON Schema, Python model, fail-closed validator, canonical content hash,
  positive/typed-negative fixtures, and legacy adapter-manifest parity.
- Added the stable `sidscope contract validate` CLI facade while retaining
  the `sidinspector` import and all legacy method-specific CLIs.
- Integrated architecture inventory and release-metadata checks into the CPU
  resource-package gate. This is transition infrastructure, not a 1.2 release.

## SIDScope v1.1.1.dev0: approve the 2.0 system architecture

- Adopted the product position "conformance and observability for Semantic-ID
  and generative recommender systems" while retaining upstream method,
  training, checkpoint production and serving as external responsibilities.
- Defined one six-layer responsibility chain: Integration, Contract,
  Observation, Evaluation, Conformance and Evidence.
- Selected a local-first modular monolith with external adapter plugins,
  file-first interchange, immutable content-addressed bundles, a rebuildable
  SQLite registry projection and deterministic static public indexes.
- Rejected both continued route-specific script growth and a premature hosted
  service topology as the post-1.1.1 target.
- Added current/interim/target states, migration waves with rollback and
  retirement gates, quality fitness functions, ownership, failure modes and
  measurable 2.0 acceptance criteria.
- Added accepted ADRs for the product boundary and runtime topology. These
  documents guide future releases and do not claim that planned 1.2--2.0
  interfaces already exist.

## SIDScope v1.1.1.dev0: DiffGRM VG trained closure and G0 license policy

- Accepted the frozen-VG 10,000-step DiffGRM checkpoint, one-per-bucket native
  v2 smoke, typed `unknown_parent_beam` failure, and external 250-episode
  balanced diagnostic through the unchanged independent real-bundle verifier.
- Added compact, non-redistributing evidence with checkpoint/training/config/
  SID-cache hashes, exact five-bucket counts, metrics, rank censoring,
  resolution, duplication, invalidity, and compute accounting.
- Promoted the frozen VG configuration to `named_adapter`; its OPQ4 tokenizer
  remains an explicit second factor and does not inherit RPG OPQ32 identity.
- Defined license state as metadata and a redistribution boundary rather than
  an experiment or evidence-delivery gate. `NOASSERTION` no longer fails G0 by
  itself; missing immutable identity, assets, round-trip, checkpoint, or real
  trace remains independently fail-closed.
- Reran the DACT/TIGER Tools primary on 500 targets with beam width 50 in both
  constrained and unconstrained modes. All 25,000 rows per mode now retain
  ordered prefixes, parent ancestry, and step log-probabilities; historical
  Recall@20 and invalid-path accounting reproduce exactly.
- Added compact hashes/counts/metrics for the external DACT traces and promoted
  the released Tools configuration to `named_adapter` without redistributing
  upstream source, checkpoint, mappings, splits, or full trace rows.

## SIDScope v1.1.1.dev0: upstream tokenizer license clarifications

- Recorded direct 2026-08-29 author clarifications for DIGER, LETTER, and
  ReSOT without publishing private correspondence.
- DIGER's author identifies the code as MIT and permits research use of the
  Hugging Face artifacts under the same terms; the repository LICENSE file is
  still pending.
- LETTER's author permits SIDScope research use of the code, datasets, and SID
  indexes with citation and acknowledgment of the CIKM 2024 paper; a
  repository license is planned.
- ReSOT's author permits the released code, datasets, checkpoints, and SID
  indexes for noncommercial academic research with citation of the KDD 2026
  paper.
- Kept `no_license_detected` and the existing non-redistribution policies until
  explicit repository license files or redistribution terms are published.
- Left the immutable TOIS submission and its `v1.0.2` evidence unchanged;
  these papers become candidates for an explicitly authorized future revision.

## SIDScope v1.1.1.dev0: formal adapter coverage cleanup

- Removed the code-less ChronoSID source-watch row from the formal generator
  adapter ledger. Literature-only candidates without official source are not
  represented as adapters or product states.

## SIDScope v1.1.1.dev0: DiffGRM external trained-trace verification

- Added `sidscope.diffgrm_masked_trace_bundle.v2` checkpoint, training, source,
  configuration, and SID-cache bindings while retaining schema-v1 fixture
  compatibility.
- Added a fail-closed three-file DiffGRM verifier that is independent of the
  source/license audit and reports canonical hashes, five-bucket metrics, rank
  censoring, resolution, duplication, and compute summaries.
- Added positive and typed negative tests for prepared binding, native parent
  ancestry, and canonical configuration hashes.

## SIDScope v1.1.1.dev0: DiffGRM staged masked/diffusion adapter

- Selected the The Web Conference 2026 DiffGRM route as the
  publication-prioritized masked/diffusion family and bound its DOI, official
  repository, immutable revision, and source hashes.
- Added dataset-neutral prepared-data and explicit ordered episode-selection
  contracts, strict four-position OPQ4 identity checks, and typed rejection of
  the incompatible RPG 32-position cache.
- Added a native masked trace contract for forward noising, adaptive
  denoising, real beam ancestry, retained/pruned candidates, raw pre-filter
  tuples, collision-aware exact resolution, compute counts, and right-censored
  target rank.
- Added positive and ten expected-failure fixtures, a non-importing staged
  source preflight, verifier CLI, and focused tests.
- Kept G0, upstream execution, GPU work, redistribution, and named-adapter
  promotion closed until explicit author code permission is recorded; no
  upstream code or assets are included.

## SIDScope v1.1.1.dev0: RPG dataset-neutral bridge

- Added hash-bound `sidscope.rpg_prepared_dataset.v1` and explicit
  `sidscope.rpg_episode_selection.v1` contracts with no first-N fallback.
- Added an upstream-compatible prepared loader and resumable training/export
  surface that retains RPG parallel unordered token-set graph semantics.
- Added dataset-neutral `sidscope.rpg_trained_trace_bundle.v2` verification and
  `sidscope.rpg_downstream_handoff.v1` evaluator-neutral episode rows.
- Added positive and typed duplicate-selection failure fixtures. A complete
  one-epoch CPU runner/export/verifier smoke passes, and the existing trained
  Beauty schema-v1 public bundle remains PASS.
- Closed the Fudan epoch-boundary audit gap with atomic
  `sidscope.rpg_resumable_state.v2` checkpoints that embed cumulative epoch
  records plus a hash-bound `sidscope.rpg_epoch_ledger.v1` sidecar. A real CPU
  epoch 1 to epoch 2 resume regression passes after removing the first
  invocation's final manifest; the resumed manifest preserves the continuous
  epoch, global-step, and model-state-hash chain.
- Separated the frozen evaluation cutoff from diagnostic rank publication in
  RPG v2 traces. The optional `sidscope.rpg_rank_depth_diagnostic.v1` extension
  preserves Hit/NDCG at the prepared cutoff, publishes up to depth 100 or the
  complete official final frontier, exports exact supported target ranks, and
  types deeper absence as right-censored. Boundary fixtures cover ranks 10,
  11, and 100, resolution failure, absence beyond depth, and rejection of an
  unsupported exact-rank claim.

## SIDScope v1.1.1.dev0: RPG trained closure

Status: unreleased post-1.1.0 maintenance

- Closed RPG G2--G5 with a fully recorded Beauty training output: 127 epochs,
  12,827 updates, best epoch 107, and patience-20 early stopping.
- Added resumable epoch-boundary training, trained parallel-trace export, and a
  fail-closed verifier without vendoring the CC BY-NC upstream implementation
  or any raw data, embedding, checkpoint, or `.sem_ids` cache.
- Added a public five-episode deidentified smoke with 43 bounded target rows
  and an external 250-episode primary with a shared 12,101-row target-universe
  hash. The external primary records 8 Hit@10 episodes (`Recall@10=0.032`).
- Promoted the pinned Beauty configuration to `named_adapter` after G0--G5
  passed. RPG remains a parallel/unordered item-node graph generator and is not
  represented with autoregressive prefix semantics.
- Kept the immutable TOIS-bound `v1.0.2` and released post-submission `v1.1.0`
  records unchanged.

## SIDScope v1.1.0: Generator adapter maintenance

Release date: 2026-08-28
Tag: `v1.1.0`
Base: public `v1.0.2` (`6ae5c4f02da3eae0cf187683d9af4c7c66e8cfa0`)
Release commit: `a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3`
Archive SHA-256: `2b71bc8ad2128a2ce9d214b4fc13840e797e7c12bba6a7f063ff18d3abf2c65f`
Public URL smoke: PASS at `https://github.com/jdding/sidscope`, ref `v1.1.0`

`v1.0.2` is the immutable public SIDScope software/resource version bound to
the submitted TOIS package. Version 1.1.0 is post-submission maintenance and
does not revise the frozen paper, submission package, evidence, or claims.

- Replaced path-name model detection with an explicit SentenceTransformer
  loader that accepts local Sentence-T5 checkpoints and registry identifiers.
- Added the optional `latte` dependency group with `faiss-cpu` and
  `sentence-transformers`, while keeping the core SIDScope installation lean.
- Documented and tested that tokenizer-only Latte intake does not require the
  HuggingFace `datasets` package. Full upstream Latte pipelines remain isolated
  in their own environments.
- No diagnostic definition, evidence snapshot, or manuscript/PDF change.
- Added a G0--G5 generator-adapter protocol and a verified coverage ledger for
  TIGER/DACT, Latte/PSID, RPG, LLaDA-Rec, and ISD. The ledger keeps
  released reference evidence, named-adapter closure, and source-audit
  candidates distinct.
- Pinned RPG's official source at `7dcf95c`, recorded its CC BY-NC 4.0 code
  boundary and absence of released checkpoints/caches, and added an independent
  unordered token-set plus per-item graph-node adapter contract.
- Added a deterministic RPG CPU fixture, ambiguity-preserving ranked-item trace,
  expected invalid-token-set fixture, verifier, and bounded smoke against the
  official source class. The smoke uses untrained weights and does not promote
  RPG to a named adapter.
- Built and hash-froze a real Beauty OPQ32 cache from the pinned official RPG
  dataset/tokenizer classes and a pinned Sentence-T5 snapshot. All 12,101 items
  pass source-item to item-node to SID to disjoint-vocabulary to item-node
  round-trip; two real token-set collisions covering four item nodes remain
  explicit rather than being collapsed.
- Added the RPG cache builder, an OpenMP-isolated exact official OPQ runner,
  cache normalizer, positive and expected-failure tests, deterministic replay,
  public summary-only evidence, and a non-paper-counted C0--C5 report. Raw data,
  text, embeddings, generated `.sem_ids`, and normalized tables stay external;
  trained RPG decoding G2--G5 remains open.
- Pinned the official Latte/PSID source, Amazon Reviews 2023 input revision,
  and Sentence-T5 model revision; generated and hash-froze one real
  Musical Instruments `rqkmeans` cache through official metadata-cleaning,
  quantization, and conflict-resolution methods.
- Added a PAD-aware Latte/PSID cache normalizer, exact PSID/Latte vocabulary
  offsets, typed collision/catalog failures, a latent-path aggregation trace,
  positive and expected-failure fixtures, an official-source CPU method smoke,
  C0--C5 intake evidence, and an executable verifier.
- Kept Amazon raw data, metadata, embeddings, the generated cache, normalized
  tables, and checkpoints outside the public package. The cache route is
  statically closed, but Latte remains below complete G0--G5 named-adapter
  status until trained inference and real trace export pass.
- Added a reusable fail-closed Latte/PSID trained-trace handoff contract and
  verifier for checkpoint-owning downstream projects. It requires hash-bound
  data, split, SID, checkpoint, configuration, command, and log evidence plus
  per-attempt beam ancestry, step log-probabilities, item resolution, ranked
  exports, retry state, and compute accounting. Aggregate confidence traces,
  raw identities, labels, private paths, and unbounded exports are rejected;
  the bundled positive fixture does not change the pending real G2/G4/G5
  status.
- Replaced the initial trained-trace handoff v1 with v2 after independent
  downstream review found that legitimate HF early termination uses PAD token
  `0` and `beam_indices=-1`. V2 retains every final beam, explicit decoded and
  ancestry lengths, raw or nullable padding slots, typed termination/failure
  labels, and canonical normalized-item/SID target-universe hashing. It also
  preserves PSID's raw top-k invalid rank slots instead of densely backfilling
  valid items; Latte aggregation remains a dense ranked-item export.
- Closed Latte/PSID G0--G5 with downstream-owned, hash-bound 10,000-update
  checkpoints. Both methods pass one episode per natural gap bucket and a
  250-episode diagnostic export; all four positive bundles pass the v2
  verifier and all four missing-ancestry derivatives fail closed with the
  expected typed label.
- Added two public deidentified real smoke bundles. PSID preserves 250 returned
  beams and 50 raw evaluation slots; Latte preserves 750 beams across both
  attempts for five retry episodes and exports 50 dense aggregated ranks. The
  250-episode bundles remain external with frozen checkpoint, cache, split,
  target-universe, command, log, and output hashes.
- Promoted the configuration-bound Latte/PSID route to SIDScope's first
  complete named generator adapter. This resource evidence is post-submission
  development and does not change the frozen TOIS manuscript or claims.
- Fixed the local G8 fresh-environment runner to upgrade pip before editable
  installation. This avoids Apple Command Line Tools Python 3.9 falling back
  to `setup.py develop` and losing pip inside its PEP 517 subprocess; a focused
  regression test now keeps the local and public URL install sequences aligned.
- Made the release archive deterministic by sorting manifest-approved paths and
  fixing ZIP timestamps, permissions, and compression settings. Rebuilding the
  same release tree now produces the same archive SHA-256 inside and outside a
  clean extracted environment.
- Pinned the official LLaDA-Rec source at `83dbcd6` and recorded that the code
  repository has no detected license, tag, release, checkpoint, semantic-ID
  cache, processed dataset, or training log.
- Added an independent masked-state adaptive-unmasking trace contract,
  position-specific vocabulary and ambiguity-aware item resolution, a
  deidentified CPU fixture, an expected remasking failure, and an official
  class-method smoke using handcrafted logits. The pinned inference code does
  not remask filled positions, so the route remains below named-adapter status.
- Backfilled DACT/TIGER into a complete method-facing G0--G5 report. The
  released source-item mapping, Tools `0.6_cf` SID array, test split, official
  preprocessing, and TIGER checkpoint are revision- and hash-bound.
- Added an ordered-prefix/parent-beam adapter contract, deidentified positive
  and typed failure fixture, and real four-target CPU checkpoint replay. The
  revised G21 exporter now records ordered prefixes and Hugging Face beam
  ancestry together with transition and sequence scores.
- DACT/TIGER passes G1--G5 but remains below named-adapter status because the
  official repository has no detected code or asset license. The historical
  500-target primary is retained accurately as pre-ancestry evidence.
- Located the ISD paper's anonymous official artifact and audited the exact
  support-map, prefix-selection, and final-RRF implementation. The artifact has
  no exposed Git revision or root code license, ships no data or checkpoints,
  and has a mismatched root README; those boundaries are retained explicitly.
- Added an independent ISD decoder-overlay contract, deterministic CPU fixture,
  collision-preserving item resolution, base-candidate and pruning trace,
  final non-inserting RRF export, typed provider-only insertion failure,
  exact-function source smoke, verifier, and package tests. ISD is no longer a
  source-watch route, but remains below named-adapter status.

## SIDScope v1.0.2 TOIS submission software/resource release

Date: 2026-08-20
Tag: `v1.0.2`

- The unauthenticated public-URL smoke now upgrades pip and installs the
  package with its declared dependencies before running conformance and
  package verifiers.
- Added a regression assertion that forbids the previous `--no-deps` path.
- No diagnostic definition, evidence row, or manuscript result changes.
- This tag is the immutable public SIDScope software/resource ref used by the
  submitted TOIS package; the separately frozen paper repository remains the
  authority for the submitted manuscript and submission files.

## SIDScope v1.0.0 reviewer release

Date: 2026-08-13
Tag: `v1.0.0`

- Froze the manifest-approved TOIS reviewer package as the first stable
  SIDScope resource release.
- Added the DIGER/Yelp non-Amazon route and refreshed the nine-route source,
  license, configuration, and C0--C5 conformance inventory.
- Bound all eight manuscript tables, D1--D7 diagnostics, the D3 evidence
  ladder, trained-trace accounting, and the diagnosis--repair--re-audit
  walkthrough to compact package-relative evidence.
- Verified the CPU-only package contract, deterministic table regeneration,
  claim ledger, clean archive extraction, and fresh-environment workflow.
- Kept paper sources, private datasets, checkpoints, cloud payloads, and local
  experiment provenance outside the release surface.
- Public no-login URL smoke remains the only release-access check that must be
  run after repository visibility is changed from private to public.

## SIDScope v1.0.1 statistical and reader-interface release

Date: 2026-08-19
Tag: `v1.0.1`

- Added exact tokenizer-export and catalog-collapse sensitivity for the D3
  construct-calibration row, plus a nine-configuration bounded protocol audit.
- Added paired user-bootstrap intervals and gate probabilities to the DACT
  refresh-and-handoff case without changing its preregistered decision rule.
- Expanded the ReSOT same-dataset control from depth 1 to the full four-level
  profile and added a worked item-to-SID teaching figure to the paper source.
- Rebuilt the evidence ladder to 14 rows and refreshed the release manifest,
  protocol configuration, claim ledger, and table/figure registry.

## TOIS M1--M5 preparation refresh

Date: 2026-08-09
Tag: `sidscope-tois-m1m5-20260809-r2`

- Added G21 released-checkpoint and G22 refresh-handoff compact evidence.
- Rebuilt all ten manuscript table snapshots with 86 verified rows.
- Added torch-absent and missing-upstream skips for the clean reviewer package.
- Refreshed the D3 calibration-reach claim ledger, pip floor, verifier commands,
  and manuscript-to-package table mapping.
- Kept the repository private; unauthenticated URL smoke remains a separate
  submission-time gate.

## Official private preparation surface

Date: 2026-08-08
Status: manifest-approved package prepared for the private official repository;
unauthenticated public URL smoke remains pending until the repository is made
reviewer-visible

### Added

- Standalone SIDScope official repository:
  `https://github.com/jdding/sidscope`.
- SIDScope resource package docs, datasheet, limitations, maintenance policy,
  release checklist, and reproducibility matrix.
- G14 usage-demo walkthrough:
  `docs/SIDSCOPE_USAGE_DEMO.md`,
  `docs/reproducibility/g14_usage_demo_decisions.csv`,
  `docs/reproducibility/g14_usage_demo_summary.json`, and
  `tools/run_sidscope_usage_demo.py`.
- CPU-only reviewer quickstart, sampled regeneration, release archive builder,
  package verifier, claim-ledger verifier, and public URL smoke runner.
- Compact evidence snapshots under `docs/reproducibility/`.
- Nine source-traced artifact routes, eight C0--C5 conformance reports, and a
  directly runnable negative fixture.
- Deterministic reconstruction of all manuscript-facing table snapshots.
- G20 trained constrained-beam trace summaries and verification code.
- G21 released DACT TIGER/T5 constrained/unconstrained trace summary.
- G22 released DACT mapping-refresh diagnosis, D6 re-audit, and bounded
  three-seed generator-handoff summary.

### Removed From Public Surface

- CIKM 2026 SIDInspector V0 paper source/PDF snapshot.
- Local handoff and cross-project idea-boundary files.
- Legacy SIDInspector project-state document that described a mixed V0/V1
  repository.

### Boundary

- The Python package import path remains `sidinspector` for compatibility with
  the diagnostic toolkit.
- The earlier SIDInspector repository remains the accepted CIKM 2026 resource
  surface and must not receive SIDScope journal-extension pushes.
- Public URL smoke for `https://github.com/jdding/sidscope` at `main` is
  required after the private preparation repository becomes reviewer-visible.

## Release boundary

The official repository is built from the manifest-approved archive rather
than the private project worktree. Paper sources, large upstream artifacts,
checkpoints, cloud payloads, and local provenance are excluded. Release commit,
tag, archive checksum, and public URL smoke are recorded outside the archive
after the release surface is frozen.
