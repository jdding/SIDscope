# SIDScope Maintenance And Versioning

Status: current maintenance plan for standalone SIDScope public repository
Last updated: 2026-08-28

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
deidentified fixture, source hashes, and derived smoke/cache summaries. The
official-code-derived Beauty cache can pass non-paper-counted C0--C5 and G1
without redistributing official code, raw data, text, embeddings, `.sem_ids`,
normalized tables, or checkpoints; those artifacts remain external.

The Latte/PSID integration demonstrates a data-license boundary. The upstream
code is MIT and Sentence-T5 is Apache-2.0, but the audited Amazon Reviews 2023
dataset card does not declare an explicit license identifier. SIDScope can
therefore record a reproducible official-code-derived cache build and C0--C5
report while redistributing only hashes, counts, bounded diagnostics, and a
deidentified fixture. Raw histories, metadata text, sentence embeddings, the
real `.sem_ids` cache, and normalized tables remain external.

Checkpoint-owning downstream projects should return only the bounded,
deidentified `sidscope.latte_psid_trained_trace_bundle.v1` handoff. SIDScope's
trained-trace verifier rejects confidence-only summaries, missing beam
ancestry or step log-probabilities, raw identities, targets, checkpoint paths,
and unbounded episode exports. This lets the canonical repository close real
G2/G4/G5 evidence without absorbing a downstream training fork or private
checkpoint.

The LLaDA-Rec integration demonstrates an absent-code-license boundary. The
paper is CC BY 4.0, but the official code repository has no detected license;
these are distinct artifacts. SIDScope may link to and hash the pinned source,
run external source-shaped checks, and publish an independently written
deidentified contract fixture. It must not vendor the upstream implementation
or promote the route until an explicit reusable source license and the missing
model/tokenizer assets are available.

The DACT/TIGER integration demonstrates that released checkpoints and passing
real-model traces do not override an absent license. Its official repository
contains the Tools mapping, test split, and TIGER weights but no detected code
or asset license. SIDScope can verify hashes, run those assets externally, and
ship independent ordered-prefix fixtures and derived/deidentified summaries;
it must not vendor the upstream files or label the route a named adapter until
reuse permission is explicit.

The ISD integration demonstrates an anonymous-review-snapshot boundary. The
paper links an artifact containing exact method files, but the artifact exposes
no Git revision or root code license, its root README describes a different
review snapshot, and it ships no model/data outputs. SIDScope binds selected
files by SHA-256, runs exact pure functions externally, and publishes only an
independent overlay contract and deidentified fixture. Snapshot identity alone
must not be represented as an immutable source revision.

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
