# SIDScope 1.4 Development Handoff

Last updated: 2026-08-30

## Executive status

SIDScope 1.1.0 is locally release-ready and publicly released. The verified
`1.1.1.dev0` tree is the frozen regression authority; active development is
`1.4.0.dev0` in the dedicated `SIDScope-v2` worktree. Annotated tag `v1.1.0`
remains unchanged and resolves to
`a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3` on the public `main` branch.

Latte/PSID, RPG, DiffGRM, DACT/TIGER Tools, and LLaDA-Rec VG are the five
configuration-bound named generator adapters admitted under the complete
G0--G5 protocol. RPG retains parallel/unordered token-set and graph item-node
semantics; LLaDA-Rec retains native confidence-guided adaptive unmasking and
never masquerades as autoregressive prefix decoding. The remaining route is a
typed partial integration and must retain its documented gate label.

DiffGRM is now the publication-prioritized masked/diffusion candidate. Its The
Web Conference 2026 DOI, official repository revision, OPQ4 identity,
dataset-neutral prepared/selection contracts, native masked trace, positive
fixture, ten typed negative fixtures, and source-identity preflight are bound.
The missing root license is recorded as a `NOASSERTION` marker and no longer
blocks development, downstream execution, verification, or evidence delivery;
upstream redistribution remains excluded. Downstream VG OPQ4/prepared/
selection, CPU runtime, recoverable 10,000-step training, a five-bucket
checkpoint smoke with typed failure, and native v2 external 250-episode
diagnostics pass independently on VG and Steam. SIDScope accepts the route as a
configuration-bound named adapter through compact hash/count/metric evidence;
the full traces and upstream assets remain external.

The submitted TOIS manuscript is a frozen, separate repository. Nothing in
SIDScope 1.1 may be written back into that submission before an explicitly
authorized revision phase.

The approved long-term product position is a conformance and observability
platform for Semantic-ID and generative recommender systems. SIDScope does not
own the upstream method or training layer. It owns six layers from Adapter SDK
integration through canonical contracts, native observation, diagnostic
evaluation, conformance verification, and immutable evidence. The authoritative
design and gated release sequence are `docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md`
and `docs/V1_2_TO_V2_ROADMAP.md`. Implemented and planned surfaces are marked
separately; 1.5, 1.6 and 2.0 target features are not claimed by the 1.4 closure.

Architecture Sprint 0 is implemented on the 1.1.1 regression baseline.
It adds canonical version/hash governance, a machine-readable schema/profile/
producer/verifier/evidence inventory, an enforced acyclic module-dependency
matrix, the stable `sidscope` CLI facade, and the first complete vertical slice:
`sidscope.source_identity.v1` schema, Python model, validator, canonical hash,
positive fixture, typed negative fixture, and legacy adapter-manifest parity.
Sprint 1 is now implemented on `1.2.0.dev0`: the bundled
`sidscope.contract_registry.v1` is the canonical discovery and CLI-dispatch
authority, and `sidscope.dataset_identity.v1` provides a complete vertical
slice with full split/catalog/target-universe bindings plus an honest
`legacy_partial` migration. Registry unknown dependencies, cycles, unsupported
revisions, resource drift, and typed negative fixtures fail closed. This is an
unreleased development milestone and does not declare 1.2 publicly released.
Sprint 2 is also closed: `sidscope.sid_space_identity.v1` binds SID structure,
vocabulary, tokenizer/cache, collision, and de-duplication semantics, while
`sidscope.prepared_dataset.v1` binds complete DatasetIdentity and
SIDSpaceIdentity artifacts to normalized splits, artifacts, catalog, target
universe, and privacy. RPG migrates with exact fixture parity. Incomplete
DiffGRM and LLaDA legacy prepared contracts fail with a typed regeneration
requirement instead of inferred fields.

