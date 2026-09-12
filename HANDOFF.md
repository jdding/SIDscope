# SIDScope 1.7 Development Handoff

<!-- SIDSCOPE:CURRENT:BEGIN -->
Local development: `1.7.0.dev0`; public GitHub remains 1.1.x; 1.8/1.9 inactive.
Current diagnostic admission and comparison require input-bound recomputation; declarations alone do not pass.
Unclosed SDLC requirements: F09.
Requirement snapshot: `d84f1b924e203550bd953ad5254467d09079fc49aee229ed85e189e890ac0e2c`.
Historical route decisions (not newly recomputed training): dact_tiger=named_adapter; diffgrm_www2026=named_adapter; isd=close_named_adapter; latte_psid=named_adapter; llada_rec=named_adapter; rpg_kdd2025=named_adapter.
Historical route snapshot: `cb51983ca33506c4c00f1722eda8e5eb9eb452409ce026f9810a76fe1cf02a92`.
Independent user acceptance is not established by automated tests. No push, tag, public release or TOIS mutation is authorized.
<!-- SIDSCOPE:CURRENT:END -->

Last updated: 2026-09-12

## 2026-09-12 whole-project review remediation

Ten newly reproduced review findings are closed in dependency order.
Public JSON artifact scanning now uses strict duplicate/depth/nonfinite intake;
quarantined CAS entries cannot participate in normal comparisons; rejected
quarantine requests are side-effect free and an index-write interruption has a
typed rebuild path. N07 now propagates ordered-prefix structural changes into
classification, examples and downstream groups, uses canonical normalized-row
pointers, and applies caller row budgets to bound evaluation tables without
adding a default input cap.

The certification verifier now has an executable pending-to-accepted transition
that requires consistent, traceable F09/N01 evidence; no such evidence is being
invented, so F09 remains pending. Separately authorized `2.0.0rcN` versions can
be checked only after certification readiness. Exact-source record v2 binds a
current six-command CPU measurement and a narrow delivery disposition; it
preserves environment-review status and never rewrites the baseline. User docs
distinguish the historical rejected fixture from the current recomputed journey,
and the N08 reproduction flag is corrected to `--repeats 3` without rerunning a
model or expanding beyond 100 episodes. Linux acceptance also replaced the
fragile 60-second postprocessing default with a documented 300-second execution
guard; it remains a caller-configurable guard, not an SLO. A new clean candidate
record is required after these changes; preceding records remain immutable.

## Current 2.0 engineering-candidate closeout

The authorized technical closeout is complete except for the deliberately human
F09 condition. Adapter SDK is stable at `1.0.0` with current descriptors bound
to `>=1.0.0,<2.0.0`; plugin API stays `1.0`, the curated facade remains 39
symbols, and the public contract counts remain 46 schema IDs, 28 schema
resources, 19 CLI result schemas and 31 CLI leaf commands. ADR-0023 and
ADR-0024 freeze these boundaries while the package remains `1.7.0.dev0`.

N07 is implemented in `src/sidscope/refresh.py` with explicit
`ordered_prefix`, `parallel_positions` and `unordered_set` semantics, typed
fail-closed negatives, bounded pseudonymous examples and optional recomputed
downstream comparison. Actual-shape same-input controls passed for RPG 12,101
items and PSID 17,396 items; these controls establish zero fabricated churn,
not a real before/after refresh effect. N08 is closed at the user-authorized
limit of exactly 100 episodes per frozen route. Three local postprocessing
repeats produced medians of 50.2044 s / 1,791,819,776 bytes peak RSS for RPG
and 9.5620 s / 1,048,821,760 bytes for PSID. No model rerun, 1000-episode
expansion or production SLO is planned. Private receipts remain under
`.local_artifacts/reviews/2026-09-09/`.

The corrected local macOS CPU suite passes with 607 tests and 6 external-input
skips. The preceding candidate's Linux arm64 Docker matrix passed on CPython
3.9, 3.10, 3.11 and 3.12. Each
cell ran the full suite (544 passed, 29 optional/external skips, 65 subtests)
and the metadata, architecture, SDLC acceptance/hardening, profile, candidate
and resource-package verifiers. The 3.10 run exposed and closed a global import
mock portability defect. The 3.12 run made the declared `setuptools>=68` build
backend explicit in CI; no runtime dependency was added.

The frozen six-command CPU baseline remains immutable. A fresh macOS 26.6.2 run
correctly returned `environment_review_required` because the baseline was recorded
on 26.5.2. The review is closed without overriding that guard: implementation,
Python and processor match; all six advisory median ratios are below 0.90; and the
separate Linux matrix is green. This is not relabeled as a same-environment PASS
or a production SLO.

The current architecture assets are
`docs/figures/sidscope-current-architecture.png`, its verified content map JSON
and prompt record. The raster overview was generated with the built-in image
generator, not draw.io; the content map now includes the N07 refresh path. Pixel
review remains visual, while the architecture verifier checks six layers, module
paths, logical edges and asset hashes.

Engineering readiness is fail-closed and green. Certification readiness remains
blocked only by F09: an independent SID algorithm engineer must complete the
documented own-producer workflow without core edits or hand-built internal JSON.
Automation and maintainer execution do not satisfy it. N09/N10 remain excluded.
No push, tag, GitHub Release, public-main change or TOIS mutation is authorized.
A clean local candidate commit, a same-source Linux matrix and its detached
exact-source record v2 are the final delivery artifacts for this handoff; their
immutable identifiers belong in the post-commit receipt rather than being
predicted in source text.

## Earlier algorithm-engineer workflow continuation (ADR-0021)

2026-09-09 bounded N08 update: the user authorized exactly 100 episodes per
existing frozen route, not 1000 or further scale expansion. Both new CPU
observations finished successfully (RPG 106.79 s; PSID 45.06 s), each with two
threads and a 7200 s guard; no training or automatic retries. The initial RPG
attempt failed on dependency import before inference and is retained separately.
The successful run used an existing dependency environment read-only with
bytecode writing disabled. All new remote outputs are in the SIDScope-v2 workspace.

