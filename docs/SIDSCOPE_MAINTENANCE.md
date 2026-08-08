# SIDScope Maintenance And Versioning

Status: current maintenance plan for standalone SIDScope public repository
Last updated: 2026-08-08

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