Sprints 3 and 4 are now closed together. EpisodeSelection, RunIdentity,
CheckpointBinding, TraceEnvelope, DiagnosticReport, ConformanceReport, and
EvidenceIndex complete the eleven-contract registry and fourteen-edge acyclic
dependency graph. Adapter SDK `0.1.0-alpha` and the shared adapter, contract,
trace, evaluate, verify, and evidence CLI paths are active. The common envelope
binds RPG's native parallel/unordered payload and never substitutes AR ancestry.
The canonical fixture has eight typed failures; report metrics and partitions
are independently recomputed; evidence packaging rejects missing dependencies,
cycles, and privacy violations.

The legacy migration matrix covers all six generator routes and nine static
mapping routes. RPG is the first exact end-to-end canonical fixture. Other
routes retain their existing verifier and status authority and receive a typed
canonical-regeneration disposition; this is not an adapter failure or implicit
promotion. The six shared command families have an eleven-repeat CPU baseline
and a 20% review policy. This closes 1.2 development scope, but does not create
a public 1.2 tag or release.

The 1.3 ecosystem milestone is also development-closed. SDK `0.2.0-alpha`
retains SDK 0.1 descriptor compatibility and binds each current capability
descriptor to one native payload schema. Lazy entry-point discovery uses
`sidscope.adapters`; listing reads metadata only and explicit preflight loads
one selected plugin. Five payload families preserve AR prefix, parallel
graph/token-set, masked diffusion, latent retry, and decoder-overlay semantics.
Their hash-bound registry, composable common/family profiles, five positive
fixtures, and seven typed negatives are independently verified.

The separately packaged `reference-parallel` plugin installs without core
edits. The isolated verifier first proves payload verification with no plugin
installed and then proves discovery/preflight after installation. RecBole is
only availability-probed and never imported. Existing named-adapter evidence is
unchanged.

The 1.4 evidence-system milestone is development-closed. EvidenceBundle v1 is
an immutable, canonical-JSON contract that binds profile, dataset, SID space,
run, checkpoint, trace, diagnostics, conformance, result-card, privacy, and
supersession identity. Semantic artifact identity (`content_sha256`) is kept
separate from exact stored-byte identity (`object_sha256`). The content-addressed
object store admits public bytes atomically, retains restricted assets as
hash-only references, and fail-closes on tampering, hash collision, forbidden
content, invalid provenance, and unsupported exact-rank claims.

SQLite is a disposable local projection, not evidence authority. It can be
deleted and deterministically rebuilt from active and quarantined immutable
bundles; the static export remains byte-equivalent. Corrections create a new
bundle with an explicit supersession edge. Comparison reports metric deltas
only when profile revision, dataset, target universe, cutoff, publication
depth, and rank semantics are compatible. The `sidscope evidence bundle` and
`sidscope registry` command families close build, verify, admit, import, list,
show, compare, supersede, quarantine, export, and rebuild workflows while the
legacy evidence-package path remains compatible. The next milestone is 1.5
conformance automation and submission ecosystem work. ADR-0010 then reserves
1.6 for compatibility, migration and external-adoption hardening before 2.0
declares the proven interfaces stable; none of those planned surfaces is
implied by the 1.4 closure.

The verified workspace policy keeps `SIDScope-v1.1` as the 1.1.x maintenance
surface and this `SIDScope-v2` worktree on `codex/sidscope-v2` as the only
1.2--2.0 development surface. The independent frozen TOIS repository remains
a non-merge target.

On 2026-08-29, the first authors of DIGER, LETTER, and ReSOT supplied direct
email clarifications for research use. DIGER's author states that the code is
MIT and that its Hugging Face artifacts may be used for research under the
same terms; the repository LICENSE is pending. LETTER's author permits use of
the code, datasets, and SID indexes for SIDScope research with citation and
acknowledgment of the CIKM 2024 paper; a repository license is planned.
ReSOT's author permits the released code, datasets, checkpoints, and SID
indexes for noncommercial academic research with citation of the KDD 2026
paper. All three repositories still return no detected LICENSE file, so the
inventory retains `no_license_detected` while recording these author
clarifications in `license_identifier`. Raw correspondence is private and is
not part of the public resource package. Existing non-redistribution policies
remain unchanged until repository-level terms make redistribution explicit.

## Canonical development surface

- Repository: the standalone `SIDScope-v2` worktree, not the historical
  `SIDInspector` workspace.
