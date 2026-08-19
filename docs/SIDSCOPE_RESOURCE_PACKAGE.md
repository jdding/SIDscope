# SIDScope Resource Package

Status: local reviewer-package contract for the TOIS journal extension
Last updated: 2026-08-19

SIDScope is the V1 resource-paper layer on top of the SIDInspector toolkit. The
package is designed to let reviewers inspect Semantic-ID artifacts, run small
diagnostic examples, and trace paper-facing claims to compact evidence
snapshots without requiring private datasets, GPUs, or AutoDL access.

## Package Contents

Reviewer-facing contents:

- `src/sidinspector/`: importable Python package for adapter normalization,
  preflight validation, D1-D6 diagnostics, optional candidate-exposure probes,
  and D7 trace labeling.
- `examples/`: CPU-only toy and reviewer quickstart examples.
- `docs/`: adapter contracts, diagnostic definitions, reproducibility matrix,
  SIDScope datasheet, limitations, changelog, public-release packet, and
  maintenance/versioning plan.
- `docs/reproducibility/`: compact paper-evidence snapshots.
- `docs/reproducibility/d3_catalog_dependence_summary.json` and
  `d3_protocol_sensitivity.json`: dependence and bounded-parameter checks for
  the D3 construct-calibration claim.
- `docs/reproducibility/g22_handoff_uncertainty.json`: paired user-bootstrap
  intervals and gate probabilities for the fixed DACT lifecycle case.
- `docs/reproducibility/sidscope_release_candidate_manifest.csv`: the
  machine-readable release-candidate package boundary.
- `tools/verify_sidscope_resource_package.py`: package contract verifier.
- `tools/build_sidscope_release_candidate_archive.py`: release-clean archive
  builder from manifest-approved paths.
- `tools/smoke_sidscope_release_candidate_archive.py`: extraction smoke test
  for archive-without-git reviewer checks.
- `tools/run_sidscope_sampled_regeneration.py`: sampled regeneration driver.
- `tools/run_sidscope_usage_demo.py`: G14 resource-use walkthrough that turns
  compact artifact diagnostics into triage decisions.
- `tools/verify_adapter_conformance_assets.py`: validates the source inventory,
  eight C0--C5 route reports, and a directly runnable negative fixture.
- `docs/reproducibility/d7_labeled_trace_rows.csv.gz`: 125,000 deidentified
  D7 beam-label rows across five trained/released-checkpoint cases.
- `tools/verify_sidscope_d7_labeled_trace_release.py`: verifies the frozen
  trace-row hash, schema, row/trace counts, and label distributions.
- `tools/build_resot_resource_walkthrough.py`: rebuilds the ReSOT
  intake-to-promotion walkthrough from compact public inputs.
- `tools/run_sidscope_public_url_smoke.py`: final public URL/tag smoke runner
  to use after the reviewer-accessible release surface exists.

Intentionally omitted:

- raw Amazon/P5/HF datasets;
- AutoDL payloads, returned archives, SSH targets, and cloud logs;
- model checkpoints, tensor dumps, parquet caches, pickle/numpy arrays, and
  identifying target-level joined trace CSVs;
- private paper-chain provenance and LaTeX/arXiv packaging artifacts.

## Install

```bash
python3 -m pip install --upgrade "pip>=21.3"
python3 -m pip install -e .
```

Editable installation requires pip 21.3 or newer. The package is CPU-only for
the bundled checks. GPU work belongs to upstream
tokenizer/generator training pipelines and is not required for SIDScope
inspection.

## Quickstart

```bash
python3 examples/run_reviewer_quickstart.py --output-dir /tmp/sidscope_quickstart
```

Expected outputs:

```text
/tmp/sidscope_quickstart/preflight_summary.json
/tmp/sidscope_quickstart/diagnostics/d1_utilization.csv
/tmp/sidscope_quickstart/diagnostics/d2_collision.csv
/tmp/sidscope_quickstart/diagnostics/d3_alignment.csv
/tmp/sidscope_quickstart/diagnostics/d4_head_tail.csv
/tmp/sidscope_quickstart/diagnostics/d5a_deployment_cost.csv
```

This is a usability example. It is not claimed to reproduce the paper's full
artifact matrix.

## Sampled Regeneration

Run the bounded regeneration path:

```bash
python3 tools/run_sidscope_sampled_regeneration.py --output-dir /tmp/sidscope_sampled_regeneration
```

This command runs:

1. reviewer quickstart on bundled sample data;
2. reproducibility-matrix validation over compact evidence snapshots.

The command writes `sampled_regeneration_result.json` to the output directory.
It verifies the release-path contract, not full regeneration of large upstream
artifacts.

## Usage Demo

Run the G14 resource-use walkthrough:

```bash
python3 tools/run_sidscope_usage_demo.py
```

Expected public outputs:

```text
docs/SIDSCOPE_USAGE_DEMO.md
docs/reproducibility/g14_usage_demo_decisions.csv
docs/reproducibility/g14_usage_demo_summary.json
```

The demo answers a reviewer-facing resource question: given compact SID artifact
diagnostics, which rows are reasonable candidates for promotion, which rows
should remain controls or stress cases, and which rows require manual review?
It is not a final downstream recommendation-quality claim.