Security review blocked transfer of native/preflight/selection/observations JSON
to the private local evidence directory pending explicit export authorization.
Do not bypass that restriction. No successful native model observation needs
rerunning: retrieve the existing authorized outputs after approval, then perform
canonical admission, original-input recheck, offline report and three CPU
postprocessing repeats. N08 remains partial only for that pending validation,
not a new larger-scale/SLO requirement. Local tests: 549 passed, 6 skipped.
The earlier delivery record remains historical; no current new distribution/G8
receipt is claimed. Private execution handoff is under
`.local_artifacts/reviews/2026-09-09/n08-100-evidence/`.
N07 is the next recommended new feature, not yet authorized for implementation.

The following workflow overview predates the bounded 100-episode authorization.

Approved order N05 → N04 → N08 was implemented as opt-in local modules and
tools, keeping 1.7.0.dev0 and the 39-symbol facade unchanged. N05 computes paired
run/user-cluster effects and approximate pointwise intervals from recomputed
reports; missing pairs, protocol/depth/control drift and insufficient evidence
fail closed or remain inconclusive. N04 creates escaped offline reviews with
slice-level findings, pseudonymous examples, evidence pointers and bounded next
checks, without causal claims. See `docs/SIDSCOPE_REGRESSION_WORKFLOWS.md`.

`tools/run_sidscope_observed_review.py` connects existing real observations to
canonical admission, original-input recheck, ranked evaluation and static review
in one command. `tools/benchmark_sidscope_observed_review.py` repeats this in fresh
CPU processes. New evidence is under
`.local_artifacts/reviews/2026-09-09/algorithm-workflows/`; old evidence unchanged.
The existing observed mappings/splits are full, but both traces have five episodes.
N08 is therefore partial for larger representative traces and a user acceptance
target. Existing NFE is reported as prior observed compute, not new inference.

N01/F09 independent actual user use is still pending. Do not simulate a user or
clone observations into seeds. Complete current tests/install/archive/G8 evidence
must be bound in a new exact-source record. Perform final readiness review with
these remaining gaps visible; no push, tag, release, new model execution or frozen
repository write is authorized by this continuation.

The following 2026-09-08 notes are historical, superseded where noted above.

## Latest native-integration continuation

Canonical bridge continuation (ADR-0020): `tools/build_sidscope_native_submission.py`
now builds real source/data/SID/prepared/selection/run/checkpoint/trace/diagnostic/
protocol/profile/EvidenceBundle objects without fixture provenance. SDK export,
diagnostic admission and same-export comparison passed for both observed routes;
`--verify-submission` rebuilds from original inputs, not caller-provided flags.
New local evidence is under `.local_artifacts/reviews/2026-09-08/canonical-native-evidence/`.
`rpg-current/` and `psid-current/` are current; earlier outputs are retained.

New records bind best checkpoint progress, not final training progress: PSID
epoch 12 / step 9372 (final run 10000), RPG epoch 107 / step 10807 (final run 12827).
Existing records were read only; no new inference, training or key access was
needed in this continuation. The extraction tool's `--metadata-only` mode automates
that read-only operation. Training remains unverified; no historical evidence changed.

The canonical profile remains partial while diagnostic admission is accepted as
`diagnostics_verified`. N03's technical bridge is implemented and exercised;
F09 still requires actual independent use. Full current delivery results belong
to the new exact-source receipt, not the older 501-test record. Next development
is N05 comparison, then N04 reports, then N08 scale. No push/tag/release authorized.

The observation-only paragraphs below record the preceding batch and are
superseded on canonical-integration status by this continuation.

RPG Beauty and PSID Video Games are the chosen engineering acceptance tracks;
compare within each frozen protocol, not across datasets. Read-only Fudan checks
matched both actual checkpoint digests and the RPG model-file digest to historical
evidence. This does not certify training or all source files.

`tools/project_sidscope_native_export.py` now validates existing native exports,
projects faithful ranked slots and identity-bound optional target labels, and
recomputes same-protocol comparisons. Missing PSID labels stay unavailable;
same-file comparison is explicitly recomputation. Fifteen new focused regressions
passed at implementation time; record current full gates separately. This is NOT
the complete native-to-TraceEnvelope/EvidenceBundle integration.

The user subsequently explicitly approved the CPU scratch observer. Both frozen
checkpoints have now executed five episodes on Fudan with two CPU threads and no
training/GPU. Only normalized exports returned locally; the existing identity key
was used in place, never displayed/copied/returned. Original source/cache hashes
were unchanged. Two failed RPG observation attempts are retained separately: one
stopped before inference, one completed inference but double-counted a multiline
trace event. The fixed observer then completed; PSID was not rerun.

`tools/verify_sidscope_native_observation.py` checks native/label/measurement
bindings and full catalog/split/target/SID/interaction joins. RPG covers 12,101
mapping items and 67,089 split rows; PSID covers 17,396 items and 42,756 split rows.
Both have five actual selected targets. Forward calls per episode are RPG 1 and
PSID 4. Same-export comparisons mean recomputation, not independent run evidence.
Category purity, vocabulary-capacity utilization and temporal split authenticity
remain unavailable. These are explicit limitations, not passing checks.

Local ignored evidence: `.local_artifacts/reviews/2026-09-08/native-runtime-evidence/`.
Raw outputs and previous receipts are immutable; latest verified outputs are in
each method's `verified-current/` directory. Do not package private runtime specs,
normalized full data, caches, checkpoints or runtime logs. F09/N03 remain partial:
canonical source/prepared/run/checkpoint/TraceEnvelope/EvidenceBundle integration
and actual independent user use are still unfinished. The next technical work is
that canonical bridge, followed by N05, N04, N08. No further runtime authorization
is needed for the already approved same-scope CPU observation work.

## Current two-step batch (ADR-0019)

`sidscope.mapping_check.preflight` implements catalog/split/target/SID joins,
explicit missing-input dispositions and conditional D3/D4/weighted D2 using only
training interactions. Held-out-only events never trigger the legacy kernel's
all-events fallback. Existing audit/evaluate/compare outputs are unchanged.
`sidscope.pipeline.run` calls an explicitly chosen AdapterHarness producer,
validates trace/run/checkpoint/family bindings, builds recomputed submission
evidence and compares it. Installed tests execute this generic chain on synthetic
inputs. They are NOT two real producer acceptances.

F09/N03 remain partial: RPG/PSID native-to-canonical export bindings still need
connection; actual CPU execution and full mapping checks are now recorded above.
No independent actual user is claimed. Historical public evidence has a
43-row RPG mapping subset (not its full 12,101-item universe) and target-free
PSID exports. Never fill absent facts from fixtures. Existing Fudan assets are now
located and the approved observation supplies real normalized labels and compute.
N05/N04/N08 (the later three plan items) are deferred; no GPU work was launched.

