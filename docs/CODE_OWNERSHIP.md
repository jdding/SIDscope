# SIDScope Code Ownership

ADR-0021 uses the existing Evaluation/Diagnostics owners for paired statistics
and offline reviews, and the existing release maintainers for installed consumers
and repeatable CPU measurements. No ownership transfer or new on-call role.

Status: active for the local 1.7 development line

This document defines review authority by product responsibility. GitHub path
matching is recorded in `.github/CODEOWNERS`; this table remains the human
governance authority when one maintainer currently fills several roles.

Actual accountable maintainer: Jiandong Ding (`jdding`, matching CODEOWNERS).
Automated consumer and delivery checks do not represent a second human reviewer.
No backup reviewer has been assigned; if the maintainer is unavailable, retain
the candidate and its evidence without authorizing publication. Do not invent
an assignee, require a signature, or block already authorized independent CPU
development merely because publication or independent user acceptance is pending.

| Surface | Owner role | Required review | Failure boundary |
| --- | --- | --- | --- |
| Current architecture diagram and code map | Core and Evidence maintainers | diagram source/preview parity; real code paths; requirement states; no private assets | reject stale view without changing runtime or evidence |
| Canonical contracts and schemas | Core contract maintainer | compatibility, canonical hash and negative-fixture review | reject the schema or revision |
| Conformance profiles and reports | Profile maintainer | owner, semantic version, fixtures, status policy and migration review | keep the prior profile active |
| Built-in and external adapters | Named adapter or plugin maintainer | native-semantics, capability and source-boundary review | disable the adapter; retain core verification |
| Observed-native canonical bridge (ADR-0020) | Adapter and Evidence maintainers | actual input bindings, best-checkpoint metadata, original-input rebuild and privacy review | reject the new submission; retain original native assets |
| Evidence bundles, registry and submission | Evidence maintainer | provenance, privacy, admission and deterministic-rebuild review | quarantine the new object or submission |
| Release manifests, archives and public indexes | Release maintainer | package boundary, version consistency and fresh-environment review | do not tag or publish |
| Security and privacy policy | Core and release maintainers jointly | fail-closed scanner and disclosure-boundary review | block admission and export |

No owner may bypass another surface's gate by editing a generated status or
result index. Profile approval does not authorize redistribution, adapter
approval does not admit evidence, and a passing local release does not imply a
public release.

Ownership changes require this document and `.github/CODEOWNERS` to change in
the same reviewed commit. Temporary compatibility wrappers additionally need a
named role, support interval and retirement or archived-history decision.
