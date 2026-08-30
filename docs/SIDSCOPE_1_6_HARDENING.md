# SIDScope 1.6 Compatibility, Migration and Adoption Hardening

Status: development-closed on `1.6.0.dev0`; no tag or public release implied

## Scope

SIDScope 1.6 proves the 1.5 platform surface before a stable 2.0 promise. It
does not add a method layer, training runtime, hosted service, second registry,
or new evidence semantics. The deployable shape remains one local-first modular
Python package plus separately installed adapter plugins.

## Executable Evidence

| Gate | Authority | Required result |
| --- | --- | --- |
| Six compatibility axes | `docs/reproducibility/sidscope_1_6_compatibility_matrix.json` | package, SDK, schema, profile, payload and bundle positive plus typed-negative cases pass |
| Legacy migration | `docs/reproducibility/sidscope_1_6_legacy_migration_records.json` | all fifteen routes bind their authority and verifier by SHA-256 |
| Derived legacy status | `docs/reproducibility/sidscope_1_6_legacy_status_index.json` | deletion/rebuild is byte-identical and status-parity preserving |
| Candidate API | `docs/reproducibility/sidscope_1_6_public_api_inventory.json` | exports and CLI commands match runtime; every wrapper is owned and archived or retained |
| External adoption | `examples/reference_adapter_plugin` and `docs/CONTRIBUTING_ADAPTERS.md` | isolated install/preflight passes without core edits |
| Cross-family comparison | `examples/compatibility_hardening_fixture` | parallel and masked bundles compare under one exact compatibility contract |

Run all CPU-only gates with:

```bash
python3 tools/build_sidscope_1_6_hardening_fixtures.py
python3 tools/verify_sidscope_1_6_hardening.py
```

The builder is deterministic. A tracked artifact that differs from rebuilt
canonical bytes fails rather than being silently refreshed by the verifier.

## Legacy Migration Semantics

RPG has a retained canonical replay path. The other routes are immutable
historical migration records when their old evidence lacks a complete current
contract surface. Their existing status remains authoritative and their exact
authority/verifier bytes are bound. Moving such a route to the canonical path
requires a newly generated artifact; 1.6 never guesses a missing split hash,
SID identity, trace, checkpoint, report, or bundle.

The legacy status projection is an archival view, not a 1.5 admission result.
Current status and result indexes continue to derive only from passing profile
reports and validated EvidenceBundles. This prevents a historical label from
becoming a synthetic metric-bearing result.

## External Adoption and Comparison

The independently packaged reference adapter is absent in a core-only
environment, appears only after installing its distribution, and preflights
through the public `sidscope` CLI. The verifier hashes the core package tree
before and after the replay. The comparison fixtures are explicitly synthetic
contract fixtures; they demonstrate compatible cross-family comparison and do
not represent scientific method results.

## Rollout and Rollback

Rollout keeps 1.5 profiles/commands and historical verifiers active while 1.6
gates run. Rollback pins the last passing 1.5 surface and defers 2.0; it never
rewrites a bundle, migration record, released tag, or frozen TOIS asset. Owners
are listed in the candidate API inventory and `docs/CODE_OWNERSHIP.md`.
