# SIDScope Acceptance Gates

Status: active journal-extension gate
Date: 2026-08-08
Project name: SIDScope
Paper title: SIDScope: Artifact-Level Diagnostics for Semantic-ID Generative Recommendation
Target venue: ACM Transactions on Information Systems (TOIS), as a disclosed substantial extension of the accepted CIKM 2026 Resources paper

## Target Acceptance Tier

The preparation target is a submission-ready TOIS substantial extension:

```text
TARGET_READINESS: TOIS_SUBSTANTIAL_EXTENSION_WITH_REVIEWER_VERIFIABLE_RESOURCE
CURRENT_READINESS: CONTENT_GATES_PASS_PRIVATE_V1_FROZEN_PUBLIC_ACCESS_AND_SUBMISSION_METADATA_OPEN
TARGET_INTERPRETATION: build standard, not a guaranteed acceptance probability
CIKM_V0_RESULT_DEPENDENCY: RESOLVED_ACCEPTED_2026_08_07
VENUE_SWITCH_GATE: V0_V1_DELTA_AND_VENUE_GATE.md
```

Historical 70% conference-readiness labels are development records only. They
must not appear in the journal manuscript, cover letter, or release claims.

## Gate Semantics

All gates in this document are construction gates. A gate is not a request to
look around, survey feasibility, or confirm what the repo already has. A gate is
complete only when the project has built the artifact, experiment, package, or
evidence object needed for the 70% target.

Prechecks and audits are allowed, but they are not gate completion. They can
only create a build backlog, downgrade decision, or stop condition.

Allowed gate statuses:

- `BUILD_NOT_STARTED`: the required deliverable does not exist yet;
- `BUILD_IN_PROGRESS`: construction is underway, but the gate cannot support a
  paper claim yet;
- `BUILT_PASS`: the required deliverable exists and passes the stated standard;
- `BUILT_FAIL`: the deliverable was attempted and did not meet the standard;
- `DOWNGRADED`: the project intentionally lowers the target because the gate
  cannot be built to the 70% standard.

## Current Gate Status

