# ADR-0022: Bounded SID refresh lifecycle diagnostics

Status: accepted local implementation scope, 2026-09-09. Version: 1.7.0.dev0.
Accountable: jdding; existing Diagnostics/Evidence owners. User approved N07 and
deferred other remaining algorithm candidates (N09/N10); no release authorized.

## Context and options

D6 counts literal code changes by depth. That is useful but can conflate token
renumbering, item additions/removals and changes in grouping. G22 is one retained
historical diagnosis/repair/handoff case; its aggregate hashes are not fresh
snapshot inputs or general lifecycle acceptance. Do not rewrite it.

Options: (A) expose raw D6 churn only; insufficient semantic separation.
(B) add a synchronous opt-in consumer over D6 and existing report validation;
selected. (C) automatic SID alignment/repair, graph-isomorphism search or a hosted
refresh service; rejected as unnecessary scope and a risk to native semantics.
No new dependencies, service, canonical schema or curated facade symbol.

## Input and identity SPEC

Two snapshots each contain exactly `dataset`, `item_namespace`, `sid_namespace`,
`semantics` and `mapping`. Mapping rows contain normalized integer `item_id` and
nonempty integer-token `sid` lists. Dataset and item namespace must match; changing
the normalization namespace requires explicit upstream alignment, not an inferred
join. Snapshot metadata are caller declarations, not authenticated dataset facts.
Duplicate items, bool/negative IDs, malformed tokens and incompatible semantics
fail closed. Empty catalogs are allowed. Optional local budgets are caller-owned.

`ordered_prefix` requires fixed width within each snapshot; different widths
between snapshots are explicit schema changes. Compare common depths only and
also report the full-code partition. `parallel_positions` also requires fixed
width, but each position is a distinct codebook and only the full vector defines
the structural partition: it never fabricates AR prefixes and it permits the
same integer value to occur at multiple positions. `unordered_set` rejects
duplicate tokens, compares full sets and never fabricates prefixes or AR
ancestry. Array-order-only changes are separate representation changes. Sort
rows by item ID for hashing; retain supplied token order in input identity, even
for unordered-set inputs.

## Diagnostic SPEC

Report common/added/removed populations separately. Raw code churn uses only
common items and has null rates when that denominator is empty. Reuse D6 for
ordered-prefix raw churn and collision statistics without modifying its legacy
behavior. With empty sides skip D6 explicitly, rather than manufacturing zero.

Structural change means an item's equivalence class among **common items**
changed at the given depth/full code. Compute old/new group sizes and their
intersection counts; no quadratic pair enumeration or approximate hash matching.
Report affected items, split/merge group counts and explicit denominator.
Added/removed items do not inflate this common-item structure measure.

For equal-width ordered-prefix or parallel-position SIDs, a per-position
bijection of old→new tokens on common items can show consistency with namespace
relabeling. This is not proof of author intent, embedding/geometric equivalence
or equivalence on unseen items. Unordered sets do not infer a token permutation.
Membership preservation alone is not proof of relabeling. Width/semantics limits
remain visible.

Reports bind normalized snapshot inputs, include bounded pseudonymous item
examples with exact source-row pointers, affected counts, observations and next
checks. Example limits never change metrics. No auto repair/re-encoding, causal
claim, training verification or mutation of the source mapping.

## Optional downstream evidence

`bind_evaluation(snapshot, report)` recomputes an existing evaluation report,
checks dataset and catalog membership, and attaches the snapshot identity without
manual hashes. `compare_snapshots` accepts two such bindings, rejects swapped or
stale snapshots, revalidates reports and requires exact cohort/protocol/depth
matching. Reuse existing ranked comparison, and show changes by target lifecycle
category and slice. This is an observed association on supplied evidence, not a
causal effect of refresh. The binding declares which mapping produced a run; it
does not authenticate upstream execution. Missing paired evidence stays
unavailable; never compare RPG Beauty against PSID Video Games.

## Delivery, validation and rollback

`sidscope.refresh` offers Python and `python -m` CLI entrypoints. Output JSON plus
a readable Markdown summary and a completion receipt are written to a new local
directory. Completion is last; existing output directories are never overwritten.
CLI `bind` can produce optional downstream bindings from ordinary snapshot and
evaluation files. No internal canonical JSON authoring is required.

Acceptance: pure renumbering; split/merge; unchanged prefixes; additions/removals;
empty/disjoint catalogs; width changes; unordered permutation; independent naive
partition oracle on small cases; tampering/identity/protocol negatives; no input
mutation; CLI/API parity and installed consumers. Actual frozen RPG/PSID mappings
exercise a zero-change control, not a claimed real refresh experiment. G22 remains
historical evidence unless its exact input snapshots are separately available.

Keep command-oriented operation: no daemon/on-call/SLO. Failure rejects the new
report and preserves all inputs. Rollback omits this optional entrypoint and uses
the unchanged D6/previous reports. N01/F09 actual independent use remains separate.
N08 is closed only after the already authorized 100-episode outputs pass local
validation/repeats; no further native inference or scale expansion is added.
