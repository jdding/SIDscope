# ADR-0024: Freeze the 2.0 engineering candidate before certification

Status: accepted local implementation scope, 2026-09-09. The package remains
`1.7.0.dev0`; no RC, tag, push or public release is authorized.

## Context and decision

The product owner chose to stabilize the Adapter SDK at 1.0 and authorized all
remaining technical and delivery closeout except F09 independent-user actual
use. Engineering completion and certification must therefore be separate
machine states. Treating a green automated suite as user adoption was rejected.

The exact candidate authority remains
`docs/reproducibility/sidscope_1_7_public_surface.json`. It now binds the 46
schema IDs, 28 resources, 19 CLI result IDs, 31 CLI leaves, 39 curated
`sidscope` facade symbols, Adapter SDK 1.0/plugin API 1.0, and the named opt-in
local workflow functions. Runtime, conformance and evidence-full remain additive
profiles. N09, N10, hosted services, model training and upstream method semantics
are excluded.

`tools/verify_sidscope_2_0_candidate.py` fails closed if the frozen surface,
version, release profiles or SDLC state drifts. `engineering_ready` may be true
with F09/N01 pending because their remaining condition is deliberately human;
`certification_ready` remains false until the authority ledger records an actual
independent run. The verifier never changes that state itself.

## Consequences, migration and rollback

This creates no 2.0 compatibility promise yet. A future authorized RC changes
package versions only after F09 closes and the clean exact-source, Linux matrix,
archives and delivery packet are current. Public publication still requires a
separate explicit authorization.

Rollback pins the preceding local commit and its surface record. It never
rewrites evidence, public 1.1.x history, TOIS refs or adapter-native semantics.

## Implementation amendment, 2026-09-12

The candidate verifier accepts both the current development stage and a later,
separately authorized `2.0.0rcN` stage. It permits the certification blocker set
to transition from exactly F09 to empty only when the ledger records consistent,
traceable F09/N01 actual-use evidence. It still rejects unknown blockers,
inconsistent readiness, unapproved version shapes and RC state before
certification. This makes the documented positive transition executable; it
does not record user acceptance, authorize an RC version change, or release.

The detached exact-source record is v2 and embeds the current six-command CPU
measurement plus its source-snapshot binding. A raw environment-review status is
retained. Delivery may accept only a platform-version-only variance when every
frozen workload remains within the original threshold; workload, Python,
implementation, processor or over-threshold drift remains blocked. No baseline
is rewritten and this is not a production SLO.
