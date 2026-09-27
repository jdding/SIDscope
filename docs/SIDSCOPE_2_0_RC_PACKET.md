# SIDScope 2.0 RC preparation packet

Status: local engineering candidate; RC transition gated on same-source delivery evidence.
independent_user_actual_use excluded from current gates
(ADR-0025, 2026-09-27) and remains not verified. Package: `1.7.0.dev0`. Adapter SDK:
`1.0.0`. Plugin API: `1.0`. Public release authorized: no.

## Candidate authority

- surface: `docs/reproducibility/sidscope_1_7_public_surface.json`;
- requirements: `docs/reproducibility/sidscope_sdlc_requirements.csv`;
- acceptance scope: `docs/reproducibility/sidscope_acceptance_scope.v1.json`;
- profiles: `docs/reproducibility/sidscope_release_profiles.v1.json`;
- package boundary: `docs/reproducibility/sidscope_release_candidate_manifest.csv`;
- decisions: ADR-0015, ADR-0022 through ADR-0025.

## Required local evidence

- full CPU suite and metadata/architecture/SDLC/resource/profile verifiers;
- stable SDK interval, legacy replay, external plugin and installed consumer;
- N07 typed suite and actual-shape zero-change controls;
- N08 exact 100-episode transfer/validation and three-repeat metrics;
- Linux CPython 3.9, 3.10, 3.11 and 3.12 matrix;
- deterministic runtime, conformance and evidence-full archives plus smoke;
- regular wheel/sdist and G8 clean-environment installation;
- a clean local candidate commit, detached exact-source record v2 (including
  its source-bound current performance measurement and delivery disposition),
  and the same-source delivery summary covering every required gate.

## Current engineering execution

- Linux arm64 Docker / CPython 3.9, 3.10, 3.11 and 3.12: the recorded four-
  version full run belongs to the preceding candidate commit, not the current
  HEAD; a new same-source matrix run is required for delivery evidence. That
  historical record passed 544 tests, skipped 29 optional/external-input tests,
  and passed 65 subtests per cell with metadata, architecture, SDLC, profile,
  candidate and resource gates green.
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

## Deliberately blocked transition

Independent user actual use is excluded from current gates by ADR-0025; the
adoption fact stays `not_verified` and no evidence file is required or invented.
What blocks the transition now is delivery evidence: `delivery_ready` requires a
same-source delivery summary with valid receipts for every required gate. Until
that summary exists and verifies against the clean candidate, the package stays
`1.7.0.dev0`, `--require-certification-ready` returns blocked, and no RC
version/tag is created.

Once the delivery summary verifies, an authorized change may set the RC version,
rerun every item above from that clean commit, and populate public URL, commit,
tag, archive hashes and smoke transcript in a new public-release packet. Do not
overwrite the historical `SIDSCOPE_PUBLIC_RELEASE_PACKET.md` for v1.1.0.
No public action is authorized by this preparation packet.
