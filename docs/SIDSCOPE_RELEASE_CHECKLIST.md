# SIDScope Release Candidate Checklist

Status: v1.0.1 frozen on the private official repository and verified from an
authenticated clean clone; unauthenticated reviewer access remains pending
Last updated: 2026-08-19

This checklist defines what must be true before a SIDScope reviewer package is
called release-ready. The current resource package is release-ready for the
local resource-package layer: the local package verifier, release-clean archive
builder, and archive smoke pass after the ReSOT/DIGER and worktree-cleanup
refresh. The private `https://github.com/jdding/sidscope` repository is the
approved official release surface. Its obsolete G14 history has been replaced
by the current manifest-built root commit, tagged for TOIS preparation, and
verified from a clean authenticated clone. Public URL smoke remains pending
until reviewer visibility is enabled.
Paper submission readiness remains a separate writing and venue-decision gate.

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
- Public release preparation packet:
  `docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md`

## Local Release-Candidate Gates

Run from the repository root:

```bash
python3 tools/verify_sidscope_resource_package.py
python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1-release-candidate.zip
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1-release-candidate.zip
python3 tools/run_sidscope_g8_fresh_env_smoke.py --archive /tmp/sidscope-v1-release-candidate.zip
python3 -m pytest -q
```

These checks are CPU-only. They verify the local reviewer-package contract,
bounded sampled regeneration, matrix consistency, release-clean archive
construction, package-boundary rules, public-package content hygiene, and local
clean-extract install usability.

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
7. Update `docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md` with the final public URL,
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

Minimum commands:

```bash
python3 -m pip install --upgrade "pip>=21.3"
python3 -m pip install -e .
python3 tools/verify_sidscope_resource_package.py
python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1-release-candidate.zip
python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1-release-candidate.zip
python3 tools/run_sidscope_sampled_regeneration.py --output-dir /tmp/sidscope_sampled_regeneration
```

Expected result: all commands pass on CPU, and the output JSON records
`status=pass`.

For the final public/reviewer URL gate, run:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/sidscope.git \
  --ref main \
  --result-json /tmp/sidscope_public_url_smoke.json
```

Rerun this if the tag, package manifest, or reviewer-facing release surface
changes.

## Release Blockers

- Any public-package manifest row points to a missing path.
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
G5_G6_LOCAL_RELEASE_CANDIDATE: PASS_CURRENT after R768 verifier, R769 archive builder, and R770 archive smoke
G8_LOCAL_CLEAN_EXTRACT_SMOKE: PASS via R603 and current archive smoke via R770
SIDSCOPE_PRIVATE_CLEAN_CLONE_SMOKE: PASS for an authenticated v1.0.1 clone
SIDSCOPE_PUBLIC_URL_SMOKE: PENDING_UNTIL_REVIEWER_VISIBLE
PUBLIC_REVIEWER_ACCESS: PENDING; https://github.com/jdding/sidscope is currently private
G7_LITE_CLAIM_PACKAGE_BOUNDARY: PASS
G7_FULL_CLAIM_TABLE_FIGURE_LEDGER: PASS for current local artifact registry
G9_G10_UTILITY_ANCHORS: PASS for current local artifact registry
G8_PUBLIC_URL_FRESH_ENVIRONMENT_SMOKE: PENDING_AFTER_PUBLIC_PUSH_OR_HOSTED_ARCHIVE
PREPARATION_TAG: sidscope-tois-m1m5-20260809-r2
FINAL_RELEASE_TAG: v1.0.1
SUBMISSION_READY_RESOURCE_PACKAGE: PASS_FOR_LOCAL_RESOURCE_PACKAGE_LAYER_ONLY
PAPER_SUBMISSION_READY: NOT_ASSESSED
```