## Current local input policy and acceptance correction

ADR-0018 removes arbitrary 10k-row/8-MiB defaults from trusted local workflows
and real-export inspection. `LocalInputBudget` and CLI flags allow explicit
caller budgets; canonical/SDK defaults and untrusted submission limits remain
unchanged. JSON structural checks, native semantics, version and authority
boundaries are preserved. JSON/CSV/Parquet mapping and evaluate/compare passed
the separate 10k/100k/1M CPU smoke; its logs are not a real-workload SLO.

F09 and N03 are partial, not closed: existing export consumers are not the
original external producer-to-bundle/comparison chain or an independent actual
user trial. N08 is partial after synthetic scale measurement. Generated status
above supersedes earlier narrower closure wording. No signature policy is added.
Next work and acceptance criteria: `docs/SIDSCOPE_NEXT_DEVELOPMENT_PLAN.md`.
All new evidence must be written to a fresh local receipt; historical receipts,
TOIS materials and native verifier bytes must not be rewritten.

## Current computation-path implementation (supersedes the earlier observations below)

Version remains `1.7.0.dev0`, local-only. Positive diagnostic admission now
recomputes embedded protocol/trace/selection/report objects and the complete
result card. Default status/result indexes repeat this check and emit only
`diagnostics_verified`, never named-adapter or training certification.
Missing inputs and rehashed inconsistent metrics fail closed. Comparisons bind
fixed metric definitions and full selection identity; unknown measurement
conditions suppress compute deltas. Historical evidence remains unchanged.

The six-command CPU performance gate passes on the original environment:
latest median ratios 0.1622-0.7468 of the immutable baseline. Selected-command
parser construction preserves parameter/help behavior without caching or relaxed
thresholds. This is not representative scale/memory/cold-start acceptance.

Two real compact export consumers execute native validators and deterministic
input-bound reports: RPG recomputes Hit@10=0.2 on five exported episodes; PSID
checks five target-free AR exports and leaves Hit/NDCG null. No label fabrication,
retraining, native execution authenticity or independent user adoption is claimed.
All required checks here are CPU-only; no cluster job or GPU was started.

The active catalog is 46 public schemas / 28 resources; 19 CLI result schemas
and 39 curated facade symbols remain unchanged. The previous batch ran 327
passing tests / 6 external-input skips and 39 resource checks. Current evidence
is produced by the detached local release-record gate; it additionally exercises
all three workflow entry points, regular wheel/sdist consumers, offline hashed
dependency replay and all ZIP profiles. Never reuse the previous count as the
current receipt. The original six external-input skips remain explicitly scoped.
Delivery checks and actual scope are governed by
`docs/SIDSCOPE_SDLC_HARDENING.md`, ADR-0016 and the requirement ledger.
Current finding states are generated above from the requirement ledger.
F03/F06/F07/F10/F11/F12/F13/F14 now have executable implementation and acceptance
gates; candidate delivery is valid only when the current exact-source record
finishes successfully. 2.0 certification is not claimed. Necessary feasible
recomputation is performed; unnecessary/unavailable claims remain unverified,
with no maintainer sign-off policy. Changes remain local and uncommitted.

New public guide: `docs/SIDSCOPE_USER_WORKFLOWS.md`. Actual installed matrix:
Darwin arm64 Python 3.9.6/3.10.19/3.11.15/3.12.13. Only recorded environments
are tested; configured Linux CI has not run. ADR-0017 keeps the modular monolith
and existing metric kernels. Four hash-pinned historical native verifier files
were preserved unchanged; untrusted input uses bounded canonical entry points,
while caller-owned local workflow/export input uses the ADR-0018 policy.
The release-record gate binds HEAD, branch, dirty public bytes, test logs,
distribution resolution/lock replay and runtime/conformance/evidence-full hashes.
No backup reviewer or independent actual user has been invented or signed off.

## Earlier SDLC observations (historical; superseded above)

The milestone summaries below are historical implementation/replay records,
not current certification or independent admission claims. Version remains
`1.7.0.dev0`; no push, tag, public release or TOIS change is authorized.
See `docs/SIDSCOPE_SDLC_HARDENING.md`, ADR-0016 and the requirement ledger.

Current new submission admission and default index publication are deliberately
quarantined with `independent_gate_verification_required`. There is no verified
positive admission path yet. Profile CLI checks say structure-only; historical
fixtures replay unchanged through an explicit non-admission path. Metric ranges,
target-state consistency and bounded submission parsing have new regressions.

Receipt v2 binds content bytes. Runtime has a self-contained synthetic first
contract example; G8 now uses regular installation and isolated out-of-source
consumers. Live CPU performance checks do not overwrite the historical baseline;
the first current run requires performance review (all six medians above 20%).
Full metric/protocol binding,
remaining parser/API checks and independent user acceptance are still open.
Regression PASS must not be reported as certification readiness. Two real
external integration acceptances have not been performed.

Validation for this hardening batch: complete CPU suite `313 passed, 6 skipped`;
metadata, architecture inventory, all three release profiles and resource
verification pass. Runtime has 117 archive members; clean extraction and regular
G8 installation pass, including isolated site-packages import and the synthetic
consumer. The six skips retain the existing external ReSOT/DACT/AutoDL input
boundaries. `--require-ready` exits 2 with the open requirement list; the live
performance result remains review-required. These are deliberately different
closure surfaces. Changes remain local and uncommitted; existing work and
untracked desktop metadata are preserved.

Subsequent correction: the project owner rejected maintainer sign-off. Necessary
feasible computations run locally or on Fudan when needed; unnecessary or
unavailable computations are not run and the associated claims stay unverified.
There is no outstanding signature-policy decision. Candidate N01-N10 features
are no longer automatically counted as certification blockers. Technical F
findings remain open until their actual implementation/acceptance is complete.

The `verify` CLI now has an executable CPU diagnostic recomputation path with
`--diagnostic --trace --selection`; rehashed metric tampering is rejected.
Without these inputs it explicitly reports that no verification was performed.
The bounded recomputation does not verify native execution or training and does
not yet complete the new-admission positive path. No cluster job was needed or
started for this correction.
Complete CPU regression after the correction: `314 passed, 6 skipped`.

