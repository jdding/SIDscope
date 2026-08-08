# SIDScope Changelog

Status: clean SIDScope official-repository changelog
Last updated: 2026-08-08

This changelog records reviewer-package changes for the standalone SIDScope
repository at `https://github.com/jdding/SIDscope`. The earlier SIDInspector
repository remains reserved for the CIKM V0 surface and is not a SIDScope
release surface.
The public repository is the reviewer-visible and post-acceptance open source
package surface only; it is not the private project workspace and must not
include paper drafts, local provenance, AutoDL payloads, or large caches.

## Official private preparation surface

Date: 2026-08-08
Status: manifest-approved package prepared for the private official repository;
unauthenticated public URL smoke remains pending until the repository is made
reviewer-visible

### Added

- Standalone SIDScope official repository:
  `https://github.com/jdding/SIDscope`.
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
- Eight source-traced artifact routes, seven C0--C5 conformance reports, and a
  directly runnable negative fixture.
- Deterministic reconstruction of all manuscript-facing table snapshots.
- G20 trained constrained-beam trace summaries and verification code.

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
- Public URL smoke for `https://github.com/jdding/SIDscope` at `main` is
  required after the private preparation repository becomes reviewer-visible.

## Release boundary

The official repository is built from the manifest-approved archive rather
than the private project worktree. Paper sources, large upstream artifacts,
checkpoints, cloud payloads, and local provenance are excluded. Release commit,
tag, archive checksum, and public URL smoke are recorded outside the archive
after the release surface is frozen.
