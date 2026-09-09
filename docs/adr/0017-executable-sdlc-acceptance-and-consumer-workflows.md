# ADR-0017: Executable SDLC acceptance and public consumer workflows

Date: 2026-09-08. Status: implementation authorized in the local 1.7 line.

## Decision and constraints

Keep the existing Python local-first modular monolith, SHA-256 immutable
artifacts and derived SQLite indexes. Add no service, training ownership,
sign-off policy or product version. Existing code owners remain responsible;
automation supplies reproducible checks, not an invented independent reviewer.

1. Public file consumers share strict JSON validation. ADR-0018 supersedes the
   original shared byte-cap policy for trusted local workflow/export intake;
   canonical/SDK defaults and untrusted submission budgets remain. Invalid inputs fail
   before admission. Historical artifact bytes are not regenerated.
2. Target-state truth tables and native projection checks distinguish actual
   exported facts from unavailable rank/generation/catalog facts. In particular,
   resolution-event order never becomes a ranking or synthetic AR ancestry.
3. `sidscope.workflows` exposes mapping audit, ranked-output evaluation and
   compatible comparison, reusing D1/D2/D5 and the canonical metric kernel.
   Reports copy their input snapshot and are recomputed before comparison.
   Missing inputs remain unavailable; no automatic SID repair or causal claim.
4. A versioned external consumer pins all 39 facade signatures/defaults and
   exercises positive/error/return behavior. Existing historical exports are not
   automatically added to this promise. New workflow contracts have their own
   consumer tests; implementation module names are not user-facing dependencies.
5. Distribution acceptance builds wheel and sdist from a separate source copy,
   installs outside the checkout, records resolved dependency hashes, and repeats
   installation offline with `--require-hashes`. Only executed OS/Python cells
   are recorded as passing. Open dependency constraints are not a lock.
6. The source-side local release record lives outside candidate archives and
   binds HEAD, dirty status, exact public source bytes, executed test output,
   build environment, profiles and archive/tree hashes. A receiver pins the
   record digest before loading it and the archive digest before executing code.
   This identifies dirty development candidates without certifying a public
   release. No signature service or manual receipt policy is introduced.
7. The requirement ledger links persona, journey, actual accountable owner,
   dependencies, implementation, tests, execution command and disposition.
   Implemented, verified, user-accepted, delivery-ready and release-authorized
   remain distinct. Current documentation blocks are generated from this ledger
   and the historical route ledger; a stale block fails the gate.

## Alternatives rejected

More handwritten route/status glue would keep the drift and fragmented workflow.
A new hosted registry, second metrics framework or mandatory approval/signature
layer adds no demonstrated benefit. Expanding all 188 historical exports into
the stable facade would create an unnecessary compatibility promise.

## Exit, unresolved dependencies and rollback

Engineering exits require the actual tests, mutation failures, distribution
matrix and content-bound local release record. A local pass is not a published
release or a new named-adapter/training certification. Independent user adoption
must come from an actual user's run; the implementing agent cannot manufacture
it. If unavailable, record pending actual use and continue independent work.

Jiandong Ding (`jdding`, existing CODEOWNERS) remains accountable. When no second
reviewer is assigned, record that limitation rather than invent a backup or
signature authority. No approval is needed merely to rerun these CPU checks.

Rollback retains the previous local source and old consumer fixtures. New reports
use new files; old evidence, tags, 1.1 maintenance and TOIS refs remain untouched.
Changes to acceptance semantics must update code, tests, ledger, ADR, manifest,
verifiers and HANDOFF together. Do not make all states green by rewriting scope.
