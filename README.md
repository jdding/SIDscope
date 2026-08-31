# SIDScope

SIDScope is evolving into the conformance and observability layer for
Semantic-ID and generative recommender systems. It owns the evidence pipeline
from adapter integration through canonical contracts, native trace capture,
diagnostic evaluation, conformance verification, and immutable evidence. It
does not own or reimplement upstream recommendation methods or training.

The 1.1 line remains the verified resource-package baseline: it audits
existing `item_id -> SID` mappings, validates configuration-bound generator
adapters, and publishes artifact-level diagnostics, candidate-exposure probes,
method-faithful trace accounting, and bounded evidence. The approved target
architecture is documented in `docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md`; the
implementation sequence through 2.0 is in `docs/V1_2_TO_V2_ROADMAP.md`.
Release numbering and compatibility are governed by `docs/VERSIONING.md` and
`docs/COMPATIBILITY.md`.

Implementation note: the distribution and historical import package remain
`sidinspector` for compatibility. New integrations should use the curated
`sidscope` Python facade; direct historical imports remain supported for replay.

## What It Reports

- D1 utilization: per-level code usage, entropy, and imbalance.
- D2 aliasing: full-code and prefix collision profile.
- D3 neighborhood alignment: whether SID prefixes recover interaction
  co-occurrence neighborhoods.
- D4 popularity allocation: head/mid/tail capacity allocation.
- D5 structural cost: SID length, unique full IDs, and active prefix counts.
- D6 churn: optional refresh-to-refresh SID stability.
- D7 trace accounting: generated-path validity, ambiguity, and item resolution.

## Install

The release verifier is CPU-only. It was checked with Python 3.9, and should run
on Python 3.9+ with the dependencies in `pyproject.toml` / `requirements.txt`.
Editable installation uses the PEP 660 path and requires pip 21.3 or newer;
stock Python 3.9 installations with older pip should upgrade it first.
No GPU is required for the bundled verifier, quickstart, or D1-D7 audits;
GPU use belongs to external tokenizer training pipelines, not to SIDScope's
artifact inspection step.

```bash
python3 -m pip install --upgrade "pip>=21.3"
python3 -m pip install -e .
```

This installs the `sidinspector` package from the repository's `src/` layout.
It also installs the stable `sidscope` command facade. The first shared
contract slice can be checked without loading any optional adapter runtime:

```bash
sidscope contract validate \
  --type source-identity \
  --input examples/source_identity_fixture/source_identity.json
```

The active `1.7.0.dev0` line retains the eleven canonical contracts from source
identity through evidence index, Adapter SDK `0.2.0-alpha`, lazy external
plugins, five registered native payload families, and composable profiles. It
adds immutable EvidenceBundle v1 objects, a rebuildable SQLite registry,
supersession, privacy-gated admission, and compatibility-aware comparison.
Version 1.5 adds governed static-mapping, generator, overlay and release
profiles, dataset/evaluation/privacy descriptors, an independent submission
checker, and deterministic report-derived status/result indexes.
Version 1.6 adds executable compatibility intervals, hash-bound migration
records for every 1.1.1 route, a frozen candidate Python/CLI inventory,
independent external-plugin onboarding proof, and a compatible cross-family
EvidenceBundle comparison. It is a hardening release: no method or training API
enters SIDScope.
Version 1.7 stabilizes the public contract surface: all 45 published schema IDs
are discoverable with an owner and semantic validator, every CLI JSON output
uses either the validated CLI envelope or its domain artifact contract, JSON
Schema validation always precedes Python
semantic validation, and the deliberately small `sidscope` Python facade is
machine-inventoried. Existing artifact bytes and historical imports are not
rewritten.
The complete common path runs without optional adapter runtimes:

```bash
sidscope contract list
sidscope contract show --type dataset-identity
sidscope contract validate \
  --type dataset-identity \
  --input examples/dataset_identity_fixture/dataset_identity.json
python3 tools/verify_sidscope_sprint2_contracts.py
python3 tools/verify_sidscope_1_2_closure.py
python3 tools/verify_sidscope_1_3_plugin_ecosystem.py
python3 tools/verify_sidscope_1_5_conformance_ecosystem.py
python3 tools/verify_sidscope_1_6_hardening.py
python3 tools/verify_sidscope_1_7_stabilization.py
```

Public schema discovery and two-stage validation are available directly:

