# SIDScope Release Candidate Checklist

Status: v1.1.0 local release-candidate gates, public tag, and public URL smoke
pass
Last updated: 2026-08-28

This checklist defines what must be true before a SIDScope reviewer package is
called release-ready. Version 1.1.0 adds the G0--G5 generator-adapter protocol,
RPG/Latte/LLaDA-Rec/DACT/ISD contracts and evidence, and the first complete
configuration-bound named generator adapter for Latte/PSID. The public
`https://github.com/jdding/sidscope` repository remains the approved release
surface. Local verification must close before any tag or push; the final public
URL smoke is a separate post-publication gate.
Paper submission readiness remains a separate writing and venue-decision gate.

Current publication boundary: this checklist may verify local 1.2--2.0
development artifacts, but GitHub `main` remains the 1.1.x maintenance line.
Passing local gates does not authorize pushing `codex/sidscope-v2`. The TOIS
submission is governed by its exact frozen ref/package, not by an assumption
that every future revision must remain on `v1.0.2` or adopt 2.x.

## Current 2.0 candidate closeout

The local engineering candidate remains `1.7.0.dev0`. Adapter SDK 1.0 and the
compatibility surface are frozen; N02-N08 engineering scope is verified. Run:

```bash
python3 tools/verify_sidscope_2_0_candidate.py --require-engineering-ready
python3 tools/verify_sidscope_2_0_candidate.py --require-certification-ready
```

The engineering command passes. The certification command remains blocked until a
same-source delivery summary with valid receipts for every required gate verifies;
independent user actual use is excluded from current gates by ADR-0025 and the
adoption fact stays not verified. ADR-0027 defers Linux/Python 3.9–3.12 support
beyond 2.0. Catalog v2 requires macOS CPU gates, wheel/sdist consumers, all three
profile archives and smoke tests, G8, and an external exact-source record.
Delivery summary v2 records Linux as unsupported/deferred. Source or
documentation changes invalidate preceding records; the current
candidate must produce record v2 and the delivery summary, including the
source-bound performance disposition, after a clean commit. Do not change to `2.0.0rc1` before the delivery summary verifies;
a separately authorized RC commit must rerun the same gates. Push, tag and GitHub Release still require separate explicit approval.
See `docs/SIDSCOPE_2_0_RC_PACKET.md`.

## Release Candidate Inputs

- Historical G7-lite claim/package boundary:
  `experiments/v1_evidence_chain/G7_LITE_CLAIM_PACKAGE_BOUNDARY.md`
- Reviewer package manifest:
  `docs/reproducibility/sidscope_release_candidate_manifest.csv`
- Sampled regeneration manifest:
  `docs/reproducibility/sidscope_sampled_regeneration_manifest.csv`
- Reproducibility matrix:
  `docs/REPRODUCIBILITY_MATRIX.md` and `docs/reproducibility_matrix.csv`
- Resource docs:
  `docs/SIDSCOPE_RESOURCE_PACKAGE.md`, `docs/SIDSCOPE_DATASHEET.md`,
  `docs/SIDSCOPE_LIMITATIONS.md`, `docs/SIDSCOPE_MAINTENANCE.md`, and
  `docs/SIDSCOPE_CHANGELOG.md`
- Version and compatibility policies:
  `docs/VERSIONING.md` and `docs/COMPATIBILITY.md`
- GitHub Release body template:
  `docs/SIDSCOPE_RELEASE_TEMPLATE.md`
- Public release preparation packet:
  `docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md`

## Local Release-Candidate Gates

Run from the repository root:

```bash
python3 tools/verify_sidscope_resource_package.py
python3 tools/verify_sidscope_release_metadata.py
python3 tools/verify_sidscope_architecture_inventory.py
python3 tools/verify_sidscope_1_3_plugin_ecosystem.py
python3 tools/verify_sidscope_1_5_conformance_ecosystem.py
python3 tools/verify_sidscope_1_6_hardening.py
python3 tools/verify_sidscope_release_profiles.py
python3 tools/build_sidscope_release_candidate_archive.py --profile runtime --output /tmp/sidscope-runtime.zip
python3 tools/build_sidscope_release_candidate_archive.py --profile conformance --output /tmp/sidscope-conformance.zip
python3 tools/build_sidscope_release_candidate_archive.py --profile evidence-full --output /tmp/sidscope-evidence-full.zip
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-runtime.zip --profile runtime
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-conformance.zip --profile conformance
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-evidence-full.zip --profile evidence-full
python3 tools/run_sidscope_g8_fresh_env_smoke.py \
  --archive /tmp/sidscope-runtime.zip --profile runtime \
  --result-json /tmp/sidscope_g8_fresh_env_smoke.json
python3 -m pytest -q
```

