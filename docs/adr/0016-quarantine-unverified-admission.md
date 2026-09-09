# ADR-0016: Separate structural replay from verified admission

Date: 2026-09-08. Status: implemented for diagnostic-scope admission and native-export inspection.

The project owner rejected the earlier maintainer sign-off proposal. No human
signature, approval receipt or review authority substitutes for computation.
Recompute only when needed and possible; otherwise leave the claim unverified.

## Context and decision

Caller-supplied G0-G5 pass rows, hashes and profile decisions prove neither
execution nor training authenticity. Keeping that path as new admission would
carry a known trust defect into the local pre-2.0 surface.

Keep the local modular monolith, current product version and immutable v1
artifacts. `check_submission` and default indexes require actual embedded protocol,
trace, selection and diagnostic bytes. Fixed CPU recomputation checks object
hashes, bindings, metrics, slices, failure counts and the complete result card.
Only this scope receives `diagnostics_verified`; named-adapter status, native
authenticity and training declarations remain unverified. Missing inputs retain
`independent_gate_verification_required` or a typed input failure. Profile CLI verification emits
`structure_only` and `unverified`, preserving the declared label separately.
Explicit historical replay retains old bytes and is not an admission API.

Standard Hit/Recall/NDCG values must lie in [0,1]. New comparisons require
`sidscope.evaluation_protocol.v1`, matching full selection identity, fixed
single-target Hit/NDCG definitions, cutoff, depth, censoring and slice semantics,
and independently recomputed results. Unknown measurement conditions suppress
compute deltas. Legacy declared comparisons are available only via the explicitly
named historical replay function. No automatic conversion certifies old evidence.

Submission parsing is bounded before decoding (8 MiB per artifact, 64 MiB total,
256 artifacts, depth 64). Native generation semantics remain upstream-owned.

Release receipt v2 binds each member's actual bytes and the content-map digest.
Old receipts are retained as historical artifacts but require rebuild for new
delivery verification. Self-contained hashes prove consistency, not publisher
authenticity: a separately trusted archive digest is still a release requirement.

## Alternatives and consequences

- Keeping permissive admission would preserve behavior but retain the defect.
- Calling self-authored receipts verified would merely move the same defect.
- Fixed CPU verifiers execute available input-bound checks locally. Fudan cluster
  compute is the selected route when necessary checkpoint inference cannot be
  done locally and the required permitted inputs are available.
- Manual sign-off and compulsory retraining are rejected. Unavailable or
  unnecessary computations are not run and their claims are not verified.

The initial blanket quarantine is superseded only by this bounded positive path.
Regression PASS does not mean named-adapter admitted, user-accepted or
certification-ready. The implementation produces input-bound computations, not signed labels.
No self-review or historical fixture is counted as new external adoption.

## Exit and rollback

Exit requires gate-specific required inputs, fixed verifier identity/revision,
input/output binding, independent recomputation where available, typed negatives
and a real positive verified path. Private hash-only claims remain unverified;
they neither acquire trust through sign-off nor require retraining merely to
make a checklist green. See `../SIDSCOPE_SDLC_HARDENING.md`.

Rollback may pin the previous local commit for historical replay. Do not enable
its permissive path as trusted new admission, mutate historical evidence, or
change any public/tag/TOIS authority. The admission quarantine must be explicitly
superseded by a reviewed positive-path implementation, not removed for green CI.