```bash
sidscope schema list
sidscope schema validate \
  --input examples/dataset_identity_fixture/dataset_identity.json
```

DatasetIdentity binds dataset/category/profile, ordered split identities,
catalog, target universe, and pseudonymous item identity. SIDSpaceIdentity
separately binds tuple structure, codebooks, offsets, special tokens, tokenizer
artifacts, collision and de-duplication semantics. PreparedDataset binds both
identities to normalized splits and artifact hashes. RPG migrates with exact
fixture parity; incomplete DiffGRM/LLaDA legacy prepared artifacts explicitly
require regeneration. Episode selection, run/checkpoint provenance, native
payload-bound traces, diagnostic/conformance reports, and deterministic
evidence indexing are now registered downstream contracts.

```bash
sidscope adapter preflight \
  --descriptor examples/canonical_pipeline_fixture/adapter_capabilities.json
sidscope trace validate \
  --input examples/canonical_pipeline_fixture/trace_envelope.json
sidscope evaluate \
  --trace examples/canonical_pipeline_fixture/trace_envelope.json \
  --selection examples/canonical_pipeline_fixture/episode_selection.json \
  --output /tmp/sidscope-diagnostic.json
sidscope verify \
  --report examples/canonical_pipeline_fixture/conformance_report.json
```

The common TraceEnvelope never substitutes for the bound method-native payload.
RPG is the first end-to-end canonical fixture. Other current routes retain
their legacy verifier authority and receive explicit regeneration dispositions;
no historical evidence or adapter status is rewritten. External adapters are
discovered lazily under `sidscope.adapters`; core verification works with the
plugin absent. EvidenceIndex remains the deterministic dependency inventory.
EvidenceBundle v1 is the independently versioned immutable package: the
SHA-256 object layout is authoritative and SQLite is only a disposable
projection. See `docs/EVIDENCE_BUNDLES_AND_REGISTRY.md`.

```bash
sidscope plugin list
sidscope trace payload list
sidscope trace payload validate \
  --input examples/native_trace_payload_fixtures/masked_diffusion.json
sidscope profile compose --profile family.masked_diffusion.v1
sidscope profile catalog
sidscope submission check \
  --root examples/conformance_ecosystem_fixture/submission/positive
```

The reference plugin under `examples/reference_adapter_plugin/` is an external
package proof, not a named-method result. See `docs/ADAPTER_PLUGIN_ECOSYSTEM.md`
and `docs/NATIVE_TRACE_PAYLOADS.md`.

### Optional Latte Tokenizer Intake

SIDScope's core artifact audits do not require tokenizer-training libraries.
When a workflow must execute the tokenizer-only Latte/PSID export path before
normalization, install the isolated optional environment:

```bash
python3 -m pip install -e '.[latte]'
```

This extra supplies `faiss-cpu` and `sentence-transformers`. Local Sentence-T5
checkpoints are passed directly to `SentenceTransformer`; SIDScope never
infers the model backend from directory-name fragments such as
`sentence-transformers`. The tokenizer-only intake does not require the
HuggingFace `datasets` package. A full upstream Latte training or evaluation
workflow may have additional dependencies and should remain in its own
hermetic environment.

## Run The Bundled Smoke Example

```bash
python3 examples/run_toy_diagnostic.py
```

Expected final line:

```text
Wrote SIDInspector toy diagnostic outputs to .../examples/toy_output
```

The example writes normalized parquet inputs and D1-D5 CSV reports under
`examples/toy_output/`.

## Reviewer Quickstart

The reviewer quickstart uses a small music-like export slice and exercises the
same command path a new adapter user would run: adapter normalization,
preflight validation, and D1-D5 CSV generation.

```bash
python3 examples/run_reviewer_quickstart.py
```

Expected outputs:

```text
examples/reviewer_quickstart_output/preflight_summary.json
examples/reviewer_quickstart_output/diagnostics/d1_utilization.csv
examples/reviewer_quickstart_output/diagnostics/d2_collision.csv
examples/reviewer_quickstart_output/diagnostics/d3_alignment.csv
examples/reviewer_quickstart_output/diagnostics/d4_head_tail.csv
examples/reviewer_quickstart_output/diagnostics/d5a_deployment_cost.csv
```

This quickstart is a usability example, not a reproduction of the paper tables.

## Paper Evidence Reproducibility