- Branch: `codex/sidscope-v2`.
- Upstream tracking branch: `sidscope/main`.
- TOIS-submission software/resource base, public `v1.0.2`:
  `6ae5c4f02da3eae0cf187683d9af4c7c66e8cfa0`.
- RPG P0 implementation commit before this handoff update:
  `60e421fb2736ceeead3cff0f7ac9e2cd23a04b95`.
- Regression authority: `1.1.1.dev0` in the separate `SIDScope-v1.1` worktree.
- Development version: `1.4.0.dev0` in both `pyproject.toml` and `setup.py`.
- Public release tag: `v1.1.0` at
  `a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3`.
- Deterministic tag archive SHA-256:
  `2b71bc8ad2128a2ce9d214b4fc13840e797e7c12bba6a7f063ff18d3abf2c65f`.

Always begin a resumed session by verifying the live branch, HEAD, worktree,
remotes, version, manifest, tests, and verifier. Do not assume the commit above
is still HEAD after handoff or release work.

## Non-negotiable boundaries

1. Do not develop in the historical `SIDInspector` directory. It contains
   unrelated projects and historical uncommitted experiments.
2. Do not edit, copy new evidence into, rebuild, or retag the frozen TOIS
   submission repository.
3. Do not commit checkpoints, raw datasets, embeddings, real `.sem_ids`
   caches, private paths, remote payloads, credentials, or source item IDs.
4. Do not create a formal release tag or push `main` without explicit user
   authorization.
5. Static item-to-SID admission is C0--C5. Generator and decoder admission is
   independently G0--G5. Passing one protocol never implies passing the other.
6. Do not promote a route to `named_adapter` unless all G0--G5 gates pass with
   the required source, identity, trace, resolution, export, fixture, smoke,
   hashes, and verifier evidence.

## Completed 1.1.0 work

### Core intake and protocol

- Local Latte/Sentence-T5 model paths are identified by filesystem semantics,
  not by model-name guessing.
- The tokenizer-only Latte extra uses optional `faiss-cpu` and
  `sentence-transformers`; Hugging Face `datasets` is not required.
- C0--C5 and G0--G5 are separate typed admission protocols.
- Coverage records distinguish reference traces, close named adapters, source
  audits, source watch, and complete named adapters.

### Latte/PSID trained adapter

Latte/PSID passes G0--G5 as a configuration-bound named adapter. Its closure
includes:

- pinned official source revision and license boundary;
- official-code-derived static cache evidence and real item/vocabulary
  round-trip;
- checkpoint- and split-bound PSID ordered-beam traces;
- checkpoint- and split-bound Latte latent-retry traces;
- two public, deidentified five-episode real smoke bundles;
- two external 250-episode diagnostics bound by hashes and counts;
- typed expected-failure bundles;
- a CPU verifier that is rerun by the resource-package verifier.

The v2 trained-trace contract preserves legitimate early-ended or invalid
beams without fabricating evidence. It supports raw token slots, decoded and
ancestry lengths, PAD or null tail slots, typed termination/failure labels,
and complete final-beam retention. PSID evaluation slots preserve original
top-k rank without backfilling invalid positions. Target-universe identity is
bound to canonical normalized-item/SID rows and does not expose source IDs.
Schema v1 trained bundles are not auto-upgraded.

Relevant evidence and contracts:

- `docs/LATTE_PSID_GENERATOR_ADAPTER.md`
- `docs/reproducibility/latte_psid_adapter_status.json`
- `docs/reproducibility/latte_psid_trained_trace_evidence.json`
- `examples/latte_psid_trained_trace_real_smoke/`
- `tools/verify_latte_psid_adapter.py`
- `tools/verify_latte_psid_trained_trace_bundle.py`

### Release preparation

- Package version promoted from `1.1.0.dev0` to `1.1.0`.
- Release checklist, public release packet, maintenance guide, changelog,
  roadmap, README, adapter ledgers, and manifest were updated.
- G8 now upgrades old environment pip to `pip>=21.3` before editable install,
  fixing the Apple command-line-tools Python 3.9 failure mode.