## Historical milestone executive status (not current verification authority)

SIDScope 1.1.0 is locally release-ready and publicly released. The verified
`1.1.1.dev0` tree is the frozen regression authority; active development is
`1.7.0.dev0` in the dedicated `SIDScope-v2` worktree. Annotated tag `v1.1.0`
remains unchanged and resolves to
`a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3` on the public `main` branch.

Latte/PSID, RPG, DiffGRM, DACT/TIGER Tools, and LLaDA-Rec VG are the five
configuration-bound named generator adapters admitted under the complete
G0--G5 protocol. RPG retains parallel/unordered token-set and graph item-node
semantics; LLaDA-Rec retains native confidence-guided adaptive unmasking and
never masquerades as autoregressive prefix decoding. The remaining route is a
typed partial integration and must retain its documented gate label.

DiffGRM is now the publication-prioritized masked/diffusion candidate. Its The
Web Conference 2026 DOI, official repository revision, OPQ4 identity,
dataset-neutral prepared/selection contracts, native masked trace, positive
fixture, ten typed negative fixtures, and source-identity preflight are bound.
The missing root license is recorded as a `NOASSERTION` marker and no longer
blocks development, downstream execution, verification, or evidence delivery;
upstream redistribution remains excluded. Downstream VG OPQ4/prepared/
selection, CPU runtime, recoverable 10,000-step training, a five-bucket
checkpoint smoke with typed failure, and native v2 external 250-episode
diagnostics pass independently on VG and Steam. SIDScope accepts the route as a
configuration-bound named adapter through compact hash/count/metric evidence;
the full traces and upstream assets remain external.

The submitted TOIS manuscript is a frozen, separate repository. Nothing in
the 1.1 maintenance or local pre-2.0 development lines may be written back into
that submission before an explicitly authorized revision phase. Its authority is the frozen
`codex/tois-submitted-20260821` branch at
`6bc58f457194e34b785d50d746a3498c6cf47faa`, tagged
`tois-2026-0745-submitted-20260821`; it is not permanently defined by the
SIDScope `v1.0.2` product label. A future authorized revision may select a
reviewed, claim-compatible 1.x software ref, but it must not absorb local 2.x
development automatically.

The approved long-term product position is a conformance and observability
platform for Semantic-ID and generative recommender systems. SIDScope does not
own the upstream method or training layer. It owns six layers from Adapter SDK
integration through canonical contracts, native observation, diagnostic
evaluation, conformance verification, and immutable evidence. The authoritative
design and gated release sequence are `docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md`
and `docs/V1_2_TO_V2_ROADMAP.md`. Implemented and planned surfaces are marked
separately; 1.6--1.7, optional 1.8--1.9 and 2.0 target features are not claimed by
the 1.5 closure.

Architecture Sprint 0 is implemented on the 1.1.1 regression baseline.
It adds canonical version/hash governance, a machine-readable schema/profile/
producer/verifier/evidence inventory, an enforced acyclic module-dependency
matrix, the stable `sidscope` CLI facade, and the first complete vertical slice:
`sidscope.source_identity.v1` schema, Python model, validator, canonical hash,
positive fixture, typed negative fixture, and legacy adapter-manifest parity.
Sprint 1 is now implemented on `1.2.0.dev0`: the bundled
`sidscope.contract_registry.v1` is the canonical discovery and CLI-dispatch
authority, and `sidscope.dataset_identity.v1` provides a complete vertical
slice with full split/catalog/target-universe bindings plus an honest
`legacy_partial` migration. Registry unknown dependencies, cycles, unsupported
revisions, resource drift, and typed negative fixtures fail closed. This is an
unreleased development milestone and does not declare 1.2 publicly released.
Sprint 2 is also closed: `sidscope.sid_space_identity.v1` binds SID structure,
vocabulary, tokenizer/cache, collision, and de-duplication semantics, while
`sidscope.prepared_dataset.v1` binds complete DatasetIdentity and
SIDSpaceIdentity artifacts to normalized splits, artifacts, catalog, target
universe, and privacy. RPG migrates with exact fixture parity. Incomplete
DiffGRM and LLaDA legacy prepared contracts fail with a typed regeneration
requirement instead of inferred fields.

Sprints 3 and 4 are now closed together. EpisodeSelection, RunIdentity,
CheckpointBinding, TraceEnvelope, DiagnosticReport, ConformanceReport, and
EvidenceIndex complete the eleven-contract registry and fourteen-edge acyclic
dependency graph. Adapter SDK `0.1.0-alpha` and the shared adapter, contract,
trace, evaluate, verify, and evidence CLI paths are active. The common envelope
binds RPG's native parallel/unordered payload and never substitutes AR ancestry.
The canonical fixture has eight typed failures; report metrics and partitions
are independently recomputed; evidence packaging rejects missing dependencies,
cycles, and privacy violations.

The legacy migration matrix covers all six generator routes and nine static
mapping routes. RPG is the first exact end-to-end canonical fixture. Other
routes retain their existing verifier and status authority and receive a typed
canonical-regeneration disposition; this is not an adapter failure or implicit
promotion. The six shared command families have an eleven-repeat CPU baseline
and a 20% review policy. This closes 1.2 development scope, but does not create
a public 1.2 tag or release.

The 1.3 ecosystem milestone is also development-closed. SDK `0.2.0-alpha`
retains SDK 0.1 descriptor compatibility and binds each current capability
descriptor to one native payload schema. Lazy entry-point discovery uses
`sidscope.adapters`; listing reads metadata only and explicit preflight loads
one selected plugin. Five payload families preserve AR prefix, parallel
graph/token-set, masked diffusion, latent retry, and decoder-overlay semantics.
Their hash-bound registry, composable common/family profiles, five positive
fixtures, and seven typed negatives are independently verified.

The separately packaged `reference-parallel` plugin installs without core
edits. The isolated verifier first proves payload verification with no plugin
installed and then proves discovery/preflight after installation. RecBole is
only availability-probed and never imported. Existing named-adapter evidence is
unchanged.

The 1.4 evidence-system milestone is development-closed. EvidenceBundle v1 is
an immutable, canonical-JSON contract that binds profile, dataset, SID space,
run, checkpoint, trace, diagnostics, conformance, result-card, privacy, and
supersession identity. Semantic artifact identity (`content_sha256`) is kept
separate from exact stored-byte identity (`object_sha256`). The content-addressed
object store admits public bytes atomically, retains restricted assets as
hash-only references, and fail-closes on tampering, hash collision, forbidden
content, invalid provenance, and unsupported exact-rank claims.