```text
NUMBERING_POLICY: experiments/v1_evidence_chain/GATE_NUMBERING.md
G15_VENUE_STATUS: BUILT_PASS_TOIS_SUBSTANTIAL_EXTENSION_SELECTED
G1_PRECHECK_STATUS: COMPLETE
G1_CURRENT_STATUS: BUILT_PASS_FOR_ARTIFACT_COVERAGE_AND_FAITHFUL_INTAKE_R116_R118_R138_R145_R147_R151_R752
G1_PRECHECK_ARTIFACT: experiments/v1_evidence_chain/GATE1_RESULT.md
G1_BUILD_PLAN: experiments/v1_evidence_chain/GATE1_BUILD_PLAN.md
G1_TARGET_STATUS: BUILD_TO_70_TIER
G2_BUILD_STATUS: PREFIX_CANDIDATE_EXPOSURE_REFRESHED_WITH_FAITHFUL_GRID_CARD_RESOT_DIGER_R201_R205_R151_R752_R760_R764
G2_CURRENT_STATUS: BUILT_PASS_FOR_TWO_VERTICAL_UTILITY
G2_PRECHECK_ARTIFACT: experiments/v1_evidence_chain/gate2_cross_dataset_utility/GATE2_RESULT.md
G3_BUILD_STATUS: CONTROLLED_EXPOSURE_SIGNAL_REFRESHED_WITH_FAITHFUL_GRID_CARD_RESOT_DIGER_R206_R208_R151_R752_R760_R764
G3_CURRENT_STATUS: BUILT_PASS_FOR_CONTROLLED_EXPOSURE_SIGNAL
G3_PRECHECK_ARTIFACT: experiments/v1_evidence_chain/gate3_controlled_exposure/GATE3_RESULT.md
G4_CURRENT_STATUS: BUILT_PASS_FOR_CLUSTER_AWARE_STATISTICAL_VALIDATION_R209_R760_R764_WITH_CARD_RESOT_DIGER
G4_ARTIFACT: experiments/v1_evidence_chain/gate35_cluster_reanalysis/GATE35_RESULT.md
G5_CURRENT_STATUS: BUILT_PASS_FOR_D7_DIAGNOSTIC_CASE_R301_R305
G5_ARTIFACT: experiments/v1_evidence_chain/gate4_d7_diagnostic/GATE4_RESULT.md
G6_CURRENT_STATUS: BUILT_PASS_FOR_REAL_FORMAT_D7_BEAM_LABELING_R306
G6_ARTIFACT: experiments/v1_evidence_chain/gate45_real_beam_d7/GATE45_RESULT.md
G7_CURRENT_STATUS: BUILT_PASS_FOR_BOUNDED_PUBLIC_TRACE_ACCOUNTING_R307_R310
G7_ARTIFACT: experiments/v1_evidence_chain/gate46_d7_per_beam_trace_join/GATE46_RESULT.md
G8_CURRENT_STATUS: REVIEWER_PACKAGE_PRIVATE_V1_FROZEN_R834_PUBLIC_NO_LOGIN_SMOKE_PENDING
G8_ARTIFACTS: docs/SIDSCOPE_RESOURCE_PACKAGE.md; docs/SIDSCOPE_DATASHEET.md; docs/SIDSCOPE_LIMITATIONS.md; docs/SIDSCOPE_MAINTENANCE.md
G9_CURRENT_STATUS: CLAIM_TABLE_FIGURE_LEDGER_CLOSED_FOR_CURRENT_ARTIFACT_REGISTRY_R510
G9_ARTIFACT: experiments/v1_evidence_chain/CLAIM_LEDGER.md; docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv
G10_CURRENT_STATUS: BUILT_PASS_FOR_DISJOINT_USER_AND_SAMPLED_RANKING_UTILITY_ANCHORS_R701_R703
G11_CURRENT_STATUS: BUILT_PASS_BOUNDARY_CONTROL_AND_PARTIAL_NON_PREFIX_SCORING_R709_R711
G12_CURRENT_STATUS: TRAINED_GENERATOR_BOUNDARY_CHECKS_CLOSED_NEGATIVE_R724_R732_R733_R742
G13_CURRENT_STATUS: BUILT_PASS_RESOURCE_USAGE_DEMO_R745
G14_CURRENT_STATUS: BUILT_PASS_R752_CARD_RQVAE_OFFICIAL_CODE_DERIVED_ROW_ADDED
G16_CURRENT_STATUS: BUILT_PASS_BOUNDARY_NEGATIVE_R753_TRAINED_GENERATOR_EXACT_AUDIT_NO_C9_SUPPORT
G17_CURRENT_STATUS: BUILT_PASS_SOURCE_PROVENANCE_AND_RESOT_DIGER_MATRIX_PROMOTION_R754_R764
G18_CURRENT_STATUS: R781_LATTE_PSID_ROUTE_VERIFIED_NOT_PROMOTED_NO_MATRIX_CHANGE_R782_R785_DEFERRED
G19_CURRENT_STATUS: R791_R792_LOCAL_TRACE_EXPORT_AND_D7_LABEL_SMOKES_PASS_VALID_ONLY_R793_OPTIONAL
CURRENT_ACCEPTANCE_PROBABILITY_BAND: RESOURCE_PACKAGE_LAYER_READY_TOIS_EXTENSION_GATES_OPEN
```

