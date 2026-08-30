# SIDScope Maintenance And Versioning

Status: current maintenance plan for standalone SIDScope public repository
Last updated: 2026-08-29

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
- `v1.0.2`: immutable public SIDScope software/resource version bound to the
  submitted TOIS package; later maintenance releases do not revise that
  submission snapshot or its claims.
- `sidscope-v1-tois-submission`: frozen journal-submission package.
- `sidscope-v1-tois-revision-N`: revised journal packages when requested by
  the editor; each tag must bind a verifier record and archive checksum.

Version 1.1.0 was released from `codex/sidscope-v1.1` as annotated tag
`v1.1.0` at `a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3`. The public URL smoke
passed and rebuilt archive SHA-256
`2b71bc8ad2128a2ce9d214b4fc13840e797e7c12bba6a7f063ff18d3abf2c65f`.
This branch must not contain or edit the frozen TOIS manuscript.

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

## Architecture Governance

The approved post-1.1.1 product boundary and runtime shape are defined in
`docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md`; versioned transition gates are in
`docs/V1_2_TO_V2_ROADMAP.md`. Significant changes to owned layers, plugin
boundaries, schema compatibility, registry authority, distribution policy or
runtime topology require an Architecture Decision Record under `docs/adr/`.

Accepted ADRs are historical records. Do not rewrite an accepted decision to
fit a later implementation; create a superseding ADR with the new context,
alternatives, consequences, rollout and rollback. Patch releases must not
introduce breaking shared-core refactors. Compatibility wrappers require an
owner plus an explicit retirement or archived-history condition.

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
deidentified fixtures, source hashes, and derived smoke/cache summaries. The
official-code-derived Beauty cache can pass non-paper-counted C0--C5 and G1
without redistributing official code, raw data, text, embeddings, `.sem_ids`,
normalized tables, or checkpoints; those artifacts remain external.

RPG's configuration-bound trained closure follows the same boundary. The
public package contains a five-episode parallel graph trace and only the 43
normalized-item/SID rows needed to verify its ranked-item collision
resolution. The complete 12,101-row target universe and 250-episode trace stay
external, while their hashes, counts, split, checkpoint, full training resume
chain, and verifier result are public. A maintenance release must rerun the
bounded public bundle and must not reinterpret RPG as an autoregressive prefix
generator.

The Latte/PSID integration demonstrates a data-license boundary. The upstream
code is MIT and Sentence-T5 is Apache-2.0, but the audited Amazon Reviews 2023
dataset card does not declare an explicit license identifier. SIDScope can
therefore record a reproducible official-code-derived cache build and C0--C5
report while redistributing only hashes, counts, bounded diagnostics, and a
deidentified fixture. Raw histories, metadata text, sentence embeddings, the
real `.sem_ids` cache, and normalized tables remain external.

Checkpoint-owning downstream projects should return only the bounded,
deidentified `sidscope.latte_psid_trained_trace_bundle.v2` handoff. SIDScope's
trained-trace verifier rejects confidence-only summaries, missing beam
ancestry or step log-probabilities, raw identities, targets, checkpoint paths,
and unbounded episode exports. This lets the canonical repository close real
G2/G4/G5 evidence without absorbing a downstream training fork or private
checkpoint.

The first completed handoff retains two public five-episode checkpoint-backed
smoke bundles and a compact hash-bound summary of two external 250-episode
diagnostics. A named-adapter release must rerun both public smoke bundles in the
release archive. Full traces and checkpoints remain external; their absence
from the package is intentional and must be accompanied by immutable hashes,
counts, split identity, training boundary, and verifier results.

The v2 handoff preserves early-ended and invalid HF beams with explicit raw
token slots, decoded/ancestry lengths, PAD or null tail slots, termination and
failure labels. It also preserves PSID's raw top-k evaluation slots without
backfilling and binds target-universe identity to canonical normalized-item/SID
rows. Schema v1 bundles must be regenerated; they are not auto-upgraded.

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

Direct author clarification is useful evidence but is not represented as a
repository license file. Until a LICENSE is published, keep
`license_status=no_license_detected`, record the dated clarification in
`license_identifier`, and retain the existing conservative redistribution
policy. Do not publish raw correspondence in the resource package.

Clarifications received on 2026-08-29:

- DIGER: the author states that the code is MIT and that the Hugging Face
  artifacts may be used for research under the same terms; the repository
  LICENSE is pending.
- LETTER: the author permits SIDScope research use of the code, datasets, and
  SID indexes, requiring citation and acknowledgment of the CIKM 2024 paper;
  a repository license is planned.
- ReSOT: the author permits released code, datasets, checkpoints, and SID
  indexes for noncommercial academic research, requiring citation of the KDD
  2026 paper.

These citations should be added only in a separately authorized future paper
revision. They do not modify the frozen TOIS submission or the immutable
`v1.0.2` evidence boundary.

A CITATION file can be added after the paper venue branch is final. Before
acceptance, cite the preprint or repository title:

```text
SIDScope: Artifact-Level Diagnostics for Semantic-ID Generative Recommendation.
```

## End-Of-Life

If upstream Semantic-ID formats change, preserve this release as a historical
artifact and add new adapters rather than rewriting old evidence snapshots.
