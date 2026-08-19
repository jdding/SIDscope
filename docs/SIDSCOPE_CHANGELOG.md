# SIDScope Changelog

Status: clean SIDScope official-repository changelog
Last updated: 2026-08-19

This changelog records reviewer-package changes for the standalone SIDScope
repository at `https://github.com/jdding/sidscope`. The earlier SIDInspector
repository remains reserved for the CIKM V0 surface and is not a SIDScope
release surface.
The public repository is the reviewer-visible and post-acceptance open source
package surface only; it is not the private project workspace and must not
include paper drafts, local provenance, AutoDL payloads, or large caches.

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
