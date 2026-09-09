# SIDScope 2.0 RC preparation packet

Status: local engineering candidate; RC transition blocked only by F09.
Package: `1.7.0.dev0`. Adapter SDK: `1.0.0`. Plugin API: `1.0`.
Public release authorized: no.

## Candidate authority

- surface: `docs/reproducibility/sidscope_1_7_public_surface.json`;
- requirements: `docs/reproducibility/sidscope_sdlc_requirements.csv`;
- profiles: `docs/reproducibility/sidscope_release_profiles.v1.json`;
- package boundary: `docs/reproducibility/sidscope_release_candidate_manifest.csv`;
- decisions: ADR-0015 and ADR-0022 through ADR-0024.

## Required local evidence

- full CPU suite and metadata/architecture/SDLC/resource/profile verifiers;
- stable SDK interval, legacy replay, external plugin and installed consumer;
- N07 typed suite and actual-shape zero-change controls;
- N08 exact 100-episode transfer/validation and three-repeat metrics;
- Linux CPython 3.9, 3.10, 3.11 and 3.12 matrix;
- deterministic runtime, conformance and evidence-full archives plus smoke;
- regular wheel/sdist and G8 clean-environment installation;
- a clean local candidate commit and detached exact-source record.

## Current engineering execution

- Linux arm64 Docker / CPython 3.9, 3.10, 3.11 and 3.12: each cell passed
  544 tests, skipped 29 optional/external-input tests, and passed 65 subtests;
  metadata, architecture, SDLC, profile, candidate and resource gates passed.
- CI explicitly provisions the declared `setuptools>=68` backend and `wheel`;
  this is build tooling, not a runtime dependency.
- The immutable macOS 26.5.2 performance baseline is not rewritten. The 26.6.2
  rerun remains typed `environment_review_required`; review found all six advisory
  medians lower than baseline, without promoting it to a same-environment PASS.
- The final local commit must be clean and is followed by one detached exact-
  source record covering full tests, wheel/sdist installation, all archives,
  smoke tests and G8. Its commit and record hashes are reported after execution.

## Deliberately blocked transition

F09 requires an independent user to run the documented producer-to-diagnostic-
evidence workflow without core edits or hand-built internal JSON. Automation and
maintainer execution cannot satisfy it. Until that row is verified, the package
stays `1.7.0.dev0`, `--require-certification-ready` returns blocked, and no RC
version/tag is created.

After F09, update the ledger from the actual-use evidence, regenerate current
status blocks, set an authorized RC version, rerun every item above from that
clean commit, then populate public URL, commit, tag, archive hashes and smoke
transcript in a new public-release packet. Do not overwrite the historical
`SIDSCOPE_PUBLIC_RELEASE_PACKET.md` for v1.1.0. No public action is authorized by
this preparation packet.
