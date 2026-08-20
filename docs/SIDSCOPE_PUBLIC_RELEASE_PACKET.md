# SIDScope Public Release Packet

Status: v1.0.2 public-smoke patch verified on the public main branch; immutable
tag freeze pending
Last updated: 2026-08-20

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
repository_remote: git@github.com:jdding/sidscope.git
candidate_public_url: https://github.com/jdding/sidscope
candidate_release_ref: v1.0.2
candidate_archive_name: sidscope-v1.0.2.zip
local_archive_path: /tmp/sidscope-v1.0.2.zip
public_main_smoke_commit: 9c0893d32359195995ca5bffc9b6d805c04492a3
release_tag: v1.0.2
public_main_smoke_archive_sha256: f85b830ad8813ec258d158da813f72a06ec5081d9f8474aa00e28be8f98932d7
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
3. `python3 tools/build_sidscope_release_candidate_archive.py --output /tmp/sidscope-v1.0.2.zip` passes.
4. `python3 tools/smoke_sidscope_release_candidate_archive.py /tmp/sidscope-v1.0.2.zip` passes.
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
`/tmp/sidscope-v1.0.2.zip` and record the hosted URL plus SHA256
in the final claim ledger.

## G8 Fresh-Environment Verification

After the public URL or hosted archive exists, run from a clean directory:

```bash
python3 tools/run_sidscope_public_url_smoke.py \
  --repo-url https://github.com/jdding/sidscope.git \
  --ref v1.0.2 \
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
PUBLIC_REPOSITORY_ACCESS: PASS; page and git refs are available without authentication
SIDSCOPE_PUBLIC_URL_SMOKE: PASS_ON_PUBLIC_MAIN via R835
PUBLIC_URL_VERIFIED: PASS_FOR_ACCESS_AND_FRESH_ENVIRONMENT_EXECUTION
RELEASE_REF: v1.0.2_PENDING_SMOKE
HOSTED_ARCHIVE_VERIFIED: NOT_USED
G8_PUBLIC_URL_FRESH_ENVIRONMENT_SMOKE: PASS_ON_PUBLIC_MAIN at 9c0893d32359195995ca5bffc9b6d805c04492a3
```

`jdding/sidscope` is the clean SIDScope official repository and is accessible
without login. The immutable release tag remains the submission-facing ref.
Rerun public URL smoke after each public-surface change and before using the URL
in a submission or claim ledger.
