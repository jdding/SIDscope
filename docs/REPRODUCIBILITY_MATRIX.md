# Resource Reproducibility Matrix

This document connects the paper evidence to the released SIDScope
resource. It is intentionally stricter than the quickstart: the quickstart
shows that the package runs, while this matrix shows where each paper-facing
evidence block comes from and whether a reviewer can regenerate it from the
release repository, an upstream public artifact, or a saved local manifest.

The machine-readable version is `docs/reproducibility_matrix.csv`. Compact
evidence snapshots are tracked under `docs/reproducibility/`.

All ten manuscript-facing table CSVs can be rebuilt from released compact summaries:

```bash
python3 tools/build_sidscope_paper_tables.py --output-dir /tmp/sidscope_paper_tables
python3 tools/verify_sidscope_paper_tables.py
```

The second command compares headers and rows against the frozen snapshots under
`docs/reproducibility/paper_tables/`.

## Status Labels

- `fully runnable from release repo`: all inputs are included in the public
  repository and the command can be run directly after installation.
- `adapter released; upstream artifact required`: SIDScope code is
  released, but the method's official item-index artifact must be downloaded
  from the upstream method release.
- `tracked evidence snapshot`: the paper value is preserved in a tracked CSV,
  while large/raw experiment artifacts are not shipped in the release repo.
- `raw local artifacts not shipped`: large generated artifacts, downloaded
  datasets, or local experiment caches are intentionally omitted from the
  reviewer package.

## Matrix

