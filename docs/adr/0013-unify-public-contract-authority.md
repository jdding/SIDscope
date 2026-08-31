# ADR-0013: Unify Public Contract Authority Before Stable 2.0

Status: Accepted

Date: 2026-08-31

## Context

SIDScope 1.2--1.6 produced sound canonical models and evidence, but three
public surfaces could drift independently: bundled JSON Schemas, Python
semantic validators, and CLI result schema IDs. The broad historical
`sidinspector` exports also made it difficult to state which Python API should
be stable in 2.0. Native payload JSON Schemas are intentionally less expressive
than their method-faithful semantic validators, so validating only one layer is
not sufficient.

## Decision Drivers

- fail closed across structural and semantic validation;
- provide one discoverable owner for every public schema ID;
- retain exact historical evidence bytes and the 1.6 rollback point;
- expose a small API that can credibly receive a 2.0 compatibility promise;
- keep SIDScope a local-first modular monolith without adding a service.

## Options

| Option | Benefit | Cost or risk |
| --- | --- | --- |
| Treat Python validators as the only authority | Minimal code | External tools cannot discover machine-readable structure; CLI schemas remain implicit |
| Treat JSON Schema as the only authority | Standard tooling | Cannot express all ancestry, transition, hash and metric invariants without duplicating complex logic |
| Use a catalog plus ordered structural and semantic validation | One discoverable surface while preserving rich validators | Requires synchronized ownership and compatibility tests |

## Decision

Activate 1.7 as a bounded contract and public-surface stabilization release.
Every bundled `*.schema.json` resource is public by convention and must declare
one or more unique schema IDs. The runtime catalog assigns every ID an owning
module and semantic validator. `sidscope schema validate` first applies Draft
2020-12 JSON Schema, then calls that owner. Neither layer substitutes for the
other.

All public CLI JSON passes through one result-envelope validator. New Python
integrations use the curated `sidscope` facade; `sidinspector` remains the
distribution and historical replay namespace. Cross-module source imports must
use package facades, and architecture tests resolve relative as well as absolute
imports.

Semantic producer versions are centralized and do not automatically follow the
package version. Packaging-only changes therefore do not invalidate immutable
artifact hashes.

## Consequences

Positive: public schemas are enumerable, structural/semantic drift is testable,
CLI output failures are typed consistently, and the 2.0 candidate API is small.

Negative: adding a schema now requires owner registration and two validation
layers; `jsonschema` becomes an explicit core dependency; broad historical
imports remain a maintenance obligation until their documented retirement.

## Migration and Validation

The change is additive. Existing CLI leaves, `sidinspector` imports, schema IDs,
schema revisions, producer strings and artifact bytes remain valid. New users
may move imports to `sidscope` incrementally. The deterministic authority is
`docs/reproducibility/sidscope_1_7_public_surface.json`; verify it with
`tools/verify_sidscope_1_7_stabilization.py`, architecture tests, the full suite,
resource-package verification, archive smoke and G8.

## Rollback

Pin the passing 1.6 surface and remove only the additive `sidscope` facade,
schema commands, shared CLI envelope and catalog. Do not modify historical
artifacts, 1.6 evidence, tags, adapter status or frozen TOIS assets.