SQLite is a disposable local projection, not evidence authority. It can be
deleted and deterministically rebuilt from active and quarantined immutable
bundles; the static export remains byte-equivalent. Corrections create a new
bundle with an explicit supersession edge. Comparison reports metric deltas
only when profile revision, dataset, target universe, cutoff, publication
depth, and rank semantics are compatible. The `sidscope evidence bundle` and
`sidscope registry` command families close build, verify, admit, import, list,
show, compare, supersede, quarantine, export, and rebuild workflows while the
legacy evidence-package path remains compatible.

The 1.5 conformance/submission milestone is development-closed. A hash-bound
profile catalog governs `static_mapping_c0_c5`, `generator_g0_g5`,
`overlay_g0_g5`, and `release_local` at revision `1.0.0`. Each profile has an
owner, ordered gates, typed failures, positive and negative fixtures,
migration/deprecation policy, and a status-label policy. DatasetProfileDescriptor
v1 binds split, catalog, target-universe, evaluation and privacy identity;
ProfileConformanceReport v1 derives its decision and status label from the
catalog rather than accepting a caller-written promotion.

EvidenceSubmission v1 provides a path-safe independent checker for structure,
completeness, compatibility, claims and privacy. It calls the public profile and
EvidenceBundle validators and never imports upstream code. The checked-in
external-adapter package passes; eight profile negatives and nine submission
negatives fail with their declared codes. Passing and registered partial/close
reports may enter deterministic status/result indexes; failing reports cannot.
The indexes contain no local paths or timestamps and rebuild byte-identically.
Legacy ledgers remain read-only authorities for unmigrated routes; complete
1.1.1 replay or archival stays in 1.6 rather than being fabricated in 1.5.

The 1.6 hardening milestone is development-closed. Its executable matrix tests
the package, SDK, canonical-schema, profile, native-payload and EvidenceBundle
axes with positive and typed-negative cases. All fifteen 1.1.1 routes now have
hash-bound migration records: RPG retains canonical replay parity and the
remaining incomplete routes retain immutable historical records with explicit
regeneration requirements. A deterministic status projection preserves ledger
parity without manufacturing metric-bearing results.

The public onboarding instructions replay the independently packaged
`reference-parallel` adapter in an isolated CPU environment without core edits.
Compatible EvidenceBundle fixtures compare parallel graph/token-set and masked
diffusion families under one exact dataset/target/rank contract. The candidate
Python exports, twenty-nine CLI leaf commands, and seven legacy compatibility
wrappers are machine-inventoried; every wrapper has an owner, support interval,
and archive decision. ADR-0012 and `docs/MIGRATING_1_X_TO_2_0.md` govern the
transition. This closure creates no 1.6 tag or public-release claim.

ADR-0010 places compatibility, migration and external-adoption hardening in
1.6 before 2.0 declares the proven interfaces stable. ADR-0013 activates 1.7
for contract and public-surface stabilization. It catalogs 45 public schema
IDs across 27 resources, orders Draft 2020-12 before Python semantic
validation, validates all 19 CLI result envelopes, introduces a curated
39-symbol `sidscope` facade, centralizes semantic producer versions, and
enforces cross-module facade imports. ADR-0014 keeps release-view separation in
the same 1.7 workstream: `runtime`, `conformance`, and `evidence-full` are
strict additive profiles under one version and manifest authority. Versions
1.8--1.9 remain optional. ADR-0015 keeps GitHub on the 1.1.x maintenance line,
keeps pre-2.0 engineering local, and treats the TOIS package as an independent
exact-ref authority rather than a permanent product-version constraint.

The verified workspace policy keeps `SIDScope-v1.1` as the 1.1.x maintenance
surface and this `SIDScope-v2` worktree on `codex/sidscope-v2` as the only
1.2--2.0 development surface. GitHub `sidscope/main` remains on 1.1.x; the
local pre-2.0 commits are not authorized for push. The independent frozen TOIS
repository remains a non-merge target.

On 2026-08-29, the first authors of DIGER, LETTER, and ReSOT supplied direct
email clarifications for research use. DIGER's author states that the code is
MIT and that its Hugging Face artifacts may be used for research under the
same terms; the repository LICENSE is pending. LETTER's author permits use of
the code, datasets, and SID indexes for SIDScope research with citation and
acknowledgment of the CIKM 2024 paper; a repository license is planned.
ReSOT's author permits the released code, datasets, checkpoints, and SID
indexes for noncommercial academic research with citation of the KDD 2026
paper. All three repositories still return no detected LICENSE file, so the
inventory retains `no_license_detected` while recording these author
clarifications in `license_identifier`. Raw correspondence is private and is
not part of the public resource package. Existing non-redistribution policies
remain unchanged until repository-level terms make redistribution explicit.

## Canonical development surface

- Repository: the standalone `SIDScope-v2` worktree, not the historical
  `SIDInspector` workspace.
- Branch: `codex/sidscope-v2`.
- Upstream tracking branch: none for the local `codex/sidscope-v2` branch.
- Current GitHub main version: `1.1.1.dev0`; latest public release tag:
  `v1.1.0`.
- Historical software/resource release associated with the submitted TOIS
  snapshot, public `v1.0.2`:
  `6ae5c4f02da3eae0cf187683d9af4c7c66e8cfa0`.
- Frozen TOIS source authority: branch `codex/tois-submitted-20260821`, commit
  `6bc58f457194e34b785d50d746a3498c6cf47faa`, tag
  `tois-2026-0745-submitted-20260821`.
- RPG P0 implementation commit before this handoff update:
  `60e421fb2736ceeead3cff0f7ac9e2cd23a04b95`.
- Regression authority: `1.1.1.dev0` in the separate `SIDScope-v1.1` worktree.
- Development version: `1.7.0.dev0` in both `pyproject.toml` and `setup.py`.
- Public release tag: `v1.1.0` at
  `a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3`.
- Deterministic tag archive SHA-256:
  `2b71bc8ad2128a2ce9d214b4fc13840e797e7c12bba6a7f063ff18d3abf2c65f`.

Always begin a resumed session by verifying the live branch, HEAD, worktree,
remotes, version, manifest, tests, and verifier. Do not assume the commit above
is still HEAD after handoff or release work.

