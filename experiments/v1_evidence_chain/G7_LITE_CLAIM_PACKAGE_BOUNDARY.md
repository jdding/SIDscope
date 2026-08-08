# SIDScope G7-Lite Claim And Package Boundary

Date: 2026-06-10
Status: historical frozen boundary for G8 package construction; superseded for
final paper tables by the canonical G9 ledger
Target: SIGIR 2027 Resource Track readiness while CIKM V0 result is pending

This file freezes what the reviewer package was allowed to support before G8
packaging. It is intentionally narrower than the full claim ledger. If a claim
is not listed as main-text or appendix-safe here, the package must not imply it.

## Main-Text Claims Allowed

1. SIDScope provides an artifact-level inspection layer for Semantic-ID
   generative recommendation artifacts before generator training.
2. SIDScope supports normalized artifact intake, schema validation, and D1-D5
   mapping diagnostics across official snapshots, official-code-derived rows,
   faithful GRID/P5 Beauty tokenizer-stage intake, and bounded local
   reference/stress rows.
3. D3 prefix/co-occurrence alignment is a fast train-only candidate-exposure
   proxy under the current prefix-candidate protocol.
4. SID interface health is a multi-signal trade-off surface. D1 utilization,
   D2 collision/load, D3 co-occurrence alignment, D4 popularity allocation, and
   D5 structural cost expose different artifact behaviors that a single
   collision or uniqueness scalar would hide.
5. Cluster-aware reanalysis is the paper-facing uncertainty boundary for the
   G2/G3 exposure signal. Row-level bootstrap CIs must not be used as headline
   uncertainty.
6. SIDScope exposes severe duplicate/full-code collision stress cases, with
   R138 explicitly labeled as a local stress/reference artifact rather than
   faithful GRID coverage.
7. D7 provides a constrained-aware trace-labeling schema and a bounded
   public-beam trace-accounting bridge from artifact diagnostics to target
   survival/hit outcomes.

## Appendix-Safe Claims

1. Detailed AutoDL recovery records for ReSID and GRID tokenizer-stage intake.
2. Public-beam D7 scale details, including per-case summaries from G6/G7.
3. R138 local stress/reference details and collision diagnostics.
4. Sensitivity tables from the scientific deep dive, including depth,
   scope, strata, and leave-one-artifact-out analyses.
5. Historical route attempts and stop-loss records, only when clearly labeled
   as provenance rather than successful evidence rows.

## Claims To Avoid

1. SIDScope improves final downstream recommendation quality.
2. SIDScope predicts trained generator failure.
3. D1-D5 causally explain downstream recommendation performance.
4. Any tokenizer or Semantic-ID assignment method is generally superior because
   of SIDScope diagnostics.
5. R138 is faithful GRID named coverage.
6. Invalid/unresolved paths are a standard constrained-decoding failure mode.
7. Current V1 is definitely a separate SIGIR submission if CIKM V0 is accepted;
   that remains controlled by `V0_V1_DELTA_AND_VENUE_GATE.md`.

## Reviewer Package Include Boundary

The G8 reviewer package may include:

- `src/sidinspector/**`;
- CPU-only examples under `examples/`;
- reviewer-facing docs under `docs/`;
- package metadata: `README.md`, `LICENSE`, `pyproject.toml`,
  `requirements.txt`;
- lightweight verification tools under `tools/verify_*.py` and
  `tools/run_sidscope_sampled_regeneration.py`;
- compact evidence snapshots under `docs/reproducibility/`;
- bounded V1 gate reports and JSON summaries when they are needed to trace
  paper claims.

The G8 reviewer package must exclude:

- `.git`, `.aris`, `.codex`, `.agents`, `.codegraph`;
- AutoDL payloads, returned archives, SSH targets, command packets with current
  remote addresses, and cloud logs;
- raw P5/Amazon data, raw HF caches, checkpoints, tensor dumps, parquet caches,
  pickle/numpy arrays, and target-level joined trace CSVs;
- paper PDFs, LaTeX build byproducts, private paper-chain provenance, and
  local-only arXiv packages;
- any file that exposes credentials, private absolute data roots, or
  non-reviewer private workflow state.

## Package Claim Boundary

The package can support three levels of reproducibility:

1. `fully runnable`: reviewer quickstart, toy diagnostic, adapter/preflight
   smoke, D1-D5 CSV generation, and reproducibility-matrix validation.
2. `tracked snapshot`: compact CSV/JSON evidence used for paper tables where
   raw artifacts are too large or depend on upstream training.
3. `provenance only`: local run records that explain how a row was produced
   but are not themselves a fresh-checkout regeneration claim.

The package must not blur these levels. Any paper table sourced from snapshots
must say so in the canonical G9 ledger.

## G8 Input Decision

This historical G7-lite boundary was sufficient to start G8 because it defines:

- the allowed main-text claim surface;
- the appendix-only surface;
- the forbidden claim surface;
- the package include/exclude boundary;
- the three reproducibility levels that G8 documentation must preserve.

The canonical G9 ledger is now closed for the current paper artifact registry in
`CLAIM_LEDGER.md` and
`docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv`. If the final
paper changes tables, figures, captions, or numerical claims, refresh the
G9 ledger and rerun the claim verifier.
