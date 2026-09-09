# ADR-0018: Separate local input budgets from submission policy

Status: accepted for local `1.7.0.dev0` development, 2026-09-08.
Accountable owner: jdding. No release, signature or upstream execution authority.

## Context and decision

The trusted local workflow's 10k-row, 8-MiB, width-256 and 32-MiB Parquet limits
were safety defaults without a workload-derived product requirement. They rejected
normal algorithm-engineering inputs and conflated local analysis with admission
of untrusted submissions. Remove those default application caps in
`sidscope.workflows` and the supported local native-export inspector. Keep shared
JSON-loader defaults and submission policy unchanged.

Expose immutable `LocalInputBudget` on audit/evaluate/compare and corresponding
CLI flags. A missing budget means no application cap, not infinite RAM. Configured
budgets are positive caller values, never imported from input JSON. Pass the same
byte choice through reading and parsing. Budgets are execution policy, excluded
from diagnostic content identity. Paths and in-memory mapping inputs use the same
normalization and metric kernels. JSON depth/encoding/duplicate/nonfinite guards,
unique IDs, consistent nonempty SID widths and ranking semantics remain mandatory.

CSV uses file iteration; Parquet uses file metadata before decoding when a budget
is configured. Neither change makes the full diagnostic pipeline streaming.
One-pass slice grouping removes repeated whole-population scans without changing
sorted output or metric definitions. No checkpoint execution, plugin sandbox,
hosted service or native generation change is introduced.

## Alternatives

- Retain hard-coded small limits: rejected; this blocks legitimate local usage
  without an evidenced supported-scale contract.
- Remove all validation and submission limits: rejected; local ownership does
  not make malformed contracts valid or change the untrusted admission boundary.
- Immediately rewrite all diagnostics as streaming: deferred until actual
  workload measurements justify the complexity and semantics are preserved.

## Verification and operations

Typed negative tests cover explicit row/byte/expanded budgets, invalid budget
types, duplicate/nonfinite/deep JSON, invalid UTF-8, duplicate IDs and no output
on failure. Positive file/API/CLI tests cross old row/byte/width/cutoff thresholds;
installed wheel/sdist consumers also cross former row/byte limits.

The independent CPU harness runs JSON/CSV/Parquet mapping and ranking
evaluate/compare at 10k, 100k and 1M rows in separate processes. It records input
and output bytes, phase times, process peak RSS and source/dependency identities.
Its timeout and post-run RSS ceiling are test policy, not product input limits.
One synthetic sample per cell cannot establish p95, native NFE, real integration
acceptance or a universal capacity SLO. N08 therefore remains partial.

No in-product timing hooks are added. The measurement harness is independently
removable. Frozen baselines, receipts, historical verifier bytes and TOIS refs
remain unchanged. Callers needing the former budget can explicitly select
`LocalInputBudget(max_rows=10000, max_input_bytes=8388608,
max_parquet_bytes=33554432)`; structural validity is never optional.

F09/N03 return to partial under their original complete-producer acceptance.
Green tests for a subset do not justify narrowing the requirement to that subset.
