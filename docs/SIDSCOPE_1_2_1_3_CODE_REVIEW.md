# SIDScope 1.2--1.3 Code Review

Status: closed before 1.6 implementation

Review date: 2026-08-30

## Scope

The review covered the 1.2 canonical contract registry, runtime/report
contracts, Adapter SDK and CLI facade, plus the 1.3 plugin lifecycle, native
payload families and composable profile registry. It checked correctness,
fail-closed behavior, compatibility, optional-runtime isolation, architecture
dependencies and unnecessary complexity.

## Findings and Repairs

| Severity | Surface | Finding | Repair and regression |
| --- | --- | --- | --- |
| P1 | Contract registry | Dependency compatibility accepted any revision-set intersection, so a declaration could mix one supported and one unsupported revision. | Require every accepted dependency revision to be supported; added a mixed-revision negative. |
| P1 | Diagnostic report | Standalone validation did not bind the overall slice to the top-level evaluation and did not range-check slice metrics. | Enforce count/metric equality for `overall` and `[0,1]` slice metrics; added count and range negatives. |
| P1 | Conformance report | `fail` or `partial` decisions could disagree with otherwise passing gates. | Derive the only allowed decision class from gate states while retaining `fixture_pass` for all-pass fixtures. |
| P1 | Native AR payload | Duplicate beam IDs and discontinuous prefixes across consecutive steps were accepted. | Reject duplicates and require `prefix_before[n] == prefix_after[n-1]`; added both typed negatives. |
| P1 | Canonical trace | An exact target rank could be asserted while the target was unresolved. | Reject `exact_rank_without_resolution`; added a typed negative. |
| P2 | Adapter SDK | A non-object capability descriptor leaked `AttributeError` instead of a typed SDK error. | Add an object guard returning `invalid_type`. |
| P2 | Legacy profile registry | Duplicate profiles/gates, unknown parents, malformed rows and unsupported method families were not fully checked at registry load. | Added a public fail-closed registry validator and duplicate-profile negative. |
| P2 | Native payload registry | Registry paths and negative-fixture rows were not validated as safe canonical resources. | Added safe relative-path, row-shape, uniqueness and optional repository-resource checks. |

## Compatibility Result

All checked-in positive 1.2 and 1.3 fixtures retain their prior meaning. The
1.2 closure verifier and 1.3 plugin-ecosystem verifier pass unchanged. The
repairs only reject inputs that were internally contradictory, malformed or
outside their declared compatibility interval.

## Complexity Review

`runtime_contracts._runtime`, `runtime_schema_path` and `report_schema_path`
had no callers and exposed no supported public behavior. They and their unused
resource imports were removed instead of being carried into the candidate 2.0
surface.

`net: -15 lines possible.` Applied in this review.

## Verification

- focused contracts/SDK/plugin/profile/architecture tests: `29 passed`;
- full suite after repairs: `261 passed, 6 skipped`;
- 1.2 closure verifier: PASS;
- 1.3 plugin ecosystem verifier: PASS, including isolated plugin install and
  no-plugin core verification.