- Release archives use sorted paths and fixed ZIP metadata, making independent
  builds byte-for-byte deterministic.

Important implementation commits:

- `45e2547` -- close the Latte/PSID trained adapter.
- `3de91eb` -- prepare SIDScope 1.1.0.
- `3f46f03` -- make the release archive deterministic.

## Completed 1.1.1.dev0 P0 work

RPG now passes G0--G5 as a configuration-bound named adapter. The closure
uses the pinned CC BY-NC source and real official-code-derived Beauty cache,
without vendoring upstream code or assets. The formal run completed 127 epochs
and 12,827 updates, selected epoch 107 by validation NDCG@10, and stopped after
the configured patience of 20.

The public package contains a five-episode deidentified trained smoke with 43
bounded normalized-item/SID resolution rows. An external 250-episode primary
contains the complete 12,101-row target universe; the public evidence binds it
by SHA-256, counts, split, checkpoint, training manifests, resumable state,
runner, exporter, verifier, and target-universe hash. The external primary has
8 Hit@10 episodes (`Recall@10=0.032`).

Relevant evidence and contracts:

- `docs/RPG_GENERATOR_ADAPTER.md`
- `docs/reproducibility/rpg_kdd2025_adapter_status.json`
- `docs/reproducibility/rpg_kdd2025_trained_trace_evidence.json`
- `examples/rpg_generator_trained_trace_real_smoke/`
- `tools/run_rpg_resumable_training.py`
- `tools/export_rpg_trained_trace.py`
- `tools/verify_rpg_trained_trace_bundle.py`

### Dataset-neutral RPG bridge

The post-P0 maintenance surface now includes a generic prepared-data bridge for
frozen downstream protocols. It binds normalized split/catalog/SID artifacts,
completed training hashes and an explicit ordered episode-selection manifest.
The upstream `Pipeline` cannot accept a dataset instance as annotated because
it calls the returned instance; SIDScope therefore constructs the unmodified
official RPG tokenizer/model over a checked `AbstractDataset` implementation.

The bridge schemas are `sidscope.rpg_prepared_dataset.v1`,
`sidscope.rpg_episode_selection.v1`, `sidscope.rpg_trained_trace_bundle.v2`,
and `sidscope.rpg_downstream_handoff.v1`. Synthetic positive and typed failure
fixtures pass, as does a one-epoch CPU prepared runner/export/verifier smoke.
Beauty's real schema-v1 five-episode bundle remains the regression authority.
No unrun downstream dataset inherits Beauty's named-adapter evidence.

The resumable runner now writes `sidscope.rpg_resumable_state.v2` atomically at
every epoch with cumulative epoch records, then atomically updates the
hash-bound `sidscope.rpg_epoch_ledger.v1`. A real two-stage CPU regression
completed epoch 1, removed the normally written invocation manifest to model a
post-checkpoint interruption, and resumed to epoch 2 using only the embedded
records plus the exact ledger. The final manifest preserves continuous epochs,
global steps, and model-state hashes. Legacy checkpoints without embedded
records require a matching continuous legacy manifest or fail closed.

Prepared v2 traces may now add the backward-compatible
`sidscope.rpg_rank_depth_diagnostic.v1` extension. It separates the frozen
evaluation cutoff from ranked-item publication depth, preserves all existing
training/prepared/selection/checkpoint and graph bindings, and requires exact
target ranks to have an ordered supporting row. Missing targets are typed as
right-censored beyond the published depth unless an in-depth SID collision
proves a resolution failure. The frozen VG RPG configuration uses 20 beams, so
its method-faithful complete ranking depth is 20 even when depth 100 is
requested; ranks 21+ remain right-censored unless a separately authorized run
changes the beam/graph experiment.

See `docs/RPG_NON_AR_BRIDGE.md`.

## Generator-route gate status

The machine-readable authority is
`docs/reproducibility/generator_adapter_coverage.csv`.