Current build evidence supports two existing official upstream snapshot rows
(`LETTER`, `LC-Rec`), plus built ReSID-HF control/reference rows on
`Musical_Instruments` and `Video_Games`. It now also supports a counted
official-code-derived ReSID GAOQ row from R116 and a second-vertical ReSID GAOQ
pilot from R118. R124 validates the returned AutoDL archive, command logs,
normalized outputs, and hashes. R138 also validates an R133-audited existing
GRID export as a counted local GRID row. R145 adds slim collected follow-up
evidence for R140-R144. G2 is now built-pass for two-vertical prefix candidate
exposure utility and has also been refreshed with the faithful GRID/P5 Beauty
and CARD RQ-VAE/P5 Beauty paper-named rows: R201-R205 evaluate 270
refresh-scope rows across Musical_Instruments, Video_Games, and Beauty. G3 is
also built-pass: R206-R208 report the candidate-exposure signal with target
popularity, popularity bucket, depth, SID length, full collision, prefix
collision, duplicate SID rate, dataset, and tokenizer-family controls over 810
primary controlled rows.
G5 is now built-pass: R301-R305 provide a deterministic D7 synthetic fixture,
reverse lookup labels, constrained-survivable vs unconstrained-only separation,
and a Prefix-Capacity Gate0 negative case showing constrained unresolved rate
`0.0`.
The post-audit content gates add four important boundaries. R146 confirmed a
faithful upstream GRID tokenizer route exists via `snap-research/GRID`. R147-R151
then completed that upgrade for P5 Beauty through
`rkmeans_train_flat -> rkmeans_inference_flat -> item_id + sid_level_*`.
R138 remains paper-facing only as a local existing RQKMeans-style
stress/reference artifact. G4/R209, R760, and R764 rerun G2/G3 with
artifact-cluster-aware uncertainty after the faithful GRID, CARD, ReSOT, and
DIGER refreshes: effective artifact `n=11`, artifact-depth `n=33`, and the
controlled G3 coefficient remains
positive with cluster-bootstrap and wild-cluster CIs. G6/R306 runs D7 labeling over four existing public
generator-beam exports (`2,000,000` beam rows, `20,000` traces) with perfect
SID reverse-lookup consistency and zero invalid paths; it validates real-format
scale, not trained-generator failure prediction.
R139 refreshes the current Gate 1 matrix after GRID closure.
G7 is now built-pass as a bounded public-beam trace-outcome join. R307 found
an eligible public-beam source, R308/R309 joined `2,000,000` public beam rows to
`240,000` target-survival rows, and R310 synthesized the result. The join has
perfect agreement with the S2 target-survival accounting after respecting each
row's beam-width budget. It does not authorize GPU work and does not support
trained-generator failure prediction because trained G6 per-beam rows remain
missing locally and the public beams have no meaningful D7 failure-family
variation. R752 then closes the G14 coverage-expansion route by building a
complete 12,101-item CARD RQ-VAE official-code-derived item-to-SID artifact
over P5 Beauty. The row passes SIDScope normalization/preflight and has
`full_collision_rate=0.0004958267911742831`, but it must be described as
official-code-derived with a local compatibility shim, not as an
author-released CARD mapping. R205/R208/R209 now promote this row into the
paper-facing G2/G3/G4 refresh scope.

G8 now includes a release-candidate checklist, machine-readable package
manifest, local release-clean archive builder, archive-without-git smoke, and a
public release packet. The local verifier checks required docs, compact
evidence snapshots, sampled regeneration, release-manifest consistency, and
forbidden tracked package-boundary files. The archive builder writes a zip from
tracked `public_package=yes` paths and records a SHA256. The smoke test
extracts that zip without `.git` metadata and reruns the verifier plus sampled
regeneration from the extracted package. The public release packet records the
candidate GitHub URL, branch/archive surface, and G8 commands. R708 verifies a
pre-split reviewer-tag public surface. The private standalone
`jdding/SIDscope` repository is now the official release surface. R834 freezes
its manifest-built 159-file package at `v1.0.0`; the tag and `main` resolve to
the same commit and an authenticated clean clone passes the package verifier
and tests. Unauthenticated URL smoke remains pending until reviewer visibility
is enabled.
Canonical G9 table-to-artifact closure is now
recorded in `CLAIM_LEDGER.md` and
`docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv`.
G13/R745 adds a CPU-only usage demonstration over compact release snapshots. It
inspects nine artifact rows and records a reproducible triage decision table
that separates named promotion candidates, diagnostic controls, monitored rows,
manual-review rows, and stress-only rows. This closes the resource-use
walkthrough gap without making downstream model-quality claims.
G14/R751-R752 audits whether the artifact matrix can be expanded with
additional named methods. R751 found no new counted row from source/artifact
audit alone. R752 then built a complete CARD RQ-VAE official-code-derived
item-to-SID artifact over P5 Beauty, normalized it through the SIDScope CARD
adapter, and passed SIDScope preflight. CapsID, DiscRec, and CoST remain
uncounted candidates or related work until reusable item-code artifacts are
available.

R114 has added a bounded official-code-derived ReSID GAOQ driver and verified
local dependencies. R115 was attempted on AutoDL for the official ReSID
`FAMAE -> GAOQ -> item_code_mapping.parquet` route. The FAMAE smoke completed
on GPU, but GAOQ became CPU-bound and produced no raw or normalized item-code
artifact before stop-loss. The attempt is recorded in R135 and does not count.
The follow-up unbalanced-GAOQ closure is the counted route: R136/R116/R117/R118
pass, and R124 collects the returned evidence.

