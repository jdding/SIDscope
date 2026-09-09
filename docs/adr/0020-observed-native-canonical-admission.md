# ADR-0020: Observed native canonical diagnostic admission

Status: accepted local implementation, 2026-09-08. Version remains 1.7.0.dev0.
Accountable: jdding; existing SDK, Contracts, Evidence and Diagnostics ownership.

## Decision

Keep one local synchronous Python process. A pure-data adapter bridge converts
the already authorized RPG Beauty / PSID Video Games observations into existing
SourceIdentity, DatasetIdentity, SIDSpaceIdentity, PreparedDataset, EpisodeSelection,
RunIdentity, CheckpointBinding, TraceEnvelope, DiagnosticReport, EvaluationProtocol,
ProfileConformanceReport and EvidenceBundle contracts. Reuse AdapterHarness,
canonical validators, current metric kernels, submission checker and comparison.
Do not build another storage system, service, model implementation or metric engine.

The producer exports an envelope for an **already observed** native execution.
It uses the SDK 0.2-supported 0.1 descriptor because the unchanged legacy payloads
are not the newer registered family-payload schemas. A payload hash binds exact
native bytes; RPG remains graph item-node/unordered-token decoding, PSID remains
ordered autoregressive decoding. No legacy evidence or native verifier is changed.

## Identities and evidence limits

- Source revision is the content digest of observed Python/YAML module hashes,
  not a claim that patched runtime sources equal a pristine upstream git commit.
- Data/prepared identities bind the actual normalized representations, full
  exported catalog and observed split rows. PSID's selected test scope remains
  explicit. Target universe here is the union of observed evaluation target IDs;
  the complete native decoding universe retains its separate hash in origin.
- SID vocabulary/offsets preserve each validated legacy format. Missing special
  token roles stay null; no new role or AR interpretation is invented for RPG.
- RunIdentity describes the canonical export of the supplied observation. Its
  command hash binds the normalized bridge entrypoint and exact input/metadata
  hashes, not a fabricated upstream shell command. Measurement environment is
  the recorded native CPU environment, retained in origin with its definition.
- Checkpoint progress comes from existing best-checkpoint records, not the final
  training budget. This inspection found PSID best epoch 12 / step 9372 while the
  run ended at step 10000, and RPG best epoch 107 / step 10807 while the run ended
  at step 12827. These records do not independently verify training.
- Checkpoint provenance is hash-only. A validated CheckpointBinding metadata
  object may accompany it under `checkpoint_identity`; no weights or training
  state are embedded. Full native/preflight files and runtime specs stay external.
- PSID slice `>365d` maps explicitly to canonical `gt365d`; the original label and
  mapping remain bound. Ranked invalid/duplicate slots are never removed/backfilled.
- Generation/resolution come from full final native frontiers/beams, not from
  whether a target appeared in the published top ten. Ranks outside publication
  remain right-censored, even when a target is observed in a wider native frontier.

Named-adapter G0--G5 statuses remain partial in these new reports. The independent
diagnostic checker may accept them as `diagnostics_verified`, which is not training,
native execution authenticity, named-adapter promotion or independent user adoption.
No signature policy. Same-export comparison is explicitly recomputation, not a
second model run, multi-seed result or cross-dataset method comparison.

## Rejected alternatives and privacy repair

Rejected: borrow fixture provenance; fill unknown counts with zero; bind a best
checkpoint to final run progress; use historical G0--G5 PASS as new verification;
claim new native-family payload schemas without migrating the actual payload.

The existing scanner rejected valid PreparedDataset normalization declarations.
Permit its two false export flags only after full PreparedDataset validation;
do not accept arbitrary normalization dictionaries or true/numeric flags. The
PreparedDataset validator now checks boolean identity, closing Python's `0 == False`
loophole without changing the schema or any valid document identity.

## Operations, recovery and verification

Caller supplies input-directory, automatically extracted checkpoint-metadata and
new output path. The bridge computes all internal contracts/hashes. It validates
before publication and writes `complete.json` last. Refuse existing outputs and
outputs nested inside original inputs; interrupted output is preserved and retried
under a new directory. Rollback: stop using the optional tool; old workflows and
immutable evidence remain unchanged. No deployment migration or new on-call role.

`--verify-submission` rebuilds expected canonical evidence from the original
native inputs, then invokes diagnostic admission. This additional check rejects
even an internally consistent, rehashed forged trace. Generic diagnostic admission
still promises only diagnostics-from-supplied-trace, not native authenticity.

Acceptance: both actual observations build and independently recheck; SDK export
is invoked once; canonical dependencies/protocols match; forged hashes, target
states, cross-protocol comparisons, private content, missing metadata and wrong
checkpoint progress fail closed. Full CPU tests, resource/profile verifiers and
exact-source wheel/sdist/archive/G8 delivery must pass. F09 independent user use
remains separate from this technical N03 acceptance. Next: N05, then N04, then N08.