The paper-facing evidence map is tracked in
`docs/REPRODUCIBILITY_MATRIX.md` and `docs/reproducibility_matrix.csv`. It
separates evidence that is fully runnable from this release checkout from
evidence that depends on upstream public artifacts or saved local experiment
manifests. Compact source summaries and frozen outputs for all eight manuscript-facing
tables are under `docs/reproducibility/paper_table_sources/` and
`docs/reproducibility/paper_tables/`.

```bash
python3 tools/build_sidscope_paper_tables.py --output-dir /tmp/sidscope_paper_tables
python3 tools/verify_sidscope_paper_tables.py
python3 tools/verify_reproducibility_matrix.py
```

These commands deterministically rebuild the paper-table CSVs and compare them
row by row with the frozen snapshots. They do not retrain upstream tokenizers or
regenerate large local experiment caches that are intentionally omitted from
the release package.

For the SIDScope resource-package contract, see
`docs/SIDSCOPE_RESOURCE_PACKAGE.md`, `docs/SIDSCOPE_DATASHEET.md`,
`docs/SIDSCOPE_LIMITATIONS.md`, `docs/SIDSCOPE_MAINTENANCE.md`, and
`docs/SIDSCOPE_RELEASE_CHECKLIST.md`. Version and compatibility policies are
in `docs/VERSIONING.md` and `docs/COMPATIBILITY.md`. The local release-candidate changelog is
`docs/SIDSCOPE_CHANGELOG.md`; the public release preparation packet is
`docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md`.

Run the bounded sampled regeneration path:

```bash
python3 tools/run_sidscope_sampled_regeneration.py --output-dir /tmp/sidscope_sampled_regeneration
```

Run the resource-use walkthrough:

```bash
python3 tools/run_sidscope_usage_demo.py
```

This writes `docs/SIDSCOPE_USAGE_DEMO.md` plus compact
`docs/reproducibility/g14_usage_demo_*` outputs. It demonstrates artifact
triage and decision tracing, not final downstream model-quality prediction.

Run the adapter conformance and ReSOT intake-to-promotion checks:

```bash
python3 tools/verify_adapter_conformance_assets.py
python3 tools/verify_resot_resource_walkthrough.py
```

The C0-C5 protocol is documented in `docs/ADAPTER_CONFORMANCE.md`. The first
command validates the nine-route source/license/config inventory, checks the
frozen ReSOT C0-C5 report, and reruns a public fixture that must fail C1 only.
The second deterministically rebuilds the ReSOT walkthrough from compact public
inputs. The upstream ReSOT archive and normalized parquet files are not
redistributed.

Generator, diffusion, and decoder-overlay integrations follow the separate
G0-G5 protocol in `docs/GENERATOR_ADAPTER_CONFORMANCE.md`. Current route status
is machine-readable in
`docs/reproducibility/generator_adapter_coverage.csv`; reference traces and
tokenizer-only intake are not labeled as complete named-method adapters.

RPG now has a pinned source/license/asset audit, an independent unordered
token-set and graph-propagation contract, a deterministic CPU fixture with an
expected failure, a bounded smoke against the pinned official `RPG` class, and
a real official-code-derived Beauty OPQ cache whose 12,101 items pass
non-paper-counted C0--C5 and G1 identity round-trip:

```bash
PYTHONPATH=src python3 tools/verify_rpg_generator_adapter.py
```

See `docs/RPG_GENERATOR_ADAPTER.md`. The real cache, raw Amazon data, metadata,
embeddings, and normalized tables remain external. This is static mapping and
interoperability evidence, not a trained checkpoint result or a complete named
adapter; the official code remains CC BY-NC 4.0 and is not vendored into
SIDScope.

Latte/PSID now has a pinned source and asset audit, a real
official-code-derived Musical Instruments `.sem_ids` cache bound by hashes, a
C0--C5 normalized intake report, a deidentified CPU fixture, and an
official-source tokenizer/aggregation smoke:

```bash
PYTHONPATH=src python3 tools/verify_latte_psid_adapter.py
```

Checkpoint-owning downstream projects can validate a bounded, deidentified
trained trace before returning evidence to SIDScope:

```bash
PYTHONPATH=src python3 tools/verify_latte_psid_trained_trace_bundle.py \
  --bundle <trained-trace-bundle.json>
```