These checks are CPU-only. They verify the local reviewer-package contract,
bounded sampled regeneration, matrix consistency, release-clean archive
construction, package-boundary rules, public-package content hygiene, and local
clean-extract install usability.

For a 1.6 or later pre-2.0 candidate, the hardening verifier additionally
requires all six compatibility axes, all fifteen legacy migration records,
external-plugin adoption, cross-family comparison, and the candidate API/
wrapper inventory to pass. The release body must link
`docs/MIGRATING_1_X_TO_2_0.md`; no development closure authorizes a tag, push,
or public release by itself.

Under the active repository policy, these pre-2.0 checks close local
development only. The public-release steps below are intentionally dormant for
`codex/sidscope-v2` until the user explicitly authorizes a public-line change.

## Public Release Gates

The following items must be refreshed for the clean `jdding/sidscope` public
surface whenever a new release tag or reviewer package is cut:

1. Create a release-clean branch or tag for the reviewed package boundary.
2. Publish a reviewer-accessible repository URL or archive URL.
3. Confirm the URL is accessible without private credentials.
4. Run G8 fresh-environment smoke from that URL or archive.
5. Record the exact tag, commit, archive checksum, and command transcript in
   the final claim ledger.
6. Add or update a changelog entry for the release tag.
7. Populate the GitHub Release body from `docs/SIDSCOPE_RELEASE_TEMPLATE.md`.
8. Update `docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md` with the final public URL,
   commit SHA, archive SHA256, and G8 command transcript.

## G8 Fresh-Environment Smoke Contract

The G8 smoke should use a clean checkout or extracted release archive. It
should not rely on local ignored artifacts, local AutoDL paths, or developer
shell state. `tools/run_sidscope_g8_fresh_env_smoke.py` provides the local
clean-extract version: it extracts the release archive into a temporary
directory, creates a temporary virtual environment, installs the package, and
runs the reviewer checks. R708 records the historical pre-split public URL/tag
smoke. The clean `jdding/sidscope` public surface must pass a fresh
unauthenticated public URL smoke after the current package surface is pushed
or otherwise hosted.

Minimum commands for the default runtime asset:

```bash
python3 -m pip install --upgrade "pip>=21.3"
python3 -m pip install -e .
python3 tools/verify_sidscope_runtime_release.py
```

Expected result: all commands pass on CPU, and the output JSON records
`status=pass`.

For the final public/reviewer URL gate, run:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/sidscope.git \
  --ref v1.1.0 \
  --result-json /tmp/sidscope_public_url_smoke.json
```

Rerun this if the tag, package manifest, or reviewer-facing release surface
changes.

## Release Blockers

- Any public-package manifest row points to a missing path.
- Package, SDK, schema, profile, bundle or CLI compatibility changes without
  the required migration note and version-axis update.
- Any tracked package file matches a forbidden private-artifact path or suffix.
- Any public-package file contains forbidden private-path, remote-address, or
  AI/tooling trace tokens outside explicit safety-token declarations.
- Any paper-facing claim lacks a package-relative artifact path, regeneration
  command, or snapshot/provenance boundary.
- The package requires GPU, private datasets, AutoDL access, or local absolute
  paths for the reviewer quickstart.
- The final paper describes R138 as faithful GRID coverage or describes
  unconstrained invalid/unresolved paths as constrained-decoding failures.

## Current Verdict

```text
PACKAGE_VERSION: 1.1.0
LATTE_PSID_NAMED_ADAPTER: PASS_G0_G5
LOCAL_TESTS: PASS_CURRENT
LOCAL_RESOURCE_PACKAGE_VERIFIER: PASS_CURRENT
LOCAL_ARCHIVE_BUILD: PASS_CURRENT
LOCAL_ARCHIVE_SMOKE: PASS_CURRENT
G8_LOCAL_CLEAN_EXTRACT_SMOKE: PASS_CURRENT with isolated sidinspector==1.1.0 install
DETERMINISTIC_ARCHIVE_REBUILD: PASS_CURRENT; SHA256=2b71bc8ad2128a2ce9d214b4fc13840e797e7c12bba6a7f063ff18d3abf2c65f
FINAL_RELEASE_TAG: v1.1.0 at a1a1226d0ee106cd98dac1cc2169dcd4fbb146a3
G8_PUBLIC_URL_FRESH_ENVIRONMENT_SMOKE: PASS_V1_1_0
TOIS_FROZEN_SUBMISSION: OUT_OF_SCOPE_UNCHANGED
```