## Non-negotiable boundaries

1. Do not develop in the historical `SIDInspector` directory. It contains
   unrelated projects and historical uncommitted experiments.
2. Do not edit, copy new evidence into, rebuild, or retag the frozen TOIS
   submission repository.
3. Do not commit checkpoints, raw datasets, embeddings, real `.sem_ids`
   caches, private paths, remote payloads, credentials, or source item IDs.
4. Do not push `codex/sidscope-v2`, change the public 1.1.x line, create a
   formal release tag, or push `main` without explicit user authorization.
5. Static item-to-SID admission is C0--C5. Generator and decoder admission is
   independently G0--G5. Passing one protocol never implies passing the other.
6. Do not promote a route to `named_adapter` unless all G0--G5 gates pass with
   the required source, identity, trace, resolution, export, fixture, smoke,
   hashes, and verifier evidence.

## Completed 1.1.0 work

### Core intake and protocol

- Local Latte/Sentence-T5 model paths are identified by filesystem semantics,
  not by model-name guessing.
- The tokenizer-only Latte extra uses optional `faiss-cpu` and
  `sentence-transformers`; Hugging Face `datasets` is not required.
- C0--C5 and G0--G5 are separate typed admission protocols.
- Coverage records distinguish reference traces, close named adapters, source
  audits, source watch, and complete named adapters.

### Latte/PSID trained adapter

Latte/PSID passes G0--G5 as a configuration-bound named adapter. Its closure
includes:

- pinned official source revision and license boundary;
- official-code-derived static cache evidence and real item/vocabulary
  round-trip;
- checkpoint- and split-bound PSID ordered-beam traces;
- checkpoint- and split-bound Latte latent-retry traces;
- two public, deidentified five-episode real smoke bundles;
- two external 250-episode diagnostics bound by hashes and counts;
- typed expected-failure bundles;
- a CPU verifier that is rerun by the resource-package verifier.

The v2 trained-trace contract preserves legitimate early-ended or invalid
beams without fabricating evidence. It supports raw token slots, decoded and
ancestry lengths, PAD or null tail slots, typed termination/failure labels,
and complete final-beam retention. PSID evaluation slots preserve original
top-k rank without backfilling invalid positions. Target-universe identity is
bound to canonical normalized-item/SID rows and does not expose source IDs.
Schema v1 trained bundles are not auto-upgraded.

Relevant evidence and contracts:

- `docs/LATTE_PSID_GENERATOR_ADAPTER.md`
- `docs/reproducibility/latte_psid_adapter_status.json`
- `docs/reproducibility/latte_psid_trained_trace_evidence.json`
- `examples/latte_psid_trained_trace_real_smoke/`
- `tools/verify_latte_psid_adapter.py`
- `tools/verify_latte_psid_trained_trace_bundle.py`

### Release preparation

- Package version promoted from `1.1.0.dev0` to `1.1.0`.
- Release checklist, public release packet, maintenance guide, changelog,
  roadmap, README, adapter ledgers, and manifest were updated.
- G8 now upgrades old environment pip to `pip>=21.3` before editable install,
  fixing the Apple command-line-tools Python 3.9 failure mode.
- Release archives use sorted paths and fixed ZIP metadata, making independent
  builds byte-for-byte deterministic.

Important implementation commits:

- `45e2547` -- close the Latte/PSID trained adapter.
- `3de91eb` -- prepare SIDScope 1.1.0.
- `3f46f03` -- make the release archive deterministic.

## Completed 1.1.1.dev0 P0 work

RPG now passes G0--G5 as a configuration-bound named adapter. The closure
uses the pinned CC BY-NC source and real official-code-derived Beauty cache,
without vendoring upstream code or assets. The formal run completed 127 epochs
and 12,827 updates, selected epoch 107 by validation NDCG@10, and stopped after
the configured patience of 20.

The public package contains a five-episode deidentified trained smoke with 43
bounded normalized-item/SID resolution rows. An external 250-episode primary
contains the complete 12,101-row target universe; the public evidence binds it
by SHA-256, counts, split, checkpoint, training manifests, resumable state,
runner, exporter, verifier, and target-universe hash. The external primary has
8 Hit@10 episodes (`Recall@10=0.032`).

Relevant evidence and contracts:

- `docs/RPG_GENERATOR_ADAPTER.md`
- `docs/reproducibility/rpg_kdd2025_adapter_status.json`
- `docs/reproducibility/rpg_kdd2025_trained_trace_evidence.json`
- `examples/rpg_generator_trained_trace_real_smoke/`
- `tools/run_rpg_resumable_training.py`
- `tools/export_rpg_trained_trace.py`
- `tools/verify_rpg_trained_trace_bundle.py`

### Dataset-neutral RPG bridge

The post-P0 maintenance surface now includes a generic prepared-data bridge for
frozen downstream protocols. It binds normalized split/catalog/SID artifacts,
completed training hashes and an explicit ordered episode-selection manifest.
The upstream `Pipeline` cannot accept a dataset instance as annotated because
it calls the returned instance; SIDScope therefore constructs the unmodified
official RPG tokenizer/model over a checked `AbstractDataset` implementation.

The bridge schemas are `sidscope.rpg_prepared_dataset.v1`,
`sidscope.rpg_episode_selection.v1`, `sidscope.rpg_trained_trace_bundle.v2`,
and `sidscope.rpg_downstream_handoff.v1`. Synthetic positive and typed failure
fixtures pass, as does a one-epoch CPU prepared runner/export/verifier smoke.
Beauty's real schema-v1 five-episode bundle remains the regression authority.
No unrun downstream dataset inherits Beauty's named-adapter evidence.

The resumable runner now writes `sidscope.rpg_resumable_state.v2` atomically at
every epoch with cumulative epoch records, then atomically updates the
hash-bound `sidscope.rpg_epoch_ledger.v1`. A real two-stage CPU regression
completed epoch 1, removed the normally written invocation manifest to model a
post-checkpoint interruption, and resumed to epoch 2 using only the embedded
records plus the exact ledger. The final manifest preserves continuous epochs,
global steps, and model-state hashes. Legacy checkpoints without embedded
records require a matching continuous legacy manifest or fail closed.

