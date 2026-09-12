# SIDScope pre-2.0 SDLC hardening

<!-- SIDSCOPE:CURRENT:BEGIN -->
Local development: `1.7.0.dev0`; public GitHub remains 1.1.x; 1.8/1.9 inactive.
Current diagnostic admission and comparison require input-bound recomputation; declarations alone do not pass.
Unclosed SDLC requirements: F09.
Requirement snapshot: `d84f1b924e203550bd953ad5254467d09079fc49aee229ed85e189e890ac0e2c`.
Historical route decisions (not newly recomputed training): dact_tiger=named_adapter; diffgrm_www2026=named_adapter; isd=close_named_adapter; latte_psid=named_adapter; llada_rec=named_adapter; rpg_kdd2025=named_adapter.
Historical route snapshot: `cb51983ca33506c4c00f1722eda8e5eb9eb452409ce026f9810a76fe1cf02a92`.
Independent user acceptance is not established by automated tests. No push, tag, public release or TOIS mutation is authorized.
<!-- SIDSCOPE:CURRENT:END -->

Active version: `1.7.0.dev0`. Local only. Updated: 2026-09-09.
Authority: ADR-0016 and the requirement ledger
`reproducibility/sidscope_sdlc_requirements.csv`.

## State and execution order

All approved technical work other than the deliberately human F09 condition is
closed. N03-N06 provide real native admission, mapping preflight, paired
regression and actionable offline review. N08 is verified at the exact user-
bounded workload of 100 episodes per RPG/PSID route, including transferred-input
hash checks and three fresh-process local postprocessing repeats; no further
inference, 1000-episode expansion or production SLO is planned. N07 adds bounded
SID lifecycle diagnostics with route-specific semantics and actual-shape
same-input controls. Adapter SDK 1.0 and the candidate surface are frozen by
ADR-0023/0024. N09/N10 are deferred.

`--require-engineering-ready` now passes. Certification remains fail-closed only
because N01/F09 requires an independent user to complete the documented own-
producer journey. No automation or maintainer sign-off substitutes for that use.
The package therefore remains `1.7.0.dev0`; no RC, tag, push or release is
implied. Current delivery results require a fresh clean exact-source record.

Current decision: computation only, no maintainer sign-off. Necessary and
feasible computations run on CPU or, when required, the Fudan cluster. If a
computation is unnecessary or unavailable, do not perform it and do not verify
the associated claim. This disposition is not a claim that the value is false.
There is no pending signature-policy decision blocking implementation.

Contain demonstrated trust failures first, then verify delivery and acceptance,
then complete the approved minimal workflow and two real native export consumer
integrations. Independent user adoption is a separate acceptance, not simulated here. Optional 1.8
and 1.9 remain inactive. A green regression run never closes an open requirement.

1. Implemented computed admission: caller gate declarations alone cannot create
   new admission or default indexes; supplied diagnostic inputs must be recomputed.
2. Implemented contracts: reject contradictory resolved/target/rank states and
   success/Hit partitions; reject out-of-range standard metrics; qualify declared
   comparisons and do not compare unknown metrics automatically.
3. Implemented resource bounds: per-file/total/count/depth limits before parsing,
   with typed malformed Unicode/JSON and excessive depth errors.
4. Implemented delivery checks: receipt v2 binds actual bytes; installed runtime
   has a self-contained synthetic example; G8 uses a regular install from a
   separate build copy and runs isolated consumers outside the source tree.
5. Implemented live performance measurement: frozen baseline remains unchanged;
   thresholds, environment mismatch and workload mismatch require review.

**Diagnostic admission, protocol-bound comparison, the six-command performance
gate and two real native export consumers are implemented and exercised.**
F01/F02/F04/F08 retain their executable acceptance. N03's approved technical
producer -> validate -> evaluate -> bundle -> compare chain is now implemented
and exercised on the two actual observations. F09 remains partial solely for its
actual independent user trial. Earlier narrower export-inspection closure wording is
superseded, not a reason to reduce the acceptance criterion. Structural historical
replay is not independent verification. No named-adapter or training authenticity
claim follows from diagnostic admission. Broader 2.0 certification remains open.

## Requirement ownership and definition of done

The CSV records finding, priority, owner role, state, acceptance and verification
pointer. Roles are accountable implementation areas, not sign-off authorities. `verified`
means the stated bounded acceptance was executed; `contained`, `partial`,
`open` and `blocked` cannot be promoted by a passing inventory test. The release
ledger separates technical findings (F01-F14) from candidate features (N01-N10).
Candidates remain visible but do not automatically block certification or imply
that every suggested feature must be implemented before a release.

F01 runs fixed diagnostic recomputation on embedded protocol/trace/selection/report
objects before `diagnostics_verified` admission and before derived indexes. Private hash-only training
claims remain unverified. F02/F04 bind fixed metric definitions, full selection
identity and slice semantics through `sidscope.evaluation_protocol.v1`, then
recompute the entire result card. Mismatched populations and tampered values fail
closed; unknown compute environments do not produce performance deltas.