GRID has two separate states. R138 remains a local existing GRID-route
stress/reference validation row, with explicit warnings
(`duplicate_sid_rate=0.842094`, `full_collision_rate=0.976876`). The fresh
official P5 GRID tokenizer-stage intake has now passed for P5 Beauty through
R147-R151 and refreshes G1/G2/G3/G4. No current GPU batch is authorized after
that closure. R146/R147-R151 add the stronger conclusion: R138 must not be
called a faithful true GRID named artifact, while the R150/R151 faithful row can
carry current GRID tokenizer-stage coverage for P5 Beauty. CARD now has a
counted R752 official-code-derived RQ-VAE row, but it must not count from
adapter tests alone and must not be described as an author-released CARD
artifact.

Clarification: Gate 1 is now built-pass for artifact coverage, not paper-ready
by itself. Release packaging still needs D1-D5 refresh for R116/R118/R138 and
final license/provenance cleanup before claims are paper-facing. Any further
GPU use needs a new plan-to-run batch; the completed R115-R118 batch must not
be reused as implicit approval.

## High-Tier Gate Summary

| Gate | Required Built Deliverable | Built-Pass Condition | If Not Built |
| --- | --- | --- | --- |
| G1 Artifact coverage and faithful intake | A high-tier artifact validation matrix, not a current-state inventory. | At least four row families, including true released or auditable named tokenizer lines, ReSID-style rows, RQ-style rows, faithful GRID/P5 Beauty, and the R752 CARD RQ-VAE official-code-derived row; each has schema, join, provenance, and reproducibility evidence. | Downgrade to 35-45% resource-hardening tier or narrow named coverage. |
| G2 Cross-dataset utility | A two-vertical diagnostic utility evidence package. | D1-D5 to candidate-exposure association is evaluated on Musical plus one second vertical with same-split controls, row counts, and uncertainty. Headline association claims need at least 30 evaluated rows or an explicit small-n limitation. | Downgrade to single-dataset resource/tool paper; do not claim broad utility. |
| G3 Controlled exposure signal | A controlled exposure model/report, not raw association. | Candidate-exposure signal is reported with popularity, depth/length, collision, prefix collision, and tokenizer-family controls, plus bootstrap/seed uncertainty where applicable. | Report descriptive diagnostics only; no triage claim. |
| G4 Cluster-aware statistical validation | Paper-facing G2/G3 uncertainty with artifact-cluster effective n. | Row-level bootstrap is superseded by artifact-cluster analysis; report effective artifact n, artifact-depth n, wild-cluster controlled-model CI, and proxy/triage claim boundary. | Do not use narrow row-bootstrap CIs in paper-facing claims. |
| G5 D7 diagnostic schema and fixture | A constrained-aware D7 diagnostic fixture plus one reproducible case. | Synthetic D7 fixture passes; constrained-survivable failures are separated from unconstrained-only invalid/unresolved paths; Prefix-Capacity Gate0 negative case is summarized with the right limitation. | Keep D7 as future work or appendix-only taxonomy. |
| G6 Real-format D7 beam labeling | D7 labeler run on existing generator-beam rows. | Existing beam rows are converted to trace schema, reverse lookup is consistent, summaries are saved, and trained-vs-public-beam limitation is explicit. | Keep D7 as synthetic/negative-case only until real rows are available. |
| G7 D7 per-beam trace-outcome accounting | A bounded source audit and joined trace-outcome table. | Per-beam rows join to target outcomes and D1-D5/G2 signals under trace-accounting wording. | Stop at source audit if no eligible source exists; do not claim D7 downstream/generator failure prediction. |
| G8 Reviewer package and documentation | A reviewer-runnable package plus docs. | Public/reviewer-accessible repo or package includes quickstart, adapter schema, manifest, examples, sampled regeneration, datasheet, limitation section, maintenance plan, and no hidden login dependency. | Do not submit to Resource Track. |
| G9 Claim ledger and evidence binding | A claim-to-artifact ledger plus V0/related-work positioning record. | Every current table/claim has placement (`main`, `appendix`, or `future_work`), source rows, package-relative artifact paths, SHA256 or regeneration notes, row counts, limitations, V0-overlap notes, and positioning against SID reliability, GRID/Latte, and evaluation-toolkit neighbors. | Delay writing paper or mark missing claims as appendix-only. |
| G10 Disjoint-user and sampled-ranking utility anchors | Bounded fixed-reranker utility anchors. | Disjoint-user candidate recall and hard-negative sampled-ranking utility remain directionally positive under stated protocol boundaries. | Keep utility claims at candidate-exposure proxy only. |
| G11 Layer-C and non-prefix controls | Controls for whether the G10 utility anchor is merely a popularity or generic ranker artifact. | Target-popularity residualization remains positive; co-occurrence/popularity-only rankers are weaker; R711 non-prefix scorer is directional but uncertain and treated as boundary evidence. | Do not claim generic non-prefix downstream utility. |
| G12 Trained-generator boundary checks | Small generator runs over fixed artifact/split/budget designs. | R724/R732/R733/R742 are recorded as negative resource-boundary findings, not positive utility anchors. | Do not claim SIDScope predicts trained generator quality; keep generator claims as future work or limitation. |
| G13 Resource usage demonstration | A realistic CPU-only walkthrough over compact release snapshots. | R745 produces a triage decision table separating promotion/control/monitor/manual/stress decisions without downstream model-quality claims. | Resource-track utility narrative weakens. |
| G14 Coverage expansion and new artifact intake | A counted-row readiness audit and follow-up intake for newly surfaced named SID/tokenizer methods. | R751 audits CARD/CapsID/DiscRec/CoST; R752 adds a counted 12,101-row CARD RQ-VAE official-code-derived row after generated codes, item-id sidecar, adapter normalization, and SIDScope preflight all pass. | Do not inflate the artifact matrix from source code, paper claims, or adapter tests alone; keep non-built candidates as roadmap/related work until item-code artifacts pass preflight. |
| G15 Venue branch and final packaging decision | A final venue/delta decision tied to the CIKM V0 result. | CIKM V0 was accepted on 2026-08-07; TOIS is selected as the disclosed substantial-extension route, with the TOIS-required 50% new-content floor and an internal target of about 60% by substance. | Do not submit until the prior-publication disclosure and V0-to-SIDScope delta ledger are complete. |
| G16 Trained-generator boundary exact audit | A claim-boundary audit of existing G12/G12b/G13 generator runs. | Existing runs are collapsed to independent artifact-level rows with exact permutation tests, and the negative/boundary verdict is reflected in paper claims. | Do not claim trained-generator utility prediction. |
| G17 Source-provenance and ReSOT/DIGER intake | A post-CARD source audit plus completed matrix refresh for eligible rows. | DIGER and ReSOT are source-verified, normalized, and promoted only after D1-D5/G2/G3/G4 refresh; all other candidates remain watch/related-work rows. | Do not count new papers, repos, or partial code without item-to-SID matrix refresh. |
| G18 Tokenizer-family expansion watch | A source-watch plus optional route-verification plan for additional tokenizer families. | R780 reconciles the current watch list against G17, and R781 verifies the Latte/PSID route but stops it before promotion: no released item-to-SID artifact was found, and Latte is primarily generator-side latent-token work. RQ-VAE-Recommender and RecTokens remain reference-only routes. No paper-facing row count changes without an explicit R782-R785 reopening. | Do not treat old TIGER/RQ-VAE reference implementations or generator-side Latte code as new tokenizer-family coverage. |
| G18 Tokenizer-family expansion | A bounded new candidate watch/intake gate after ReSOT/DIGER. | A future candidate enters the paper-facing matrix only after source route, normalized item-to-SID output, preflight, D1-D5/G2/G3/G4 refresh, and claim/package sync pass. | Keep candidates as watch/related-work rows; do not inflate coverage. |
| G19 D7 trained-trace staging | A bounded D7 trained-trace export and labeling path. | R790 found no reusable per-beam source; R791/R792 then established the candidate-pool export and label smoke that G20 extends. | Treat G19 as staging evidence; the paper-facing trained constrained-beam result is G20. |
| G20 Trained trie-constrained D7 case | A reviewed trained per-beam trace export with repeated constrained-survivable labels and target outcomes. | R807-R810 pass: two GRID/P5 folds observe `ambiguous_path` over 50,000 beam rows, DIGER adds a 25,000-row portability sensitivity, and compact hashes bind full outputs. | Keep the claim at trained-beam observability and path-versus-item accounting; do not claim universal prevalence, a failure mechanism, or D1-D5 predictivity. |
| G21 Mature TIGER D7 robustness case | A released-checkpoint Transformer-style trace case under constrained and unconstrained decoding. | R820--R822 pass: released-checkpoint preflight, reviewed CUDA canary, and 500-target primary all close with matched accounting. | Promote released-checkpoint portability and constrained-aware trace accounting only; no universal prevalence, ranking-improvement, or failure-mechanism claim. |
| G22 Diagnosis-to-action re-audit | A released stale mapping, released repair, D1--D6 re-audit, and same-architecture A/B/C generator handoff. | R823--R825 pass: paired mapping audit, corrected CUDA canary, and three-seed 5,364-target primary all satisfy the preregistered recovery, new-item, validity, and accounting gates. | Promote one positive released handoff case only; no universal repair-effectiveness, causal mapping-to-quality, or general D1-D5 predictivity claim. |