| Paper evidence | Source artifact | Command | Output | Runtime | Release status |
|---|---|---|---|---|---|
| SIDScope manuscript Tables 1--10 | `docs/reproducibility/paper_table_sources/*.csv`; compact evidence snapshots, source inventory, conformance records, walkthrough records, G20--G21 trained-trace summaries, and the G22 lifecycle-handoff summary | `python3 tools/build_sidscope_paper_tables.py --output-dir /tmp/sidscope_paper_tables` then `python3 tools/verify_sidscope_paper_tables.py` | ten deterministic CSV tables with 86-row verification | CPU seconds | fully runnable from release repo; does not rerun upstream tokenizer or generator training |
| Release package verifier | tracked package files, examples, docs, tests | `python3 tools/verify_sidscope_resource_package.py` | package import, toy diagnostic, reviewer quickstart, unit tests | CPU seconds to minutes | fully runnable from release repo |
| SIDScope package verifier | tracked package files, SIDScope docs, sampled regeneration manifest, release-candidate manifest | `python3 tools/verify_sidscope_resource_package.py` | package import, reproducibility matrix validation, release-manifest validation, sampled regeneration | CPU seconds to minutes | fully runnable from release repo; local G8 contract verifier |
| SIDScope release-candidate manifest | `docs/reproducibility/sidscope_release_candidate_manifest.csv`; `docs/SIDSCOPE_RELEASE_CHECKLIST.md` | `python3 tools/verify_sidscope_resource_package.py --skip-sampled-regeneration` | manifest path, evidence-level, gate-status, and package-boundary validation | CPU seconds | fully runnable from release repo; corrected `sidscope/main` public URL smoke pending; rerun after changes |
| SIDScope canonical G9 table/figure ledger | `docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv`; `experiments/v1_evidence_chain/CLAIM_LEDGER.md` | `python3 tools/verify_sidscope_claim_ledger.py` | claim placement, source row, package-relative path, hash/regeneration-note validation | CPU seconds | tracked evidence snapshot; final TeX audit still required after manuscript writing |
| SIDScope release archive builder | `docs/reproducibility/sidscope_release_candidate_manifest.csv`; tracked public-package files | `python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1-release-candidate.zip` | release-clean zip archive plus SHA256 in command output | CPU seconds | fully runnable from release repo; rerun after package file changes |
| SIDScope release archive smoke | `/tmp/sidscope-v1-release-candidate.zip` from release archive builder | `python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1-release-candidate.zip` | extracted archive verifier and sampled regeneration pass without `.git` metadata | CPU seconds to minutes | fully runnable from release repo; approximates reviewer archive extraction |
| SIDScope sampled regeneration | `examples/reviewer_quickstart_data/*.csv`; `docs/reproducibility/sidscope_sampled_regeneration_manifest.csv` | `python3 tools/run_sidscope_sampled_regeneration.py --output-dir /tmp/sidscope_sampled_regeneration` | `/tmp/sidscope_sampled_regeneration/sampled_regeneration_result.json` and reviewer quickstart diagnostics | CPU seconds | fully runnable from release repo; does not regenerate raw upstream artifacts |
| SIDScope usage demo | `docs/reproducibility/table2_musical_diagnostic.csv`; `docs/reproducibility/official_adapter_metrics_snapshot.csv`; `docs/reproducibility/table1_evidence_catalog.csv`; `docs/reproducibility/extension_checks_snapshot.csv` | `python3 tools/run_sidscope_usage_demo.py` | `docs/SIDSCOPE_USAGE_DEMO.md`; `docs/reproducibility/g14_usage_demo_decisions.csv`; `docs/reproducibility/g14_usage_demo_summary.json` | CPU seconds | fully runnable from release repo; demonstrates artifact-triage decisions, not downstream quality |
| Adapter C0-C5 evidence | `docs/reproducibility/sidscope_source_license_config_inventory.csv`; `docs/reproducibility/conformance/*`; `examples/conformance_failure_fixture/*` | `python3 tools/verify_adapter_conformance_assets.py` | seven verified C0-C5 route reports, exact C1 failure fixture, and inventory evidence boundary | CPU seconds | fully runnable from release repo over compact evidence; source-dependent recomputation requires separately obtained upstream inputs |
| ReSOT resource walkthrough | `docs/reproducibility/resot_walkthrough_sources.json`; conformance reports; source inventory | `python3 tools/verify_resot_resource_walkthrough.py` | deterministic `docs/RESOT_RESOURCE_WALKTHROUGH.md` and JSON record | CPU seconds | fully runnable from release repo; compact source bundle traces omitted experiment records |
| Reviewer quickstart | `examples/reviewer_quickstart_data/*.csv` | `python3 examples/run_reviewer_quickstart.py --output-dir /tmp/sidinspector_quickstart` | `/tmp/sidinspector_quickstart/{preflight_summary.json,diagnostics/*.csv}` | CPU seconds | fully runnable from release repo; usability example, not paper-table reproduction |
| Toy diagnostic | `examples/sample_data/*.csv` | `python3 examples/run_toy_diagnostic.py --output-dir /tmp/sidinspector_toy` | `/tmp/sidinspector_toy/*.csv` and normalized parquet files | CPU seconds | fully runnable from release repo |
| Table 1 evidence catalog | `docs/reproducibility/table1_evidence_catalog.csv`; `docs/VALIDATED_ADAPTERS.md` | `python3 tools/verify_reproducibility_matrix.py` | matrix and evidence snapshots validated | CPU seconds | tracked evidence snapshot |
| Table 2 Musical diagnostic profile | `docs/reproducibility/table2_musical_diagnostic.csv`; `docs/reproducibility/rqmin_reference_snapshot.csv`; local `_gate0_artifacts` paths listed per row | `python3 -m sidinspector.metrics --sid-assignments <normalized/sid_assignments.parquet> --item-metadata <item_metadata.parquet> --interactions <interactions.parquet> --output-dir <metrics_dir>` | `d1_utilization.csv`, `d2_collision.csv`, `d3_alignment.csv`, `d4_head_tail.csv`, `d5a_deployment_cost.csv` | CPU minutes from normalized artifacts | tracked evidence snapshot; raw local artifacts not shipped |
| Table 3 mechanism probes | `docs/reproducibility/table3_probe_calibration.csv`; local `_gate0_artifacts/controllers/*` summary CSVs | `python3 tools/verify_reproducibility_matrix.py` | probe snapshot validated | CPU seconds | tracked evidence snapshot; controller raw artifacts not shipped |
| LETTER official adapter row | official LETTER item-index JSON artifact; `docs/reproducibility/official_adapter_metrics_snapshot.csv` | `python3 -m sidinspector.adapters.letter ... && python3 -m sidinspector.preflight ... && python3 -m sidinspector.metrics ...` | `sid_assignments.parquet`, preflight JSON, D1-D5 CSVs | CPU minutes after downloading upstream artifact | adapter released; upstream artifact required |
| LC-Rec official adapter row | official LC-Rec Instruments JSON artifact; `docs/reproducibility/official_adapter_metrics_snapshot.csv` | `python3 -m sidinspector.adapters.lcrec ... && python3 -m sidinspector.preflight ... && python3 -m sidinspector.metrics ...` | `sid_assignments.parquet`, preflight JSON, D1-D5 CSVs | CPU minutes after downloading upstream artifact | adapter released; upstream artifact required |
| ReSOT released-archive adapter row | official ReSOT `data.zip` Instruments index JSON and sidecars; `docs/reproducibility/official_adapter_metrics_snapshot.csv` | `python3 tools/run_v1_gate17_resot_intake.py --index-json <Instruments.index_lemb.json> --item2id <Instruments.item2id> --item-json <Instruments.item.json> --inter-json <Instruments.inter.json>` | `sid_assignments.parquet`, `item_metadata.parquet`, `interactions.parquet`, preflight JSON, bounded D1-D5 smoke | CPU minutes after downloading upstream archive files | adapter released; upstream archive required; no-license-detected caveat |
| DIGER RQ-VAE adapter row | DIGER Hugging Face Beauty embeddings, `emb_map`, train/valid/test JSONL, and RQ-VAE checkpoint; `docs/reproducibility/official_adapter_metrics_snapshot.csv` | `python3 tools/run_v1_gate17_diger_intake.py` | `sid_assignments.parquet`, `item_metadata.parquet`, `interactions.parquet`, preflight JSON, bounded D1-D5 smoke | CPU minutes after staging upstream HF files | adapter released; upstream HF files/checkpoint required; no-license-detected caveat |
| D3/ranking and portability checks | `docs/reproducibility/extension_checks_snapshot.csv`; local `_gate0_artifacts` vertical/downstream/churn paths | `python3 -m sidinspector.downstream_probe --manifest <manifest.csv> --output-dir <probe_output>`; `python3 -m sidinspector.churn --old-sid <old.parquet> --new-sid <new.parquet> --output <d6.csv>` | `downstream_probe_summary.csv`, `downstream_probe_correlations.csv`, `d6_churn*.csv` | CPU minutes for bounded probes | tracked evidence snapshot; raw local artifacts not shipped |

