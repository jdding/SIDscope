# SIDScope 2.0 RC preparation packet

Status: local engineering candidate; RC transition gated on same-source delivery evidence.
independent_user_actual_use excluded from current gates
(ADR-0025, 2026-09-27) and remains not verified. Package: `2.0.0`. Adapter SDK:
`1.0.0`. Plugin API: `1.0`. Owner authorization: ADR-0028, 2026-10-08.

## Candidate authority

- surface: `docs/reproducibility/sidscope_1_7_public_surface.json`;
- requirements: `docs/reproducibility/sidscope_sdlc_requirements.csv`;
- acceptance scope: `docs/reproducibility/sidscope_acceptance_scope.v1.json`;
- profiles: `docs/reproducibility/sidscope_release_profiles.v1.json`;
- package boundary: `docs/reproducibility/sidscope_release_candidate_manifest.csv`;
- decisions: ADR-0015, ADR-0022 through ADR-0027;
- required gates: `docs/reproducibility/sidscope_required_gate_catalog.v2.json`;
- platform backlog: `docs/SIDSCOPE_DEFERRED_PLATFORM_SUPPORT.md`.

## Required local evidence

- full CPU suite and metadata/architecture/SDLC/resource/profile verifiers;
- stable SDK interval, legacy replay, external plugin and installed consumer;
- N07 typed suite and actual-shape zero-change controls;
- N08 exact 100-episode transfer/validation and three-repeat metrics;
- macOS arm64 / CPython 3.9.6 acceptance; Linux support deferred beyond 2.0;
- deterministic runtime, conformance and evidence-full archives plus smoke;
- regular wheel/sdist and G8 clean-environment installation;
- a clean local candidate commit, detached exact-source record v2 (including
  its source-bound current performance measurement and delivery disposition),
  the three-group performance campaign, and the same-source delivery summary
  covering every required gate in the frozen catalog.

## Current engineering execution

- Linux CPython 3.9–3.12: unsupported in 2.0, deferred by the project owner
  on 2026-10-08 (ADR-0027). Historical matrix records remain intact. No new
  Linux execution, receipt or container recovery gates this RC transition.
  Current required evidence is the ten-gate catalog v2 under the documented
  macOS acceptance scope, recorded in delivery summary v2.
- CI explicitly provisions the declared `setuptools>=68` backend and `wheel`;
  this is build tooling, not a runtime dependency.
- The immutable macOS 26.5.2 performance baseline is not rewritten. A 26.6.2
  rerun was typed `environment_review_required`; the deterministic delivery
  policy accepts platform-version-only variance only when all six medians stay
  within the frozen threshold, without promoting it to a same-environment PASS.
  The environment-comparison defect fixed in this round requires a fresh
  measurement campaign bound to the final candidate.
- The final local commit must be clean and is followed by one detached exact-
  source record covering full tests, wheel/sdist installation, all archives,
  smoke tests and G8. Its commit and record hashes are reported after execution.

## Evidence-gated authorized transition

Independent user actual use is excluded from current gates by ADR-0025; the
adoption fact stays `not_verified` and no evidence file is required or invented.
What blocks the transition now is delivery evidence: `delivery_ready` requires a
same-source delivery summary with valid receipts for every required gate. Until
that summary exists and verifies against the clean candidate, the package stays
uncertified, `--require-certification-ready` returns blocked, and no public
version/tag is created for that candidate. Engineering receipts may be gathered
on RC/stable commits before the final summary without claiming certification.

The 1.7 baseline was certified before the authorized RC transition. Rerun every
item above from the new clean RC/stable commit and populate public URL, commit,
tag, archive hashes and smoke transcript in a new public-release packet. Do not
overwrite the historical `SIDSCOPE_PUBLIC_RELEASE_PACKET.md` for v1.1.0.
Public actions rely on explicit owner authorization in ADR-0028, not automated
PASS. Main, origin and frozen TOIS remain unchanged.
