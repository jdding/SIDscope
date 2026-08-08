# SIDScope

SIDScope is a resource package for auditing semantic-ID tokenizer artifacts
before training or evaluating a downstream generative recommender. It does not
train a tokenizer or generator. It checks an existing `item_id -> SID` mapping
plus item metadata and interactions, then reports artifact-level diagnostics,
candidate-exposure probes, and bounded trace-accounting evidence.

Implementation note: the Python import package remains `sidinspector` for
compatibility with the released diagnostic code.

## What It Reports

- D1 utilization: per-level code usage, entropy, and imbalance.
- D2 aliasing: full-code and prefix collision profile.
- D3 neighborhood alignment: whether SID prefixes recover interaction
  co-occurrence neighborhoods.
- D4 popularity allocation: head/mid/tail capacity allocation.
- D5 structural cost: SID length, unique full IDs, and active prefix counts.
- D6 churn: optional refresh-to-refresh SID stability.

## Install

The release verifier is CPU-only. It was checked with Python 3.9, and should run
on Python 3.9+ with the dependencies in `pyproject.toml` / `requirements.txt`.
No GPU is required for the bundled verifier, quickstart, or D1-D6 diagnostics;
GPU use belongs to external tokenizer training pipelines, not to SIDScope's
artifact inspection step.

```bash
python3 -m pip install -e .
```

This installs the `sidinspector` package from the repository's `src/` layout.

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
manifests. Compact source summaries and frozen outputs for all ten manuscript-facing
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
`docs/SIDSCOPE_RELEASE_CHECKLIST.md`. The local release-candidate changelog is
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
command validates the eight-route source/license/config inventory, checks the
frozen ReSOT C0-C5 report, and reruns a public fixture that must fail C1 only.
The second deterministically rebuilds the ReSOT walkthrough from compact public
inputs. The upstream ReSOT archive and normalized parquet files are not
redistributed.

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
python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1-release-candidate.zip
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1-release-candidate.zip
python3 tools/run_sidscope_g8_fresh_env_smoke.py --archive /tmp/sidscope-v1-release-candidate.zip
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
  --repo-url https://github.com/jdding/SIDscope.git \
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
