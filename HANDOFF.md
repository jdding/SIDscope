# SIDScope 1.1 Development Handoff

Last updated: 2026-08-28

## Executive status

SIDScope 1.1.0 is locally release-ready and publicly released. The package
version is `1.1.0`; the local tests, resource-package verifier, deterministic
archive smoke, G8 clean-environment installation, and unauthenticated public
URL smoke have passed. Annotated tag `v1.1.0` resolves to
`a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3` on the public `main` branch.

Latte/PSID is the first configuration-bound named generator adapter admitted
under the complete G0--G5 protocol. The other generator routes remain useful,
typed partial integrations and must retain their documented gate labels.

The submitted TOIS manuscript is a frozen, separate repository. Nothing in
SIDScope 1.1 may be written back into that submission before an explicitly
authorized revision phase.

## Canonical development surface

- Repository: the standalone `SIDScope-v1.1` worktree, not the historical
  `SIDInspector` workspace.
- Branch: `codex/sidscope-v1.1`.
- Upstream tracking branch: `sidscope/main`.
- TOIS-submission software/resource base, public `v1.0.2`:
  `6ae5c4f02da3eae0cf187683d9af4c7c66e8cfa0`.
- Last implementation commit before this handoff document:
  `3f46f0371a5a85a05ce0ba93b7343998a7def888`.
- Version: `1.1.0` in both `pyproject.toml` and `setup.py`.
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

## Generator-route gate status

The machine-readable authority is
`docs/reproducibility/generator_adapter_coverage.csv`.

| Route | Current gate state | Allowed description | Next closure |
| --- | --- | --- | --- |
| Latte / PSID | G0--G5 pass | `named_adapter` | Maintain v2 compatibility and rerun both public real smoke bundles for every release archive. |
| RPG | Real G0/G1 pass; G2--G4 fixture; G5 partial | `close_named_adapter` | Run trained parallel/unordered decoding from a checkpoint or fully recorded training output and export real G2--G5 evidence. |
| TIGER / DACT | G1--G5 pass; G0 blocked by absent upstream code/asset license | `close_named_adapter` | Obtain explicit reuse permission; then rerun the 500-target primary with ancestry export before promotion. |
| LLaDA-Rec | G2--G4 adaptive-unmasking fixture; G0 blocked and G1/trained evidence pending | `close_named_adapter` | Obtain an explicit source license plus fixed tokenizer/checkpoint assets; run real G1 and trained G4--G5. |
| Item-Supported Decoding | Fail-closed overlay contract and exact-function smoke; G0 blocked, G1 fixture, G5 partial | `close_named_adapter` | Obtain an immutable official revision and license; bind data/checkpoints and export a real overlay trace. |
| ChronoSID | Official versioned source/assets unavailable | `watch_official_source` | Keep on source watch. |

RPG must retain unordered token-set identity and graph-valid completion; it
must never be converted into a TIGER-style autoregressive prefix trace.
LLaDA-Rec must retain diffusion/remasking state. ISD remains a decoder overlay,
not a standalone generator.

## Last verified local release evidence

The exact working tree containing the three implementation commits above
passed:

- full tests: `118 passed, 6 skipped`;
- resource-package verifier: PASS;
- release archive build: PASS;
- extracted archive smoke: PASS;
- G8 isolated `sidinspector==1.1.0` install and verification: PASS;
- manifest before this handoff row: 175 rows, 172 public rows, 0 pending;
- archive contents before this handoff row: 244 public files.

Because this document updates the public manifest, a resumed session must use
the commands below to obtain the current archive counts and SHA-256. Treat the
command results, not the historical counts above, as current release evidence.

## Required verification commands

Run from the repository root:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
python3 -m pytest -q
python3 tools/verify_sidscope_resource_package.py
python3 tools/build_sidscope_release_candidate_archive.py \
  --output /tmp/sidscope-v1.1.0.zip
python3 tools/smoke_sidscope_release_candidate_archive.py \
  /tmp/sidscope-v1.1.0.zip
python3 tools/run_sidscope_g8_fresh_env_smoke.py \
  --archive /tmp/sidscope-v1.1.0.zip
```

The checks are CPU-only. A new GPU run is not required to publish the already
verified bounded trained evidence. A GPU is required only for a newly scoped
trained-route closure such as RPG G2--G5.

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

RPG trained closure, TIGER/DACT license closure, LLaDA-Rec real trained
evidence, ISD immutable-source closure, and ChronoSID source availability are
post-1.1.0 maintenance items unless the user explicitly changes the release
scope. They must not silently delay or inflate the 1.1.0 claim.

## Resume protocol

1. Read this file, `docs/V1_1_ROADMAP.md`, the two conformance documents,
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
LOCAL_RELEASE_READY: PASS
PUBLIC_RELEASED: YES
PUBLIC_RELEASE_TAG: v1.1.0
PUBLIC_RELEASE_COMMIT: a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3
LATTE_PSID_NAMED_ADAPTER: PASS_G0_G5
RPG_TRAINED_G2_G5: OPEN_POST_1_1_0
TOIS_FROZEN_SUBMISSION: UNCHANGED_OUT_OF_SCOPE
```