## Minimum High-Tier Package

The project reaches the target preparation tier only if the submission package
contains:

0. V0/V1 delta and venue branch record;
1. artifact validation matrix for true-tokenizer and control rows;
2. candidate-exposure controlled evidence on two verticals with
   artifact-cluster-aware and wild-cluster controlled-model uncertainty;
3. deterministic D7 trace-labeling fixture plus at least one real-format
   diagnostic case;
4. optional bounded D7 per-beam trace join if a source exists, for a stronger
   main-text science claim rather than as a submission blocker;
5. reviewer-accessible resource package, currently locally verified by
   `tools/verify_sidscope_resource_package.py`;
6. tutorial or realistic quickstart, not only toy examples;
7. datasheet, manifest, hashes, license, limitation, and maintenance plan;
8. sampled table regeneration command;
9. evidence ledger mapping every paper claim to an artifact.

## Stop / Downgrade Rules

- If G1 fails, do not submit a named-tokenizer resource paper.
- Do not advertise R138 as faithful true GRID named coverage. The faithful
  GRID claim, when used, must point to the R147-R151 P5 Beauty row and carry its
  scope.
- If G15 fails after the CIKM result is known, do not submit V1 as a separate
  conference resource paper.
- If G2 or G3 fails, submit only a descriptive resource paper or delay.
- If G4 fails, remove narrow row-bootstrap CIs from paper-facing claims and
  downgrade utility to descriptive/proxy-only.
