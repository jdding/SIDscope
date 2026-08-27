# SIDScope Maintenance And Versioning

Status: current maintenance plan for standalone SIDScope public repository
Last updated: 2026-08-27

## Release Policy

The reviewer package should be tagged only after G8 closes. Current
reviewer-package release tags or branch references must remain tied to a
recorded verifier and public URL smoke result.

The release-candidate contents are tracked in
`docs/reproducibility/sidscope_release_candidate_manifest.csv`. Any public tag
or archive should be checked with `tools/verify_sidscope_resource_package.py`
and the G8 fresh-environment smoke in `docs/SIDSCOPE_RELEASE_CHECKLIST.md`.
The public URL, tag, archive checksum, and fresh-environment transcript should
be recorded in `docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md`.

Release refs:

- `main`: current clean SIDScope public repository surface at
  `https://github.com/jdding/sidscope`.
- `sidscope-v1-tois-submission`: frozen journal-submission package.
- `sidscope-v1-tois-revision-N`: revised journal packages when requested by
  the editor; each tag must bind a verifier record and archive checksum.

Active development occurs on `codex/sidscope-v1.1` as `1.1.0.dev0`. It may
change code and public resource documentation, but it must not contain or edit
the frozen TOIS manuscript.

## Maintenance Commitments

For the paper artifact:

- keep the package importable on Python 3.9+;
- keep the CPU quickstart runnable without private data;
- keep `tools/verify_sidscope_resource_package.py` passing for release tags;
- preserve compact evidence snapshots used in the paper;
- document any upstream artifact that is required but not shipped.

## Changelog Policy

Before any public release, create or update `docs/SIDSCOPE_CHANGELOG.md` with:

- package tag;
- public repository or archive URL;
- commit hash and archive checksum;
- date;
- paper/resource status;
- supported diagnostic surfaces;
- known omitted artifacts;
- reproduction commands tested;
- compatibility notes.

## Issue Triage

Report and triage issues by category:

- adapter/schema bug;
- diagnostic metric bug;
- evidence snapshot mismatch;
- documentation ambiguity;
- package usability failure;
- upstream artifact unavailable.

Evidence snapshot mismatch and package usability failure are release blockers
for resource-paper packaging.

## Generator Adapter Lifecycle

Generator integrations use the G0--G5 protocol in
`docs/GENERATOR_ADAPTER_CONFORMANCE.md` in addition to any applicable C0--C5
mapping checks. A successful upstream training command or local workaround is
not a named adapter. Promotion requires typed method-specific traces, item
round-trip evidence, ranked-item export, a CPU fixture, a bounded model smoke,
and a passing verifier.

The active queue and source-watch state are tracked in
`docs/reproducibility/generator_adapter_coverage.csv`. Downstream projects should
report failures through an issue packet and keep any workaround visibly
non-canonical until it is incorporated and tested in SIDScope.

The RPG integration demonstrates the license boundary: its official source is
CC BY-NC 4.0, so SIDScope ships only an independently implemented MIT contract,
deidentified fixture, source hashes, and derived smoke summary. Official code,
data, `.sem_ids`, and checkpoints must remain external.

## License And Citation

The code package uses the repository `LICENSE`. If an upstream artifact has a
different license or redistribution restriction, SIDScope should link to the
upstream source and ship only lightweight derived summaries when allowed.

A CITATION file can be added after the paper venue branch is final. Before
acceptance, cite the preprint or repository title:

```text
SIDScope: Artifact-Level Diagnostics for Semantic-ID Generative Recommendation.
```

## End-Of-Life

If upstream Semantic-ID formats change, preserve this release as a historical
artifact and add new adapters rather than rewriting old evidence snapshots.
