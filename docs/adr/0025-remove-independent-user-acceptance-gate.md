# ADR-0025: Remove the independent-user acceptance gate for the current scope

Status: accepted project-owner scope decision, 2026-09-27. The package remains
`1.7.0.dev0`; no RC, tag, push or public release is authorized.

## Context and decision

F09/N01 combined a technical condition (two distinct-family producer chains
running through validation, evaluation, bundle and comparison without core
edits) with a deliberately human condition (an independent user actually running
the workflow). The project owner decided on 2026-09-27 that independent user
actual use is no longer a certification, RC or delivery precondition for this
round: no independent user trial is scheduled, and readiness must not wait for
or imply adoption, sign-off or sign-back.

The decision is recorded as a versioned, machine-validated condition-scope
policy, `docs/reproducibility/sidscope_acceptance_scope.v1.json`
(`tools/sidscope_acceptance_scope.py`). It maps acceptance conditions to
requirement rows and carries exactly one excluded condition,
`independent_user_actual_use` (requirements F09/N01), with its decision date,
owner, rationale and the explicit fact that adoption remains `not_verified`.
The producer technical chains stay `required` and are covered by verified
requirement rows (N03 for the two producer chains; N03+N04 for the approved
single-command observed-review workflow). No ledger row is rewritten: F09/N01
keep `state=partial` and `user_accepted=pending_actual_use`, and
`tools/verify_sidscope_sdlc_acceptance.py` still rejects any recorded
`user_accepted=yes` without a traceable evidence file and matching SHA-256.

Readiness gating becomes policy-driven. The hardening verifier no longer
special-cases `{F09, N01}`; a requirement is out of gating only when every
policy condition mapped to it is excluded or covered by verified requirements.
If a covering requirement (for example N03) regresses, or a policy entry is
missing, unknown, duplicated, or tries to exclude any technical condition
(F01/F02/F11 producer/admission/input-safety chains), the verifiers fail closed
with typed codes (`scope_policy_missing`, `scope_policy_invalid`,
`scope_policy_unknown_requirement`, `scope_policy_forbidden_exclusion`,
`scope_requirement_unmapped`). State separation follows the delivery design:
`implementation_ready`, `delivery_ready` and `certification_ready` are distinct;
without a current-source delivery summary, `delivery_ready` and
`certification_ready` stay false even when implementation is complete.

## Consequences, migration and rollback

`pending_acceptance` becomes empty while `excluded_acceptance` records
`independent_user_actual_use`; the fact stays `not_verified` in generated status
blocks and hand-edited plan/RC/freeze documents, which must carry the scope
sentence ("independent_user_actual_use excluded from current gates") or the
verifier fails. Candidate readiness no longer names the user condition as a
blocker; `certification_ready` additionally requires delivery evidence, so the
`--require-certification-ready` gate stays blocked until the delivery summary
exists. Certification means current engineering-scope compliance only; it does
not claim training authenticity, adoption or publication.

Rollback reverts the scope policy, verifier and documentation changes for this
decision without touching historical evidence, ledger bytes, public 1.1.x
history, TOIS refs or adapter-native semantics. Old receipts keep their original
policy interpretation and are never rewritten under the new policy.
