# ADR-0010: Separate 1.6 Hardening from the 2.0 Stability Declaration

## Status

Accepted on 2026-08-30. This decision partially supersedes ADR-0004 only where
ADR-0004 expected legacy and target modules to coexist through 1.5; the
coexistence and retirement window now extends through 1.6 hardening.

## Context

The original roadmap moved directly from 1.5 conformance/submission features to
2.0. The 2.0 gates nevertheless required work that had not been assigned to a
pre-stable milestone: multi-version compatibility, complete legacy migration,
external plugin adoption, cross-family comparison, interface freeze and wrapper
retirement. Treating those as 2.0 implementation would mix product development
with the major-version stability promise and make rollback ambiguous.

## Goals

- make compatibility and migration proof an explicit, reversible milestone;
- keep 2.0 focused on stable-contract declaration and final certification;
- preserve immutable evidence, historical verifiers and released tags;
- expose ownership, retirement and adoption gaps before the major release.

## Non-Goals

- adding a seventh SIDScope product layer;
- introducing a hosted registry, service runtime or dashboard;
- changing the method/training boundary;
- requiring new GPU evidence when method, data, checkpoint and configuration
  identity are unchanged.

## Constraints

- SIDScope remains a local-first modular monolith and CPU-verifiable package;
- `SIDScope-v1.1` remains the 1.1.x maintenance authority and the TOIS
  repository remains frozen and separate;
- admitted bundles and published tags are immutable;
- the distribution/import remains `sidinspector` through 1.x unless a separate
  ADR and deprecation window authorize a change.

## Decision Drivers

| Priority | Driver | Measurement |
| ---: | --- | --- |
| 1 | Honest stability promise | 2.0 contains no unresolved migration or first-time adoption work. |
| 2 | Compatibility confidence | Every supported version interval has positive and typed-negative CI. |
| 3 | Reversibility | A failed hardening gate returns to a passing 1.5 profile/CLI without evidence mutation. |
| 4 | External usability | One independent adapter onboards and one cross-family comparison passes before 2.0. |
| 5 | Ownership | Every compatibility wrapper has an owner and retirement/archive state. |

## Options Considered

| Option | Advantages | Disadvantages | Reversibility |
| --- | --- | --- | --- |
| Move directly from 1.5 to 2.0 | Short roadmap and fewer version labels. | Hides migration/adoption work inside the stability release and weakens rollback. | Medium. |
| Add 1.6 compatibility, migration and adoption hardening | Separates feature completion, proof and stability declaration; provides a clean rollback point. | Adds one governed milestone and release record. | High. |
| Pre-plan both 1.6 and 1.7 | More scheduling capacity. | Invents scope before 1.6 evidence identifies a need. | High, but unnecessarily speculative. |

## Decision

Add 1.6 as the mandatory pre-stable hardening milestone. Version 1.5 completes
profiles and submission workflows. Version 1.6 proves supported compatibility
intervals, migrates or archives legacy authorities, completes independent
external adoption and cross-family comparison, freezes candidate public
interfaces, and rehearses the 2.0 release gates. Version 2.0 reruns those gates
and declares only the proven surface stable.

If 1.6 reveals additional additive product work, that work receives another
1.x minor version. It is not silently moved into the 2.0 candidate.

## Architecture Impact

- runtime and deployable topology do not change;
- immutable bundles remain evidence authority and SQLite remains derived;
- 1.5 profiles and legacy replay paths coexist through 1.6;
- compatibility matrices become executable release evidence rather than prose;
- 2.0 accepts only interfaces with demonstrated 1.6 support intervals;
- hosted services, dashboards and training execution remain out of scope.

## Rollout, Validation, and Rollback

Roll out one compatibility interval or legacy route at a time. Require
multi-version CI, deterministic migration replay, generated-ledger parity,
external plugin onboarding, compatible cross-family comparison, wrapper-owner
audit, archive smoke and G8. A red gate pins the last passing 1.5 combination,
keeps the previous profile active, quarantines only newly invalid bundles and
defers 2.0. No rollback rewrites historical evidence or a released tag.

## Consequences

Positive:

- the major release becomes a credible compatibility commitment;
- migration risk has an explicit cutover and rollback boundary;
- external adoption is demonstrated before interfaces are frozen;
- additional 1.x work remains possible when hardening exposes real gaps.

Negative and tradeoffs:

- the path to 2.0 contains one more formal milestone;
- compatibility matrices and wrapper ownership add maintenance work;
- 2.0 may be delayed when a hardening gate finds an unresolved contract issue.

## Links

- `docs/V1_2_TO_V2_ROADMAP.md`
- `docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md`
- `docs/COMPATIBILITY.md`
- `docs/VERSIONING.md`
- ADR-0004: `docs/adr/0004-module-boundaries-and-cli-identity.md`