F06 binds source HEAD, dirty public-file bytes, tests, environment and all three
archive hashes in a detached local record. Pin its digest before reading an
archive; no signature service or publisher-authenticity claim is introduced.
F07 executes wide dependency resolution and a separate hash-locked offline
replay, wheel consumers and sdist round-trip consumers. Actual local install matrix: Darwin arm64 Python 3.9.6, 3.10.19, 3.11.15 and
3.12.13. The current Linux arm64 Docker matrix also executed CPython 3.9 through
3.12, with the full suite and engineering verifiers green in every cell. CI now
installs the declared `setuptools>=68` build backend explicitly. Windows,
optional training extras and unlisted Python versions remain outside the recorded
acceptance; none is inferred from `>=3.9`.
F11 keeps bounded untrusted intake and strict structural checks; ADR-0018 removes
arbitrary default caps from trusted local workflows and export inspection while
offering explicit caller budgets. Hash-pinned historical verifier scripts retain their original
bytes and trusted-replay scope. No complete security audit is claimed.

F03 has a full 48-case target-state table and optional native projection in
`verify --native-payload`. Explicit overlay ranks are checked; resolution-array
order is never invented into ranking. Missing catalog/generation/authenticity
facts stay unverified. F12 pins signatures/defaults and executes all 39 curated
symbols from site-packages, with semantic mutation regressions. F14 is the
three-journey public API/CLI documented in `SIDSCOPE_USER_WORKFLOWS.md`; the
lightweight observed-cohort comparison is qualified, not full experiment proof.

The local input-policy change has a separate 10k/100k/1M CPU matrix across JSON,
CSV, Parquet mapping and evaluation/comparison. N08 adds the bounded real-route
100-episode observations and three local repeats described above. These results
support only the measured workloads; they do not establish p95, arbitrary scale
or a production SLO. See `SIDSCOPE_NEXT_DEVELOPMENT_PLAN.md` for the remaining
F09 acceptance and RC transition gates.

F10 links all findings and candidates to an actual accountable owner, code,
tests, commands, dependencies, risk and disposition. F13 generates marked current
status sections in seven documents. Changing the ledger without regenerating
those sections fails; historical route decisions and evidence remain intact.

## Minimal user workflow (implementation approved; independent user acceptance separate)

Actor: an SID algorithm engineer with an existing mapping or native output;
no upstream retraining or semantic rewrite is required.

Input: a permitted item-to-SID mapping and optional interactions, or a native
trace export with dataset/selection/run/checkpoint/protocol identities. Private
raw data and real caches stay outside the public package.

Flow: preflight -> canonicalize without changing native meaning -> validate ->
diagnose -> inspect actionable evidence -> compare only compatible protocols ->
export an immutable review bundle. Output must include exact failing records,
metric denominators, censoring, supported next checks and unsupported claims.

Acceptance: a new user completes the documented path in a clean regular install;
at least one deliberate invalid input fails with a typed actionable message;
repeating the run reproduces canonical outputs; no manual JSON fabrication or
core edits; no training-performance or verified-admission claim from fixtures.
Record elapsed onboarding time and manual interventions, without inventing a
success threshold before owner approval.

Two real external integrations must use distinct native semantics (suggested:
one AR export and one non-AR/masked export) and provenance-bound real exports.
Execute their end-to-end consumer checks; no manual sign-off is required.
Existing packaged plugin fixtures remain regression evidence, not new real
exports. Necessary feasible recomputation may use the Fudan cluster; check
input availability and resource scope first. Private-data publication remains
out of scope, as does unrelated or speculative retraining.

### Executable entry points

In a regular conformance install, create a **new** diagnostic submission from
existing declarations and supplied canonical inputs without hand-editing JSON:

```bash
python3 -m sidinspector.submission.recomputed \
  --source examples/conformance_ecosystem_fixture/submission/positive \
  --trace examples/canonical_pipeline_fixture/trace_envelope.json \
  --selection examples/canonical_pipeline_fixture/episode_selection.json \
  --output /tmp/sidscope-recomputed-submission
sidscope submission check --root /tmp/sidscope-recomputed-submission
```

The example uses synthetic canonical inputs and proves the software path only.
An existing output is never overwritten. G8 also runs the builder and both
derived indexes through isolated site-packages imports outside the source tree.

In the source or evidence-full profile, run the two real compact native exports:

```bash
python3 tools/inspect_sidscope_native_export.py \
  examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json \
  --output /tmp/sidscope-rpg-inspection.json
python3 tools/inspect_sidscope_native_export.py \
  examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json \
  --output /tmp/sidscope-psid-inspection.json
```

Both run their native verifiers and emit deterministic input-hash-bound reports.
RPG preserves unordered graph semantics and recomputes Hit@10=0.2 on five actual
exported episodes. PSID preserves AR ancestry and evaluation-slot semantics;
its five episodes have no target labels, so Hit/NDCG remain null with
`target_labels_not_exported`. No label substitution, new training, model-quality
generalization or independent user adoption is claimed. These existing real
exports are not synthetic fixtures and are not rewritten. Native execution
authenticity remains unverified, as opposed to export content consistency.

