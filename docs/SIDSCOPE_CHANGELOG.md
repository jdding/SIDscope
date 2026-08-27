# SIDScope Changelog

Status: clean SIDScope official-repository changelog
Last updated: 2026-08-27

This changelog records reviewer-package changes for the standalone SIDScope
repository at `https://github.com/jdding/sidscope`. The earlier SIDInspector
repository remains reserved for the CIKM V0 surface and is not a SIDScope
release surface.
The public repository is the reviewer-visible and post-acceptance open source
package surface only; it is not the private project workspace and must not
include paper drafts, local provenance, AutoDL payloads, or large caches.

## SIDScope v1.1.0-dev: Generator adapter maintenance

Development opened: 2026-08-27
Base: public `v1.0.2` (`6ae5c4f02da3eae0cf187683d9af4c7c66e8cfa0`)

- Replaced path-name model detection with an explicit SentenceTransformer
  loader that accepts local Sentence-T5 checkpoints and registry identifiers.
- Added the optional `latte` dependency group with `faiss-cpu` and
  `sentence-transformers`, while keeping the core SIDScope installation lean.
- Documented and tested that tokenizer-only Latte intake does not require the
  HuggingFace `datasets` package. Full upstream Latte pipelines remain isolated
  in their own environments.
- No diagnostic definition, evidence snapshot, or manuscript/PDF change.
- Added a G0--G5 generator-adapter protocol and a verified coverage ledger for
  TIGER/DACT, Latte/PSID, RPG, LLaDA-Rec, ISD, and ChronoSID. The ledger keeps
  released reference evidence, named-adapter closure, source-audit candidates,
  and source-watch routes distinct.
- Pinned RPG's official source at `7dcf95c`, recorded its CC BY-NC 4.0 code
  boundary and absence of released checkpoints/caches, and added an independent
  unordered token-set plus per-item graph-node adapter contract.
- Added a deterministic RPG CPU fixture, ambiguity-preserving ranked-item trace,
  expected invalid-token-set fixture, verifier, and bounded smoke against the
  official source class. The smoke uses untrained weights and does not promote
  RPG to a named adapter.
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

## SIDScope v1.0.2 public-smoke dependency fix

Date: 2026-08-20
Tag: `v1.0.2`

- The unauthenticated public-URL smoke now upgrades pip and installs the
  package with its declared dependencies before running conformance and
  package verifiers.
- Added a regression assertion that forbids the previous `--no-deps` path.
- No diagnostic definition, evidence row, or manuscript result changes.

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
