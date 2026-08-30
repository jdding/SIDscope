# SIDScope Code Ownership

Status: active for the 1.5 development line

This document defines review authority by product responsibility. GitHub path
matching is recorded in `.github/CODEOWNERS`; this table remains the human
governance authority when one maintainer currently fills several roles.

| Surface | Owner role | Required review | Failure boundary |
| --- | --- | --- | --- |
| Canonical contracts and schemas | Core contract maintainer | compatibility, canonical hash and negative-fixture review | reject the schema or revision |
| Conformance profiles and reports | Profile maintainer | owner, semantic version, fixtures, status policy and migration review | keep the prior profile active |
| Built-in and external adapters | Named adapter or plugin maintainer | native-semantics, capability and source-boundary review | disable the adapter; retain core verification |
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