| Route | Current gate state | Allowed description | Next closure |
| --- | --- | --- | --- |
| Latte / PSID | G0--G5 pass | `named_adapter` | Maintain v2 compatibility and rerun both public real smoke bundles for every release archive. |
| RPG | G0--G5 pass on the pinned Beauty configuration | `named_adapter` | Maintain the bounded public smoke and rerun external training evidence only when the pinned source, cache, or configuration changes. |
| TIGER / DACT | G0--G5 pass on released Tools configuration, including refreshed 500-target dual-mode ancestry export | `named_adapter` | Maintain compact external-trace evidence; rerun only when pinned inputs or configuration change. |
| LLaDA-Rec | G0--G5 pass on frozen VG: formal 10,000-epoch official tokenizer, prepared round-trip, recoverable 10,000-step generator, native five-bucket trace, typed failure, and external 250 diagnostic | `named_adapter` | Maintain compact external evidence and rerun only when the tokenizer, generator, data, or configuration changes. |
| DiffGRM | G0--G5 pass independently on frozen VG and Steam OPQ4/10,000-step configurations, including five-bucket native v2 smokes and external 250 diagnostics | `named_adapter` | Maintain both compact configuration records; rerun only when pinned inputs change. |
| Item-Supported Decoding | Content-addressed snapshot, fail-closed overlay contract, and exact-function smoke; G0 revision identity partial, G1 fixture, G5 partial | `close_named_adapter` | Obtain an immutable official revision; bind data/checkpoints and export a real overlay trace. |

RPG must retain unordered token-set identity and graph-valid completion; it
must never be converted into a TIGER-style autoregressive prefix trace.
LLaDA-Rec must retain diffusion/remasking state. ISD remains a decoder overlay,
not a standalone generator.
DiffGRM must retain forward noising and adaptive masked-position filling; RPG's
32-position OPQ cache is not compatible with DiffGRM's four-position OPQ4
identity and must never be cropped or silently converted.

## Last verified local release evidence

The 1.4 development tree passed:

- focused evidence-bundle, object-store, registry, comparison, and CLI tests:
  `23 passed`;
- full tests: `238 passed, 6 skipped`;
- resource-package verifier: PASS;
- contract-registry verifier: PASS with 11 canonical contracts, 11 positive
  fixtures, 12 typed-negative fixtures, and 14 declared dependency edges;
- Sprint 2 verifier: PASS with exact RPG migration parity and typed
  regeneration-required outcomes for DiffGRM/LLaDA legacy prepared artifacts;
- 1.2 execution/report/SDK legacy closure and fifteen-route migration matrix:
  PASS;
- 1.3 ecosystem verifier: PASS with SDK `0.2.0`, five native payload families,
  six composable profiles, five positive fixtures, seven typed negatives,
  no-plugin core validation, and external `reference-parallel` installation;
- 1.4 evidence-system verifier: PASS with three positive immutable bundles,
  three typed negative fixtures, one embedded CAS object, seven hash-only
  objects, supersession, quarantine/rebuild, compatible comparison, typed
  incompatible-comparison rejection, and SQLite delete/rebuild parity;
- 1.4 CLI CPU baseline verifier: PASS under the 20% review policy; seven-repeat
  medians are 5.098 ms bundle build, 4.226 ms verify, 8.374 ms registry add,
  5.051 ms compare, 3.953 ms list, and 10.041 ms rebuild;
- release-metadata verifier: PASS;
- architecture inventory verifier: PASS with 176 schema IDs, 11 canonical
  contracts, 9 profiles, 6 generator routes, 9 static-mapping routes, and 15
  canonical evidence edges;
- release archive build: PASS;
- extracted archive smoke: PASS;
- G8 isolated `sidinspector==1.4.0.dev0` install and deterministic archive
  rebuild: PASS;
- RPG non-AR bridge verifier: PASS, including Beauty v1 regression, generic v2
  positive fixture, typed duplicate-selection failure, and the hash-bound CPU
  runner/export smoke;
- DiffGRM staged verifier: PASS, including source-identity preflight,
  dataset-neutral positive fixture, and ten typed expected failures; the
  independent external-bundle CLI and its v2 binding/negative tests also pass;
- LLaDA-Rec verifier: PASS, including the formal tokenizer, recoverable
  10,000-step generator, five-bucket checkpoint smoke, typed ancestry failure,
  and external 250-episode native v2 diagnostic;