The trained handoff fails closed on aggregate-only summaries, missing beam
ancestry or step log-probabilities, raw identities, labels, private paths, and
unbounded exports. Schema v2 preserves PAD/`-1` early-ended beams and PSID's
raw invalid top-k rank slots, while Latte retains dense post-aggregation ranks.

Two checkpoint-backed five-episode Amazon Video Games smoke bundles are
included for direct CPU verification:

```bash
PYTHONPATH=src python3 tools/verify_latte_psid_trained_trace_bundle.py \
  --bundle examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json
PYTHONPATH=src python3 tools/verify_latte_psid_trained_trace_bundle.py \
  --bundle examples/latte_psid_trained_trace_real_smoke/latte_amazon_vg_1_per_bucket_s2024.json
```

Both methods also pass external 250-episode diagnostics whose hashes and
verifier summaries are frozen in
`docs/reproducibility/latte_psid_trained_trace_evidence.json`. This closes
G0--G5 for the recorded configurations and promotes Latte/PSID to a named
generator adapter.

The Amazon raw data, metadata text, sentence embeddings, generated cache, and
normalized tables are not redistributed because the audited dataset card does
not declare an explicit license identifier. See
`docs/LATTE_PSID_GENERATOR_ADAPTER.md`. Raw data, generated caches, and
checkpoints remain external; the public trained-trace fixtures contain only
normalized item identities and bounded deidentified decode state.

LLaDA-Rec now has a pinned source/license/asset audit, a masked-state adaptive
unmasking trace contract, a deidentified deterministic CPU fixture with a
typed remasking failure, and a smoke against the pinned official class methods:

```bash
PYTHONPATH=src python3 tools/verify_llada_rec_adapter.py
```

The audit found that the pinned inference implementation monotonically fills
confidence-selected masked positions; it does not remask filled positions.
The official repository has no released model, tokenizer cache, or training
output. Its `NOASSERTION` license state is retained as a non-redistribution
marker rather than an experiment gate. SIDScope therefore ships only its
independent contract and compact evidence and does not yet label this route a
complete named adapter. See `docs/LLADA_REC_DIFFUSION_ADAPTER.md`.

DACT/TIGER now has a released-asset G0--G5 report, an ordered-prefix and
parent-beam fixture, and a bounded replay of the official Tools `0.6_cf`
checkpoint:

```bash
PYTHONPATH=src python3 tools/verify_dact_tiger_adapter.py
```

G0--G5 pass. A refreshed 500-target, beam-50 constrained/unconstrained primary
retains ordered prefixes, parent ancestry, and step log-probabilities for all
25,000 rows per mode, promoting the released Tools configuration to a named
adapter. The absent explicit code/asset license remains a non-redistribution
marker, so SIDScope ships only hashes, compact/deidentified evidence, and its
independent fixture. See `docs/DACT_TIGER_GENERATOR_ADAPTER.md`.

ISD now has a paper-linked anonymous-source audit, a deterministic
decoder-overlay fixture, and an exact-function smoke over the official
`support_maps`, prefix-selection, and final-RRF functions:

```bash
PYTHONPATH=src python3 tools/verify_isd_adapter.py
```

The contract retains base candidate scores and parents, best item-support
ranks, RRF pruning survival, collision-aware resolution, and final reranking
without inserting provider-only items. The anonymous artifact exposes no
immutable repository revision and ships no data, checkpoint, cache, or trace,
so this is bounded interoperability evidence rather than a named adapter. Its
`NOASSERTION` state is only a non-redistribution marker. See
`docs/ISD_DECODER_OVERLAY_ADAPTER.md`.

Version 1.1.0 is prepared on `codex/sidscope-v1.1`; see
`docs/V1_1_ROADMAP.md`. The TOIS submission remains frozen outside this
software worktree until an editorial revision request.

Run the local reviewer-resource package verifier:

```bash
python3 tools/verify_sidscope_resource_package.py
```

Run the claim-ledger boundary verifier:

```bash
python3 tools/verify_sidscope_claim_ledger.py --result-json /tmp/sidscope_claim_ledger_verification.json
```

Build a release-clean local archive from the manifest-approved package paths:

```bash
python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1.1.0.zip
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1.1.0.zip
python3 tools/run_sidscope_g8_fresh_env_smoke.py --archive /tmp/sidscope-v1.1.0.zip
```

