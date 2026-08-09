# SIDScope Public Release Packet

Status: private official-repository preparation package verified;
unauthenticated public access remains a submission-time gate
Last updated: 2026-08-09

This packet records the exact public/reviewer release surface for the SIDScope
resource package. It is intentionally explicit about the local checks, public
tag, archive checksum, and public URL smoke that must be refreshed whenever the
reviewer-facing package changes.
The public GitHub repository is a reviewer-visible and post-acceptance open
source release surface, not the full private project workspace; local paper
drafts, AutoDL payloads, large caches, and planning records stay out of it.

## Candidate Release Identity

```text
project_name: SIDScope
paper_title: SIDScope: Artifact-Level Diagnostics for Semantic-ID Generative Recommendation
repository_remote: git@github.com:jdding/SIDscope.git
candidate_public_url: https://github.com/jdding/SIDscope
candidate_release_ref: main
candidate_archive_name: sidscope-v1-release-candidate.zip
local_archive_path: /tmp/sidscope-v1-release-candidate.zip
preparation_commit: recorded package-externally in R814 after the package commit is frozen
preparation_tag: sidscope-tois-m1m5-20260809-r2
archive_sha256: recorded package-externally in R814 to avoid recursive self-hashing
```

The GitHub URL is the reviewer-facing release surface. It must be checked after
each release commit/tag is pushed.

## Local Evidence Already Built

- `tools/verify_sidscope_resource_package.py` verifies the manifest-approved
  package boundary, compact evidence, quickstart, and forbidden-content rules.
- `tools/build_sidscope_release_candidate_archive.py` builds the clean archive;
  `tools/smoke_sidscope_release_candidate_archive.py` verifies it without
  relying on Git metadata.
- `tools/run_sidscope_g8_fresh_env_smoke.py` verifies installation and the
  reviewer workflow in a clean environment.
- `docs/reproducibility/sidscope_g7_full_table_figure_ledger.csv` binds claims
  and manuscript floats to compact source rows.
- `tools/run_sidscope_public_url_smoke.py` is the final gate after the private
  official repository becomes accessible without login.

## Release Preconditions

Before creating a public release:

1. Canonical G9 final claim-to-artifact ledger is updated with package-relative
   table paths, row counts, source-row bindings, claim placement, and
   snapshot/provenance boundaries.
2. `python3 tools/verify_sidscope_resource_package.py` passes.
3. `python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1-release-candidate.zip` passes.
4. `python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1-release-candidate.zip` passes.
5. `pytest` passes.
6. The release commit contains no private datasets, AutoDL payloads, checkpoints,
   local caches, `.aris`, `.codex`, `.agents`, `.codegraph`, or `.git` package
   metadata.

## Public Release Commands

These commands are intentionally not run by the local package verifier:

```bash
git status --short --branch
git commit -m "Prepare SIDScope V1 reviewer package"
git push official HEAD:main
```

If a GitHub release or external archive is used, upload
`/tmp/sidscope-v1-release-candidate.zip` and record the hosted URL plus SHA256
in the final claim ledger.

## G8 Fresh-Environment Verification

After the public URL or hosted archive exists, run from a clean directory:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/SIDscope.git \
  --ref main \
  --result-json /tmp/sidscope_public_url_smoke.json
```

Record:

- clone URL and tag;
- commit SHA;
- archive URL if used;
- archive SHA256;
- command transcript;
- pass/fail verdict;
- any environment differences.

## Current Verdict

```text
LOCAL_RELEASE_CANDIDATE: PASS_CURRENT
G8_LOCAL_CLEAN_EXTRACT_SMOKE: PASS_CURRENT
AUTHENTICATED_PRIVATE_REMOTE: PASS; exact commit recorded package-externally in R814
SIDSCOPE_PUBLIC_URL_SMOKE: PENDING_UNTIL_REVIEWER_VISIBLE
PUBLIC_URL_VERIFIED: PENDING; private repository is not an unauthenticated reviewer surface
RELEASE_REF: main; preparation tag sidscope-tois-m1m5-20260809-r2
HOSTED_ARCHIVE_VERIFIED: NOT_USED
G8_PUBLIC_URL_FRESH_ENVIRONMENT_SMOKE: PENDING_AFTER_PUBLIC_PUSH_OR_HOSTED_ARCHIVE
```

`jdding/SIDscope` is the clean SIDScope official repository, but the final
reviewer URL must be accessible without login.
Rerun public URL smoke after each public-surface change and before using the URL
in a submission or claim ledger.