Prepared v2 traces may now add the backward-compatible
`sidscope.rpg_rank_depth_diagnostic.v1` extension. It separates the frozen
evaluation cutoff from ranked-item publication depth, preserves all existing
training/prepared/selection/checkpoint and graph bindings, and requires exact
target ranks to have an ordered supporting row. Missing targets are typed as
right-censored beyond the published depth unless an in-depth SID collision
proves a resolution failure. The frozen VG RPG configuration uses 20 beams, so
its method-faithful complete ranking depth is 20 even when depth 100 is
requested; ranks 21+ remain right-censored unless a separately authorized run
changes the beam/graph experiment.

See `docs/RPG_NON_AR_BRIDGE.md`.

## Historical generator-route gate status (configuration-bound records)

The machine-readable authority is
`docs/reproducibility/generator_adapter_coverage.csv`.

| Route | Current gate state | Allowed description | Next closure |
| --- | --- | --- | --- |
| Latte / PSID | G0--G5 pass | `named_adapter` | Maintain v2 compatibility and rerun both public real smoke bundles for every release archive. |
| RPG | G0--G5 pass on the pinned Beauty configuration | `named_adapter` | Maintain the bounded public smoke and rerun external training evidence only when the pinned source, cache, or configuration changes. |
| TIGER / DACT | G0--G5 pass on released Tools configuration, including refreshed 500-target dual-mode ancestry export | `named_adapter` | Maintain compact external-trace evidence; rerun only when pinned inputs or configuration change. |
| LLaDA-Rec | G0--G5 pass on frozen VG: formal 10,000-epoch official tokenizer, prepared round-trip, recoverable 10,000-step generator, native five-bucket trace, typed failure, and external 250 diagnostic | `named_adapter` | Maintain compact external evidence and rerun only when the tokenizer, generator, data, or configuration changes. |
| DiffGRM | G0--G5 pass independently on frozen VG and Steam OPQ4/10,000-step configurations, including five-bucket native v2 smokes and external 250 diagnostics | `named_adapter` | Maintain both compact configuration records; rerun only when pinned inputs change. |
| Item-Supported Decoding | Content-addressed snapshot, fail-closed overlay contract, and exact-function smoke; G0 revision identity partial, G1 fixture, G5 partial | `close_named_adapter` | Obtain an immutable official revision; bind data/checkpoints and export a real overlay trace. |

RPG must retain unordered token-set identity and graph-valid completion; it
must never be converted into a TIGER-style autoregressive prefix trace.
LLaDA-Rec must retain diffusion/remasking state. ISD remains a decoder overlay,
not a standalone generator.
DiffGRM must retain forward noising and adaptive masked-position filling; RPG's
32-position OPQ cache is not compatible with DiffGRM's four-position OPQ4
identity and must never be cropped or silently converted.

## Historical milestone release evidence (current checks are recorded above)

The last complete release-gate baseline was the 1.6 development tree. The 1.7
stabilization tree has now completed its source-tree and archive/G8 gates:

- 1.2--1.3 focused code-review regression: `29 passed`; the review hardened
  dependency revisions, report/status cross-bindings, exact-rank resolution,
  SDK type failures, native ancestry/episode uniqueness, and registry safety;
- full tests: `285 passed, 6 skipped` on the 1.7 tree;
- resource-package verifier: PASS;
- contract-registry verifier: PASS with 11 canonical contracts, 11 positive
  fixtures, 12 typed-negative fixtures, and 14 declared dependency edges;
- Sprint 2 verifier: PASS with exact RPG migration parity and typed
  regeneration-required outcomes for DiffGRM/LLaDA legacy prepared artifacts;
- 1.2 execution/report/SDK legacy closure and fifteen-route migration matrix:
  PASS;
- 1.3 ecosystem verifier: PASS with SDK `0.2.0`, five native payload families,
  six composable profiles, five positive fixtures, seven typed negatives,
  no-plugin core validation, and external `reference-parallel` installation;
- 1.4 evidence-system verifier: PASS with three positive immutable bundles,
  three typed negative fixtures, one embedded CAS object, seven hash-only
  objects, supersession, quarantine/rebuild, compatible comparison, typed
  incompatible-comparison rejection, and SQLite delete/rebuild parity;
- 1.4 CLI CPU baseline verifier: PASS under the 20% review policy; seven-repeat
  medians are 5.098 ms bundle build, 4.226 ms verify, 8.374 ms registry add,
  5.051 ms compare, 3.953 ms list, and 10.041 ms rebuild;
- 1.5 conformance-ecosystem verifier: PASS with four governed profiles, four
  positive reports, eight typed profile negatives, one positive external
  submission, nine typed submission negatives, deterministic status/result
  indexes, and migrated-row legacy parity;
- 1.6 hardening verifier: PASS with six compatibility axes and six typed
  negatives, fifteen legacy route records, one retained canonical replay,
  fourteen immutable historical records, isolated external-plugin onboarding,
  compatible parallel-versus-masked comparison, eight candidate Python
  modules, 188 exports, twenty-nine CLI leaves, and seven owned wrappers;
- profile status-index SHA-256:
  `cc358f11903680bc99a5baa2127e0d91150f531b41e0976263989386015b3589`;
- profile result-index SHA-256:
  `71ee3ea7c485a0885c65ac66e4a9b7e5a938dd954f3a5a1e0b2601b9e69e66af`;
- release-metadata verifier: PASS;
- architecture inventory verifier: PASS with 204 schema IDs, 11 canonical
  contracts, 10 profiles, 6 generator routes, 9 static-mapping routes, and 15
  canonical evidence edges;
- release archive build: PASS;
- extracted archive smoke: PASS;
- G8 isolated `sidinspector==1.6.0.dev0` install and deterministic archive
  rebuild: PASS;
- RPG non-AR bridge verifier: PASS, including Beauty v1 regression, generic v2
  positive fixture, typed duplicate-selection failure, and the hash-bound CPU
  runner/export smoke;
- DiffGRM staged verifier: PASS, including source-identity preflight,
  dataset-neutral positive fixture, and ten typed expected failures; the
  independent external-bundle CLI and its v2 binding/negative tests also pass;
- LLaDA-Rec verifier: PASS, including the formal tokenizer, recoverable
  10,000-step generator, five-bucket checkpoint smoke, typed ancestry failure,
  and external 250-episode native v2 diagnostic;
- manifest: 331 rows, 328 public rows, 0 pending;
- resource-package verifier: 358 required files, 549 public files, and 552
  tracked files checked with no forbidden-content findings;
