# ADR-0026: Same-source delivery summary and application-layer boundaries

Status: accepted local implementation scope, 2026-09-27. The package remains
`1.7.0.dev0`; no RC, tag, push or public release is authorized.

## Context and decision

Delivery readiness previously had no machine-aggregated authority: readiness
claims could not be bound to a complete, same-source set of executed gate
receipts, and business logic for the evidence registry lived only in the CLI
while the native bridge lived only in source-tree tools, so installed
consumers could not reach it.

Three boundaries are now explicit:

1. Required delivery gates are frozen in
   `docs/reproducibility/sidscope_required_gate_catalog.v1.json`. The new
   `tools/sidscope_delivery_summary.py` runs individual gate receipts, builds
   `sidscope.delivery_summary.v1` and verifies it by recomputing every
   referenced digest and re-running record v2 verification for all three
   profiles. Missing, duplicated, unknown, failed, not-run or
   unapproved-skipped gates fail closed; the three-group performance campaign
   must pass every group. The summary is a local hash binding, not a signature
   scheme, not publisher authenticity and not a release authorization.
2. Evidence registry business judgements moved to
   `sidinspector.evidence.operations` (admission ordering, register, supersede,
   CAS-authoritative compare, quarantine two-phase handling, rebuild). The CLI
   delegates and keeps only parsing, paths and formatting. Parameters, JSON
   schemas and error codes are unchanged; CAS stays authoritative and the
   SQLite projection disposable.
3. The pure-data RPG/PSID native bridge and observed-review orchestration moved
   into opt-in `sidscope.native_bridge` and `sidscope.observed_review` modules.
   The unchanged hash-pinned RPG v1 verifier is an explicit evidence-full
   provider: wrapper entries register it, the default runtime install fails
   closed with `native_verifier_unavailable`, and the PSID family verifies
   in-package.

`certification_ready` now means `implementation_ready` AND `delivery_ready`
(verified summary bound to the clean candidate) with no unresolved technical
blocker; `--require-certification-ready` returns a typed
`delivery_summary_required` block without the explicit summary and trusted
digest.

## Consequences and rollback

Linux preparation correction (2026-09-28): shared cell validation accepts the
prepared `sidscope-matrix:<version>` images documented in the runbook, not the
git-less upstream base-image names. Source manifests hash live Git-tracked
bytes so worktree and real clone agree despite ignored build/evidence output.
The collector independently reads HEAD, branch-bound public snapshot and clean
state; expected strings are comparison inputs, not observed evidence. Prepared
wheelhouses are resolved inside each target runtime and cells run offline.
This changes no runtime API or public compatibility promise. Local shell
regressions cannot substitute for four actually executed Linux cells.

Every readiness statement must cite the summary digest and gate catalog
digest; no pytest count, old PASS or running process substitutes for receipts.
Runtime schema/facade surfaces do not grow (39 curated symbols, 46 schema IDs,
19 CLI result schemas unchanged). Rollback reverts the summary tool, catalog,
operations module and bridge modules without touching historical evidence,
ledger facts, public 1.1.x history, TOIS refs or adapter-native semantics.