## Paper Table Snapshots

The following tracked snapshots preserve the exact numbers used by the paper
without shipping large local artifacts:

Legacy filenames remain stable for released manifests. Manuscript Table 8 maps
to `table10_g20_trained_trace.csv`, Table 9 to
`table8_resot_walkthrough.csv`, and Table 10 to
`table9_resource_contract.csv`; `sidscope_g7_full_table_figure_ledger.csv`
records the same mapping.

- `docs/reproducibility/table1_evidence_catalog.csv`
- `docs/reproducibility/table2_musical_diagnostic.csv`
- `docs/reproducibility/table3_probe_calibration.csv`
- `docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv`
- `docs/reproducibility/g14_usage_demo_decisions.csv`
- `docs/reproducibility/g14_usage_demo_summary.json`
- `docs/reproducibility/official_adapter_metrics_snapshot.csv`
- `docs/reproducibility/extension_checks_snapshot.csv`
- `docs/reproducibility/rqmin_reference_snapshot.csv`
- `docs/reproducibility/sidscope_sampled_regeneration_manifest.csv`

The `source_evidence` column records the local raw artifact path used during
paper construction when that artifact is not included in the release repo. Rows
with `raw local artifacts not shipped` should be read as traceable evidence
snapshots, not as a claim that a fresh reviewer checkout contains the full
training/evaluation cache.

## Verification

Run:

```bash
python3 tools/verify_reproducibility_matrix.py
```

This checks that the matrix and tracked evidence snapshots are present,
well-formed, and internally consistent. For a full package smoke test, run:

```bash
python3 tools/verify_sidscope_resource_package.py
```

The package verifier runs import checks, the toy diagnostic, the reviewer
quickstart, unit tests, and the reproducibility-matrix check.
