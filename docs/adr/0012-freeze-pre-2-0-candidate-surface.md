# ADR-0012: Freeze the Pre-2.0 Candidate Surface Through Executable Inventories

Status: Accepted

Date: 2026-08-30

## Context

SIDScope 1.2--1.5 established canonical contracts, plugins/native traces,
immutable evidence, profiles, submissions and derived views. A prose promise
that these surfaces are stable is insufficient for 2.0: legacy routes differ
in migration completeness, external adoption must work without core changes,
and compatibility wrappers need explicit owners and end states.

## Decision Drivers

- preserve method-native semantics and immutable historical evidence;
- prove compatibility without inventing missing legacy fields;
- keep the local-first modular monolith and external-plugin boundary;
- make CLI/Python changes reviewable before stable 2.0;
- retain a reversible 1.5 rollback point.

## Options

| Option | Benefit | Cost/risk |
| --- | --- | --- |
| Declare 2.0 from prose and tests | Fastest release | Hidden surface drift and unowned migration debt |
| Add a new compatibility service/registry | Centralized policy | Duplicates authority and adds operations not required by the product |
| Freeze executable inventories in the existing package | Deterministic, local, reviewable, reversible | Tracked fixtures and owner records require maintenance |

## Decision

Use the existing modular package and add deterministic 1.6 artifacts for the
six compatibility axes, legacy migration/status records, candidate Python/CLI
surface, external-plugin replay, and compatible cross-family comparison. The
verifier rebuilds the expected documents and rejects tracked drift. Historical
routes without complete canonical inputs receive immutable records and typed
regeneration requirements, not fabricated bundles or promotions.

The inventory is a pre-stable candidate contract. Listed surfaces cannot be
removed before 2.0 without a documented compatibility change and migration.
Every legacy wrapper carries an owner, support interval and archive decision.

## Consequences

Positive: 2.0 can be based on measured support rather than intent; third-party
onboarding and cross-family comparison are demonstrated; the architecture gains
no new deployable or source of truth.

Negative: exported symbols and CLI leaf commands now require synchronized
inventory updates; retained wrappers remain maintenance obligations through
2.x; historical records do not magically make incomplete routes canonical.

## Migration and Validation

Generate fixtures with `tools/build_sidscope_1_6_hardening_fixtures.py` and
verify with `tools/verify_sidscope_1_6_hardening.py`. CI runs independent gates
for compatibility, migration, adoption, comparison and API ownership, plus the
existing Python/archive/fresh-environment suite. The user migration actions are
in `docs/MIGRATING_1_X_TO_2_0.md`.

## Rollback

Retain the passing 1.5 profiles, CLI and legacy verifiers and defer 2.0. Remove
only new derived 1.6 state; immutable bundles, historical records, released
tags and frozen TOIS artifacts are never rewritten.