- If G11 is weak or fails, keep the non-prefix scorer result as a
  boundary/falsifier and do not describe G10/G11 as independent scoring
  evidence. R711 currently falls in this partial/boundary category.
- Because G12/R724 is a negative boundary result, keep trained-generator
  utility prediction out of the main claim and use G12 only as limitation or
  appendix evidence.
- If G8 fails, do not submit the resource claims to TOIS.
- If G8 fails but G1-G7 pass, target remains plausible but should be described
  as 55-65% internally, not 70%.
- If only schema/taxonomy exists for D7, D7 must not be advertised as a major
  contribution.
- If G7 finds no eligible per-beam trace source, stop without GPU and keep
  the current D7 claim at schema/scale/constrained-boundary level.
- If G7 produces joined traces but no stable trace-accounting signal, place
  the result in appendix or limitations and do not claim downstream prediction.
- If G18 finds no candidate with a reproducible item-to-SID route, record the
  audit and do not change the matrix or paper row counts.
- G19's valid-only smoke is superseded by G20's repeated trained constrained-
  beam observability evidence. G20 still does not authorize a universal
  prevalence or generator-failure mechanism claim.
- G20 may appear in the main paper because the same constrained-survivable
  `ambiguous_path` family is observed in two declared GRID/P5 folds. Treat this
  as repeated observability, not independent prevalence replication.
- G21/G22 primary runs remain blocked until their standalone CUDA canaries are
  complete and independently reviewed. A remote connection failure is not a
  scientific result and must not change paper claims.

## Recording Rules

For every run, record:

- run id and date;
- dataset, split, tokenizer row, and artifact source;
- command/script path;
- output artifact paths;
- row counts and failure counts;
- controls used;
- pass/fail verdict;
- paper claim affected;
- limitation or downgrade decision.