- release-profile verifier: PASS with strict `runtime < conformance <
  evidence-full` containment, receipt/path tamper rejection, and large trained
  traces admitted only to `evidence-full`;
- current profile surfaces including the generated receipt: 114 runtime files,
  429 conformance files, and 550 evidence-full files;

The additive 1.7 focused verifier passes with 45 public schema IDs,
27 schema resources, 19 CLI result schema IDs, 39 curated facade symbols, two
validation layers and two typed negatives. The 1.6 compatibility/API replay
also passes on the 1.7 tree. The full tests, resource verifier, release metadata
verifier, architecture inventory verifier, archive build, and extracted archive
smoke all pass after the final 1.7 implementation and manifest update. The
post-handoff deterministic double-build reproduces identical bytes, and the G8
fresh-environment install/replay passes with `sidinspector==1.7.0.dev0`.
The default G8 target is now the installable `runtime` profile; the
`conformance` and `evidence-full` profiles retain their own extracted archive
smokes.

The development archive SHA-256 is intentionally reported by the final build
command rather than embedded in this hash-sensitive source tree. Rebuild it
after any source or documentation change.

## Required verification commands

Run from the repository root:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
python3 -m pytest -q
python3 tools/verify_sidscope_resource_package.py
python3 tools/verify_sidscope_contract_registry.py
python3 tools/verify_sidscope_sprint2_contracts.py
python3 tools/verify_sidscope_1_2_closure.py
python3 tools/verify_sidscope_1_2_legacy_migration_matrix.py
python3 tools/verify_sidscope_1_2_cli_baseline.py
python3 tools/verify_sidscope_1_3_plugin_ecosystem.py
python3 tools/verify_sidscope_1_4_evidence_system.py
python3 tools/verify_sidscope_1_4_cli_baseline.py
python3 tools/verify_sidscope_1_5_conformance_ecosystem.py
python3 tools/verify_sidscope_1_6_hardening.py
python3 tools/verify_sidscope_1_7_stabilization.py
python3 tools/verify_sidscope_release_profiles.py
python3 tools/build_sidscope_release_candidate_archive.py \
  --profile runtime --output /tmp/sidscope-v1.7.0.dev0-runtime.zip
python3 tools/build_sidscope_release_candidate_archive.py \
  --profile conformance --output /tmp/sidscope-v1.7.0.dev0-conformance.zip
python3 tools/build_sidscope_release_candidate_archive.py \
  --profile evidence-full --output /tmp/sidscope-v1.7.0.dev0-evidence-full.zip
python3 tools/smoke_sidscope_release_candidate_archive.py \
  /tmp/sidscope-v1.7.0.dev0-runtime.zip --profile runtime
python3 tools/smoke_sidscope_release_candidate_archive.py \
  /tmp/sidscope-v1.7.0.dev0-conformance.zip --profile conformance
python3 tools/smoke_sidscope_release_candidate_archive.py \
  /tmp/sidscope-v1.7.0.dev0-evidence-full.zip --profile evidence-full
python3 tools/run_sidscope_g8_fresh_env_smoke.py \
  --archive /tmp/sidscope-v1.7.0.dev0-runtime.zip --profile runtime \
  --result-json /tmp/sidscope_g8_fresh_env_smoke.json
```

The release checks are CPU-only. A new GPU run is not required to reverify the
already closed RPG evidence. GPU work is required only for a newly scoped
trained route such as LLaDA-Rec.

The separate public URL gate passed for `v1.1.0` and should be rerun after any
future public release-surface change:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/sidscope.git \
  --ref v1.1.0 \
  --result-json /tmp/sidscope_public_url_smoke.json
```

## Published release record

No additional internal implementation is required for the agreed 1.1.0
boundary. Publication is closed as follows:

1. annotated tag `v1.1.0` created and pushed;
2. release commit `a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3`
   published to `sidscope/main`;
3. unauthenticated public URL smoke passed against the tag;
4. final tag, commit, URL, archive checksum, and transcript are recorded in
   `docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md`.

RPG, DiffGRM VG/Steam, TIGER/DACT, and LLaDA-Rec VG trained/released-checkpoint
closure are complete in 1.1.1.dev0. ISD immutable-source/data/checkpoint closure
remains a post-1.1.0 maintenance item. These changes must not silently alter the
immutable 1.1.0 claim.

## Resume protocol

1. Read this file, `docs/V1_2_TO_V2_ROADMAP.md`, `docs/CONTRACT_REGISTRY.md`,
   `docs/COMPATIBILITY.md`, the two conformance documents,
   `docs/VALIDATED_ADAPTERS.md`, the generator coverage CSV,
   `docs/SIDSCOPE_MAINTENANCE.md`, and the release checklist/packet.
2. Verify the live Git and package state before making claims.
3. Inspect the release manifest and run focused tests before changing adapter
   status.
4. Preserve unrelated worktree changes; never clean them destructively.
5. Keep the submitted-paper freeze separate from software maintenance.
6. Report outcomes as `LOCAL_RELEASE_READY` and `PUBLIC_RELEASED` separately.

Expected status at this handoff:

```text
LOCAL_DEVELOPMENT_READY_1_7_DEV0: PASS
LOCAL_DEVELOPMENT_READY_1_1_1_DEV0: PASS
LOCAL_PRE_2_0_BRANCH_PUSHED: NO
PUBLIC_GITHUB_MAIN_LINE: 1.1.x
PUBLIC_RELEASED_1_1_1: NO
PUBLIC_RELEASED_1_1_0: YES
PUBLIC_RELEASE_TAG_1_1_0: v1.1.0
PUBLIC_RELEASE_COMMIT_1_1_0: a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3
LATTE_PSID_NAMED_ADAPTER: PASS_G0_G5
RPG_NAMED_ADAPTER: PASS_G0_G5
DIFFGRM_VG_NAMED_ADAPTER: PASS_G0_G5
DIFFGRM_STEAM_NAMED_ADAPTER: PASS_G0_G5
DACT_TIGER_NAMED_ADAPTER: PASS_G0_G5
TOIS_FROZEN_SUBMISSION: UNCHANGED_EXACT_REF_AUTHORITY
TOIS_FUTURE_REVISION_VERSION: NOT_PRECOMMITTED_SELECT_EXPLICIT_COMPATIBLE_1_X
```
