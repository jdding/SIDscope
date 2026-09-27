# SIDScope 2.0 engineering candidate freeze

Status: engineering candidate only; package `1.7.0.dev0`; certification gated on
same-source delivery evidence, with
independent_user_actual_use excluded from current gates
(ADR-0025, 2026-09-27) and still not verified.
No RC, tag, push or release authorized.

## Frozen compatibility inputs

- 46 public schema IDs backed by 28 schema resources;
- 19 CLI result schema IDs and 31 CLI leaf commands;
- 39 curated `sidscope` facade symbols;
- stable Adapter SDK `1.0.0`, plugin API `1.0`, and exact current descriptor
  interval `>=1.0.0,<2.0.0`;
- opt-in local workflows for audit/evaluate/compare, mapping preflight,
  producer admission, paired regression, diagnostic review and SID refresh;
- additive `runtime < conformance < evidence-full` release profiles.

The machine authority is
`docs/reproducibility/sidscope_1_7_public_surface.json`; this document does not
replace it. N09 notebook specialization, N10 additional static review packaging,
hosted services, training frameworks and method implementation are excluded.
Existing HTML diagnostic review is retained; N10 does not reopen it.

## Two-stage verdict

```bash
python3 tools/verify_sidscope_2_0_candidate.py --require-engineering-ready
python3 tools/verify_sidscope_2_0_candidate.py --require-certification-ready
```

The first command must pass once all technical gates are green. The second must
return a typed blocked result until the same-source delivery summary exists and
verifies: `delivery_ready` requires valid receipts for every required gate bound
to the clean candidate. Independent user actual use is excluded from current
gates by the acceptance scope policy (`docs/reproducibility/sidscope_acceptance_scope.v1.json`,
ADR-0025); no user trial, sign-off or adoption evidence is required or accepted.
The policy fails closed on missing, unknown or over-broad exclusions, and any
required technical condition that loses verified coverage (for example N03)
re-enters gating. When the delivery summary verifies, an authorized change may
set an RC version from a new clean commit and rerun the same gates.

## RC transition

The engineering candidate runs wheel/sdist, all three profile archives, the
Linux/Python matrix and a detached exact-source record v2 before F09 so delivery
defects do not hide behind human acceptance. Only after certification readiness
is true may a separately authorized change set `2.0.0rc1`; that RC commit must
rerun the same gates and populate a new public release packet. Push, tag and GitHub Release remain separate
explicit actions.

Record v2 embeds and binds the current six-command CPU observation and its narrow delivery
disposition to the exact source snapshot. Platform-version-only variance can be
accepted only when every frozen workload stays inside the original 20% threshold;
other environment, workload or performance drift remains blocked. The raw
observation status is preserved and the baseline is never rewritten.