These checks validate the reviewer quickstart, compact evidence snapshots,
release-candidate manifest, package boundary, and local clean-extract install
smoke. They do not regenerate raw upstream tokenizer artifacts or large local
experiment caches, and they do not replace the final public URL/tag
accessibility check.

After a public reviewer URL or release tag exists, run the final public URL
smoke:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/sidscope.git \
  --ref main \
  --result-json /tmp/sidscope_public_url_smoke.json
```

Run the realistic tutorial validator:

```bash
python3 tools/run_sidscope_realistic_tutorial.py --output-dir /tmp/sidscope_realistic_tutorial
```

This repeats the reviewer quickstart and validates that the normalized adapter
outputs, preflight JSON, and D1-D5 CSVs are non-empty and interpretable.

## Optional Downstream Probe

SIDScope also includes an optional fixed-reranker probe for users who want
to test whether SID prefixes recover held-out targets under a fixed protocol.
This is candidate-exposure evidence, not a trained generator evaluation, and is
kept outside the core D1-D5 diagnostics.

```bash
python3 -m sidinspector.downstream_probe \
  --manifest path/to/probe_manifest.csv \
  --output-dir path/to/probe_output
```

The manifest needs one row per SID artifact with `sid_assignments` and
`interactions` paths; optional `dataset`, `method`, and `label` columns select
or name rows. The output contains per-artifact summary metrics, per-user
bootstrap inputs, and D3-vs-recovery correlations.

## Normalize LETTER/LC-Rec Style JSON Indexes

For releases that store semantic IDs as JSON token lists such as
`{"item_id": ["<a_1>", "<b_7>"]}`, use the bundled normalizers:

```bash
python3 -m sidinspector.adapters.letter \
  --index-json path/to/Instruments.index.json \
  --item-json path/to/Instruments.item.json \
  --inter-json path/to/Instruments.inter.json \
  --dataset-name Instruments \
  --method letter_official_rqvae \
  --output-dir runs/letter_instruments

python3 -m sidinspector.adapters.lcrec \
  --index-json path/to/Instruments.index.json \
  --item-json path/to/Instruments.item.json \
  --inter-json path/to/Instruments.inter.json \
  --dataset-name LCRec_Instruments \
  --output-dir runs/lcrec_instruments
```

The adapter emits the same normalized `sid_assignments.parquet`,
`item_metadata.parquet`, and `interactions.parquet` files used by preflight and
D1-D5 metrics.

## Use Your Own Tokenizer Export

If your tokenizer already exports one row per item:

```csv
item_id,sid_0,sid_1,sid_2
1,12,3,91
2,12,8,17
```

normalize it:

```bash
python3 examples/minimal_adapter.py \
  --input-csv path/to/item_codes.csv \
  --output-dir runs/my_tokenizer \
  --method my_tokenizer \
  --dataset my_dataset
```

Prepare `item_metadata.parquet` and `interactions.parquet`, then run:

```bash
python3 -m sidinspector.preflight \
  --sid-assignments runs/my_tokenizer/sid_assignments.parquet \
  --item-metadata runs/my_tokenizer/item_metadata.parquet \
  --interactions runs/my_tokenizer/interactions.parquet \
  --run-metric-smoke

python3 -m sidinspector.metrics \
  --sid-assignments runs/my_tokenizer/sid_assignments.parquet \
  --item-metadata runs/my_tokenizer/item_metadata.parquet \
  --interactions runs/my_tokenizer/interactions.parquet \
  --output-dir runs/my_tokenizer/diagnostics
```

See `docs/ADAPTER_TEMPLATE.md` for the required table contract,
`docs/ADAPTER_CONFORMANCE.md` for promotion requirements, and
`docs/reproducibility/sidscope_source_license_config_inventory.csv` for the
current named routes. See `docs/PROBE_INTERPRETATION.md` for the
signal-to-risk-to-next-check guide for D1-D7.

## Development Checks

```bash
python3 -m pip install -e .
python3 -m pytest -q
python3 tools/verify_sidscope_resource_package.py
python3 tools/verify_reproducibility_matrix.py
```

The package verifier checks importability, the toy diagnostic, reviewer
quickstart, compact evidence, and the reproducibility-matrix index from a clean
checkout. On a typical laptop CPU, the bundled checks should finish in seconds
to a few minutes, depending mostly on first-time dependency imports.
