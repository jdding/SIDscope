# ADR-0021: Paired regression, offline review and measured local workflows

Status: accepted local implementation, 2026-09-09. Product remains 1.7.0.dev0.
Accountable: jdding; existing Evaluation, Diagnostics, Evidence and Release owners.

## Requirements and topology

Approved order: N05 → N04 → N08, with N01/F09 actual-use closure alongside and a
final readiness review. Keep one synchronous Python process and local files.
Use existing evaluation kernels and NumPy for statistics, standard-library HTML
escaping for reports, and fresh subprocesses/resource.getrusage for measurement.
No service, database, job queue, browser runtime dependency, new model, GPU,
training, external reviewer or signature service is introduced.

Alternatives rejected: per-episode IID bootstrap (ignores users), treating seed
replicates as users, silent cohort intersections, rebuilding a separate metric
engine, JavaScript dashboard/hosted viewer, and streaming without demonstrated
need. Existing CLI/API and canonical schemas retain their behavior and versions.
New opt-in modules are local development APIs, not additions to the 39-symbol
stable facade or 19 canonical CLI-result schemas.

## N05 statistical SPEC

Input: two lists of {run_id, pair_id, seed, controls, report}, a shared complete
episode→user-cluster map, explicit absolute Hit/NDCG degradation budgets, bootstrap
seed, replicate count and confidence level. CLI also resolves report file paths.
Every report is recomputed from its inputs. Match all pair IDs, seeds, controls,
cohort/target/slice labels, K and publication depths. Reject duplicates, missing
runs, reused run IDs across arms and any incompatible protocol; never drop rows.
Controls and run/user independence are declarations, not authenticated facts.

Estimand: equal run-pair weight, episode-macro metric difference (candidate minus
baseline), including original invalid slots and right-censoring. User clusters
may contain unequal episode counts. Aggregate sums per run×user, retain cluster
sizes in the denominator, independently resample run-pair and user multiplicities,
and apply identical product weights to both arms. Return absolute and relative
effects (relative unavailable at zero baseline) and pointwise percentile intervals.
The approach follows the [pigeonhole bootstrap](https://arxiv.org/abs/0712.1111);
it is approximate, not an exact finite-sample or simultaneous coverage guarantee.

Budget decisions per metric/slice: interval wholly below -budget → regression;
lower bound at least -budget → within_budget; otherwise inconclusive. Fewer than
two pairs/users or constant observed cell effects → unavailable interval and
inconclusive, never automatic PASS. Two is merely an identifiability floor, not
sufficient power. Do not aggregate pointwise decisions into familywise PASS.
Original actual RPG/PSID observations contain one run each on different datasets;
they cannot supply real paired multi-seed inference. Never clone them into seeds.

Acceptance: independent expanded resampling reference; known effects; invariance
under run reordering and repeated episodes within existing users; unequal cluster
size weighting; typed incompatible/missing/tampered input tests; CLI/API parity;
installed consumer. Small-sample and declaration limitations stay in every output.

## N04 review SPEC

Recompute candidate and optional compatible baseline before rendering. Identify
invalid slots, target-rank regression and targets outside top-K, grouped by slice.
Show total affected counts, bounded pseudonymous examples, source content hashes,
JSON evidence pointers, next checks, hypotheses and null confirmed causes. Bounds
only truncate displayed examples, not metrics/counts. No raw episode IDs, cluster
IDs, ranked input or private assets are embedded. Optional uncertainty is rebuilt
from its run inputs and must bind the displayed reports to the comparison arms.

HTML has escaped text, restrictive CSP, no scripts, input hyperlinks or external
requests. Baseline means comparator, not automatic supersession. No native or
training authenticity follows from ranked diagnostics. N10 portable evidence
review with full registry/supersession navigation remains a distinct candidate.

Acceptance: three preset degradations point to exact rows; privacy, hostile HTML,
input tampering, mismatched uncertainty/depth, CLI/API equality and no-overwrite
tests. Installed package consumers render outside the checkout.

## N01/N08 execution and boundaries

`run_sidscope_observed_review.py` performs canonical/mapping admission, original-
input reconstruction, faithful native rank projection, evaluation and static
review in one command. Native split/catalog identity is hashed, never shortened.
Duplicate native ranked slots are explicitly unsupported by this optional ranked
consumer; it fails rather than silently deduplicating. Canonical evidence retains
its original native semantics. No inference happens during postprocessing.

`benchmark_sidscope_observed_review.py` repeats each existing real observation
three or more times in new processes. Bind inputs and source bytes, record phase
wall time, whole-process peak RSS, output volume, exact workload shape and existing
native NFE with its original scope. Require numerical/evidence identity equality
across repeats. Timeout is enforced; RSS is a post-run guard, not a memory limiter.
The default timeout guard is 300 seconds, aligned with the local scale harness;
it is scheduling headroom for supported Python/dependency combinations, not a
latency promise. Callers can explicitly select a smaller guard.
Report median/min/max, not a tail-latency claim from three samples.

The available real workloads contain full 12101/17396-item mappings and
67089/42756 split rows but only five trace episodes each. These runs can accept
that exact postprocessing scale, not a full-population trace workload or inference
throughput. N08 remains partial until representative larger real traces and an
applicable acceptance target are supplied or authorized. No new hard product cap.

## Bounded N08 authorization addendum (2026-09-09)

The user approved exactly 100 episodes per existing frozen route, not 1000 or
further scale expansion. Preserve the RPG test-prefix and PSID five-bucket
selection (20 each), checkpoint and native generation semantics. Each route has
a 7200-second CPU-only guard, two threads, no training and no automatic restart.
Use a new private workspace; source/cache/checkpoint remain read-only. A failed
dependency import is not inference evidence. Explicit `--episodes` and
`--scratch-parent` parameters preserve the old five-episode default; incomplete,
duplicate or unbalanced selections fail closed. Historical results are retained.

Successful fresh observations plus three consistent postprocessing repeats
close N08 for that recorded workload. Arbitrary scale, production tail-latency
SLOs and independent user use are not new exit gates for this bounded approval.
Do not reopen N08 for 1000 episodes without a new user requirement.

## Operation, migration, rollback and completion

The 2026-09-09 architecture-view refresh maps these implementations to actual
code paths and distinguishes logical layers from workflow consumers. Editable
draw.io source and its preview are conformance/evidence-full documentation only.
The existing inventory verifier checks the graph's paths, requirement states and
source/preview hashes. This is documentation synchronization, not a new runtime,
schema, release promise, N07 implementation or change to the N08 approval scope.

Optional entrypoints; no migration of old evidence. New output paths only;
completion markers written last. A failed stage preserves its partial directory
without a top-level completion marker; retry in a new directory. Rollback means
stop using the additive modules. Local failure domain and CPU/memory are owned by
the invoking engineer; no new on-call or remote job. Artifact hashes and atomic
completion records are integrity checks, not signatures or authenticity claims.

Success: all focused and full CPU tests, synchronized ledger/ADR/manifest/inventory,
normal wheel/offline lock/sdist consumers, all three archive+G8 gates, exact-source
record and final readiness review. F09 requires an actual independent user run;
neither this developer's automated runs nor a fabricated reviewer closes it.
The readiness verifier distinguishes approved-local pending N01/N08 from the
unapproved N07/N09/N10 backlog; completed N04/N05 no longer appear as candidates.