- manifest: 288 rows, 285 public rows, 0 pending;
- current public package surface: 480 files.

The development archive SHA-256 is intentionally reported by the final build
command rather than embedded in this hash-sensitive source tree. Rebuild it
after any source or documentation change.

## Required verification commands

Run from the repository root:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
python3 -m pytest -q
python3 tools/verify_sidscope_resource_package.py
python3 tools/verify_sidscope_contract_registry.py
python3 tools/verify_sidscope_sprint2_contracts.py
python3 tools/verify_sidscope_1_2_closure.py
python3 tools/verify_sidscope_1_2_legacy_migration_matrix.py
python3 tools/verify_sidscope_1_2_cli_baseline.py
python3 tools/verify_sidscope_1_3_plugin_ecosystem.py
python3 tools/verify_sidscope_1_4_evidence_system.py
python3 tools/verify_sidscope_1_4_cli_baseline.py
python3 tools/build_sidscope_release_candidate_archive.py \
  --output /tmp/sidscope-v1.4.0.dev0.zip
python3 tools/smoke_sidscope_release_candidate_archive.py \
  /tmp/sidscope-v1.4.0.dev0.zip
python3 tools/run_sidscope_g8_fresh_env_smoke.py \
  --archive /tmp/sidscope-v1.4.0.dev0.zip
```

The release checks are CPU-only. A new GPU run is not required to reverify the
already closed RPG evidence. GPU work is required only for a newly scoped
trained route such as LLaDA-Rec.

The separate public URL gate passed for `v1.1.0` and should be rerun after any
future public release-surface change:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/sidscope.git \
  --ref v1.1.0 \
  --result-json /tmp/sidscope_public_url_smoke.json
```

## Published release record

No additional internal implementation is required for the agreed 1.1.0
boundary. Publication is closed as follows:

1. annotated tag `v1.1.0` created and pushed;
2. release commit `a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3`
   published to `sidscope/main`;
3. unauthenticated public URL smoke passed against the tag;
4. final tag, commit, URL, archive checksum, and transcript are recorded in
   `docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md`.

RPG, DiffGRM VG/Steam, TIGER/DACT, and LLaDA-Rec VG trained/released-checkpoint
closure are complete in 1.1.1.dev0. ISD immutable-source/data/checkpoint closure
remains a post-1.1.0 maintenance item. These changes must not silently alter the
immutable 1.1.0 claim.

## Resume protocol

1. Read this file, `docs/V1_2_TO_V2_ROADMAP.md`, `docs/CONTRACT_REGISTRY.md`,
   `docs/COMPATIBILITY.md`, the two conformance documents,
   `docs/VALIDATED_ADAPTERS.md`, the generator coverage CSV,
   `docs/SIDSCOPE_MAINTENANCE.md`, and the release checklist/packet.
2. Verify the live Git and package state before making claims.
3. Inspect the release manifest and run focused tests before changing adapter
   status.
4. Preserve unrelated worktree changes; never clean them destructively.
5. Keep the submitted-paper freeze separate from software maintenance.
6. Report outcomes as `LOCAL_RELEASE_READY` and `PUBLIC_RELEASED` separately.

Expected status at this handoff:

```text
LOCAL_DEVELOPMENT_READY_1_1_1_DEV0: PASS
PUBLIC_RELEASED_1_1_1: NO
PUBLIC_RELEASED_1_1_0: YES
PUBLIC_RELEASE_TAG_1_1_0: v1.1.0
PUBLIC_RELEASE_COMMIT_1_1_0: a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3
LATTE_PSID_NAMED_ADAPTER: PASS_G0_G5
RPG_NAMED_ADAPTER: PASS_G0_G5
DIFFGRM_VG_NAMED_ADAPTER: PASS_G0_G5
DIFFGRM_STEAM_NAMED_ADAPTER: PASS_G0_G5
DACT_TIGER_NAMED_ADAPTER: PASS_G0_G5
TOIS_FROZEN_SUBMISSION: UNCHANGED_OUT_OF_SCOPE
```