## What needs recomputation

| Claim | Minimum executable check | If inputs or need are absent |
| --- | --- | --- |
| Diagnostic metric values given a trace | CPU recomputation using diagnostic + trace + selection; compare metrics and bindings | Do not claim metric verification |
| Native output corresponds to a checkpoint | Re-run bounded native inference on the permitted data/checkpoint; use Fudan when necessary | Leave native-output authenticity unverified |
| Historical training occurred exactly as declared | Not established by a hash or a new training run | No verification claim and no sign-off workaround |
| Structure or archive byte consistency | Existing CPU contract/hash checks; no training computation | Describe only the check actually performed |

The existing `verify` CLI now accepts all three recomputation inputs together:

```bash
sidscope verify \
  --report examples/canonical_pipeline_fixture/conformance_report.json \
  --diagnostic examples/canonical_pipeline_fixture/diagnostic_report.json \
  --trace examples/canonical_pipeline_fixture/trace_envelope.json \
  --selection examples/canonical_pipeline_fixture/episode_selection.json
```

This source/conformance-profile example executes real CPU metric recomputation
on synthetic inputs, not a real algorithm acceptance. A rehashed inconsistent
metric fails with `metric_mismatch`; partial inputs fail with
`incomplete_recomputation_inputs`. With no recomputation inputs, the command
reports `verification_performed=false` and `structure_only`. A passing recompute
is limited to `diagnostics_from_supplied_trace`; it does not verify training,
native-trace authenticity or adapter admission. Those claims stay explicit.
The conformance-profile G8 also executes this recomputation through the regular
installed package with isolated imports outside the source tree.

## Historical preceding-batch verification (superseded by the current ledger)

Final computation-path validation (2026-09-08): 327 tests pass, 6 retain their
existing external-input skips; metadata, architecture inventory, all three
release profiles and all 39 resource-verifier commands pass. Regular runtime G8
passes 7 commands; regular conformance G8 passes 12, including the new builder,
diagnostic admission and both indexes through isolated installed imports.
G8 caught a legitimate pretty-JSON input being incorrectly treated as a package
object; the input boundary was corrected and regression-tested, then the archive
was rebuilt and installed again. No frozen input, baseline or historical receipt
was rewritten. Failed and corrected temporary archives remain separate.

At that earlier snapshot F03/F06/F07/F10/F11/F12/F13/F14 remained nonpassing.
That record closes only the preceding computation/protocol/performance/native
consumer batch. Current engineering status comes from the generated ledger above.
The passing performance report is limited to the original six-command workload.

```bash
python3 -m pytest -q
python3 tools/verify_sidscope_sdlc_hardening.py
python3 tools/verify_sidscope_sdlc_hardening.py --require-ready
python3 tools/check_sidscope_current_performance.py \
  --require-delivery \
  --output /tmp/sidscope-current-performance.json
```

The readiness command intentionally exits 2 while blockers remain. Performance
output must be outside the repository and must not overwrite an existing file.
The raw observation status remains distinct from the delivery disposition and
record v2 binds both to the exact source snapshot.
The first live run exceeded the 20% review threshold for all six commands.
The implemented fix constructs only the selected root command's argument tree;
full inventory/help construction remains available. All branch parameter trees
and help text have equivalence regressions. The subsequent original-environment
run passes all six medians without changing the baseline (latest ratios 0.1622-0.7468).
In-process fixture
latency does not establish cold-start latency, throughput, memory or scale.

A 100-call CPU profile of contract validation attributed about 0.577 of 0.726
seconds to constructing the complete CLI parser. This identifies a concrete
optimization target. No parser cache or threshold relaxation was introduced.
This benchmark does not claim cold-start, representative scale or memory closure.

Rollback: pin the prior local source for replay; preserve all evidence and refs.
Do not push, tag, publish, promote to 2.0 or restore unverified admission merely
to close a checklist. Remaining executable paths and required evidence must be
completed before claiming end-to-end closure; there is no sign-off dependency.

## Current delivery acceptance

The executable delivery gate is `tools/sidscope_local_release_record.py build
--output-dir /tmp/sidscope-local-candidate`. Pass repeatable `--python` options
to select installed interpreters. It runs the full suite, resource and profile
gates, wheel/sdist/offline-lock consumers, and G8 regular installation for each
ZIP profile. It refuses source-tree output, overwrites and source changes during
verification. Logs, dependency locks, wheelhouse, archives and the detached record
remain outside the source tree. A source inventory PASS alone is not delivery.

Use `verify --record RECORD --expected-record-sha256 TRUSTED_DIGEST --archive ZIP
--profile runtime` on the same tool before trusting candidate bytes. The expected
digest must come from the trusted local build, not from inside an untrusted ZIP.
The record identifies dirty input exactly; it does not turn a local candidate
into a public release or prove private training. No human signature is required.

Engineering completion (`--require-engineering-ready`) and independent actual
user use (`--require-ready`) are separate. The latter remains unestablished;
no elapsed onboarding time, second reviewer or user adoption is fabricated.
Candidate features N01-N10 retain their explicit backlog dispositions.
