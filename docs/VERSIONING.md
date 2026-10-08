# SIDScope Versioning and Release Governance

<!-- SIDSCOPE:CURRENT:BEGIN -->
Local development: `1.7.0.dev0`; public GitHub remains 1.1.x; 1.8/1.9 inactive.
Current diagnostic admission and comparison require input-bound recomputation; declarations alone do not pass.
Unclosed SDLC requirements: F09.
Requirement snapshot: `d84f1b924e203550bd953ad5254467d09079fc49aee229ed85e189e890ac0e2c`.
Acceptance scope: `docs/reproducibility/sidscope_acceptance_scope.v1.json` revision 2 snapshot `fc0ab4a29822290d43eb190364443c5afbc7d288de57ed30988f0269f26db9db`.
Acceptance scope decision: independent_user_actual_use excluded from current gates (2026-09-27, docs/adr/0025-remove-independent-user-acceptance-gate.md); the adoption fact stays not_verified.
Historical route decisions (not newly recomputed training): dact_tiger=named_adapter; diffgrm_www2026=named_adapter; isd=close_named_adapter; latte_psid=named_adapter; llada_rec=named_adapter; rpg_kdd2025=named_adapter.
Historical route snapshot: `cb51983ca33506c4c00f1722eda8e5eb9eb452409ce026f9810a76fe1cf02a92`.
Independent user actual use is excluded from current certification, RC and delivery gates by acceptance scope policy revision 2; it remains not verified and is not a current prerequisite. No push, tag, public release or TOIS mutation is authorized.
<!-- SIDSCOPE:CURRENT:END -->

Status: active; current development baseline `1.7.0.dev0`

## Sources of Truth

| Surface | Purpose | Update rule |
| --- | --- | --- |
| `README.md` | Current stable/development entry point and supported commands | Review every release; edit when current onboarding or product behavior changes. |
| `docs/SIDSCOPE_CHANGELOG.md` | Human-readable release history | Update for every release. |
| Git tag and GitHub Release | Immutable release identity and public artifacts | Create for every authorized formal release. Never move a published tag. |
| Release manifest | Machine-readable public package boundary | Update for every release-surface change. |
| `docs/COMPATIBILITY.md` | Package, SDK, schema, profile, and bundle compatibility | Update whenever a supported version axis changes. |
| Migration notes | User actions required to upgrade | Required for incompatible or action-requiring changes. |
| ADRs | Durable architecture decisions and rejected options | Add only for significant decisions; supersede rather than rewrite. |
| Product roadmap | Current milestone, exit gates, and deferred work | Update when milestone state or sequencing changes. |

README is not a cumulative changelog. A tag already freezes the README that
belonged to that release.

## Version Axes

SIDScope tracks five independent compatibility axes:

1. product/package version, governed by semantic versioning;
2. Adapter SDK version;
3. schema major ID plus semantic schema revision;
4. conformance-profile version;
5. evidence-bundle format version.

Changing one axis does not silently advance another. The compatibility matrix
records supported combinations.

## Product Version Rules

- Patch: compatible fixes, validation corrections that preserve meaning, and
  documentation/evidence refreshes.
- Minor: additive public CLI/API, contracts, profiles, or evidence capability.
- Major: incompatible public contract or compatibility-policy changes.
- Development builds use `.devN`; release candidates use `-rc.N` tags while the
  Python version uses a PEP 440-compatible `rcN` form.

`pyproject.toml` is primary package metadata. `setup.py` is a compatibility shim
and must carry the same distribution name, version, package data, and console
entry point until retired by an ADR.

## Repository and Publication Lines

Product versions do not by themselves identify where a change is published or
which manuscript package uses it. The current authorities are deliberately
separate:

| Surface | Current authority | Promotion rule |
| --- | --- | --- |
| Public GitHub | `sidscope/main` on the 1.1.x maintenance line | Remains 1.1.x until an explicit user-authorized push or release changes the public line. |
| Local pre-2.0 development | `SIDScope-v2` on `codex/sidscope-v2` | Local commits may advance through 1.2--1.9 toward 2.0, but do not imply a tag, push, GitHub release, or public compatibility promise. |
| TOIS submission/revision | Exact frozen manuscript branch, commit, tag, and archived package | The submitted package remains untouched. A future revision chooses and verifies an explicit claim-compatible 1.x software snapshot; local 2.x is never inherited automatically. |

`v1.0.2` remains an immutable historical release associated with the submitted
TOIS snapshot. It is not a permanent prospective version constraint for every
future editorial revision. Historical tags and release records are never moved
or rewritten.

## Pre-2.0 Stabilization Sequence

The roadmap intentionally uses three distinct release responsibilities:

- 1.5 completes the additive conformance and submission feature surface;
- 1.6 hardens compatibility, migration, external adoption and candidate API
  stability without adding another owned product layer;
- 1.7 is activated for contract and public-surface stabilization: unified
  schema discovery, structural-to-semantic validation, CLI result envelopes,
  a curated Python facade, executable module boundaries, and additive
  runtime/conformance/evidence-full release profiles;
- 1.8--1.9 remain optional reserved slots for later explicitly approved
  additive or hardening work;
- 2.0 reruns the final gates against the last passing 1.x baseline and makes the
  stable public compatibility promise.

A major version is not used as a backlog container. Any unresolved migration,
first-time external onboarding, unowned wrapper or undocumented breaking change
blocks 2.0 and remains on the active 1.x line. If additional additive work is later
required, it receives another 1.x minor version rather than being hidden inside
the 2.0 release candidate.

Reserved 1.8--1.9 numbers are not placeholder releases. A number is used only
after its scope, compatibility delta, migration, rollback and exit gates are
approved and documented. Unused numbers may be skipped, and no empty tag or
synthetic changelog entry is created merely to keep the sequence contiguous.

The historical 1.6 candidate surface is machine-readable in
`docs/reproducibility/sidscope_1_6_public_api_inventory.json`. Any change to a
listed CLI leaf command, Python export, compatibility wrapper owner, support
interval, or archive decision requires a compatibility review and an updated
migration action before 2.0.

The additive 1.7 delta and current candidate surface are machine-readable in
`docs/reproducibility/sidscope_1_7_public_surface.json`. Semantic producer
versions remain independent of package-only releases so unchanged canonical
artifact bytes do not drift merely because the distribution version advances.
Release-profile IDs select assets inside one product version and never consume
a new minor version by themselves.

## Release Flow

```text
short-lived feature branch
  -> reviewed main candidate
  -> vX.Y.Z-rc.N (when an RC is needed)
  -> local release gates
  -> immutable vX.Y.Z tag
  -> GitHub Release and artifacts
  -> unauthenticated public URL smoke
  -> finalized public release packet
```

`main` is the current releasable line. A long-lived maintenance branch is used
only when an older line must receive fixes while newer development continues.
Tag creation, push, and public publication always require explicit release
authorization. Under the current repository policy, this generic flow applies
to public 1.1.x maintenance only; the local pre-2.0 branch stops before the
`reviewed main candidate` step unless separately authorized.

## Required Release Record

The 2.0 platform decision (ADR-0027, 2026-10-08) replaces the required Linux
four-cell gate with an explicit unsupported/deferred declaration in catalog
v2 and delivery summary v2. Platform support is limited to executed acceptance
listed in `docs/COMPATIBILITY.md`. This decision authorizes scope and local
evidence updates, not an RC version bump or public publication.

Every formal GitHub Release records version, tag, commit, release date,
compatibility, breaking changes, migration, schema/profile/SDK/bundle versions,
adapter status, known limitations, test/verifier/archive/G8 outcomes, artifact
URLs, and SHA-256 values. Use `docs/SIDSCOPE_RELEASE_TEMPLATE.md`.