## Adapter Conformance And ReSOT Walkthrough

```bash
python3 tools/verify_adapter_conformance_assets.py
python3 tools/verify_resot_resource_walkthrough.py
```

The conformance protocol separates source and license declaration (C0), table
coherence (C1), joins (C2), bounded D1-D5 execution (C3), commands and pinned
input hashes (C4), and paper-matrix promotion (C5). ReSOT is the current full
paper-counted execution. Other inventory rows retain historical preflight or
snapshot labels until the same standard manifest is run for them. The negative
fixture fails exactly C1, demonstrating that a syntactically readable mapping
is not promoted when its full SID disagrees with its level columns.

## Package Verification

```bash
python3 tools/verify_sidscope_resource_package.py
python3 tools/verify_sidscope_d7_labeled_trace_release.py
```

The verifier checks required package files, reviewer docs, compact evidence
snapshots, quickstart executability, sampled regeneration, release-candidate
manifest consistency, package boundary rules, and forbidden content tokens in
the public-package file set. The D7 verifier separately checks that the released
beam rows contain no user/item IDs, raw SID paths, scores, or checkpoint fields
and reproduce the five case-level label distributions. These are the current
local package checks.

Run the claim-ledger boundary verifier:

```bash
python3 tools/verify_sidscope_claim_ledger.py --result-json /tmp/sidscope_claim_ledger_verification.json
```

This validates claim status labels, forbidden-claim boundaries, missing evidence
paths, and private-path leakage in `experiments/v1_evidence_chain/CLAIM_LEDGER.md`.
When `tools/verify_sidscope_resource_package.py` runs from an extracted release
archive without `.git`, it invokes the same verifier with `--package-mode`.
Package mode still requires shipped public-package evidence paths to exist, but
records full-repository experiment evidence that is intentionally omitted from
the zip under `package_omitted_evidence_paths`.

Run the realistic tutorial validator:

```bash
python3 tools/run_sidscope_realistic_tutorial.py --output-dir /tmp/sidscope_realistic_tutorial
```

Run the local G8 clean-extract smoke:

```bash
python3 tools/run_sidscope_g8_fresh_env_smoke.py --archive /tmp/sidscope-v1-release-candidate.zip
```

This extracts the release archive into a temporary directory, creates a
temporary virtual environment, installs the package, and reruns the reviewer
checks. It is stronger than the no-git archive smoke, but still does not verify
public URL, release tag, or hosted archive accessibility. The clean
`jdding/sidscope` `main` surface has a separate public URL smoke gate and must
be rechecked after public-package changes.

The final public URL smoke for the active release candidate is:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/sidscope.git \
  --ref main \
  --result-json /tmp/sidscope_public_url_smoke.json
```

This command clones the public release surface and reruns the reviewer package
checks from that checkout. Rerun it if the public tag or reviewer-facing release
surface changes.

This is the R509 tutorial/example check. It repeats the reviewer quickstart and
asserts that adapter normalization, preflight validation, and D1-D5 CSV outputs
all produce non-empty, interpretable artifacts.

Build a local release-candidate archive:

```bash
python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1-release-candidate.zip
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1-release-candidate.zip
```

The archive builder uses `git ls-files` plus
`docs/reproducibility/sidscope_release_candidate_manifest.csv`; it includes
only `public_package=yes` manifest paths and refuses forbidden package-boundary
files or forbidden public-package content tokens. The smoke test extracts the
archive without `.git` metadata and runs the package verifier plus sampled
regeneration from the extracted package.

## Release Candidate Checklist

Use `docs/SIDSCOPE_RELEASE_CHECKLIST.md` before any public archive, tag, or
reviewer URL is created. The checklist separates the local package contract
from public release requirements:

- local G8 verifier pass;
- public or reviewer-accessible URL;
- release tag or archive checksum;
- canonical G9 claim-to-artifact ledger for the current paper artifact registry;
- G8 fresh-environment smoke.

## Evidence Levels

SIDScope separates evidence into three reviewer-visible levels:

- `fully runnable`: bundled examples, quickstart, preflight, metrics, and
  sampled regeneration;
- `tracked snapshot`: compact CSV/JSON evidence snapshots used for paper tables
  where raw artifacts are too large to ship;
- `provenance only`: run records that explain how evidence was produced but do
  not imply fresh-checkout regeneration.

Paper claims must preserve this separation.

## Current Boundary

This package supports resource and evaluation claims about artifact inspection,
prefix-candidate construct calibration, G9 disjoint-user ranking checks,
bounded fixed-reranker Recall@20/NDCG@20 anchors, G10 non-prefix
hard-negative sampled-ranking anchors, bounded public-beam D7 accounting, G20
trained trie-constrained path-versus-item accounting, G21 released-checkpoint
trace portability, a deidentified 125,000-row D7 label surface, and one G22
released-refresh handoff. It does not claim
final trained downstream recommendation improvement, a generator failure
mechanism, D1-D5 trained-generator predictivity, universal ranking-quality prediction
across candidate protocols, or a new Semantic-ID tokenizer method.
