# SIDScope 1.7 Release Profiles

SIDScope 1.7 publishes one product version through three additive release
profiles. Profiles are packaging views, not product versions, schema versions,
or support branches.

| Profile | Audience | Contents | Default |
|---|---|---|---|
| `runtime` | Users installing and invoking SIDScope | Python packages, bundled public schemas, package metadata, essential compatibility/security documentation, and the runtime verifier | Yes |
| `conformance` | Adapter authors and reviewers | Everything in `runtime`, plus source tools, tests, documentation, reference plugin, and compact positive/negative fixtures | No |
| `evidence-full` | Release auditors and reproducibility reviewers | Everything admitted by the public release manifest, including hash-bound evidence, paper tables, compact labeled data, and trained real-smoke traces | No |

The profiles are strict additive subsets:

```text
runtime < conformance < evidence-full
```

The default profile deliberately excludes tests, examples, tracked evidence,
and trained traces. The conformance profile excludes the three large real-smoke
trace documents and `docs/reproducibility`. The full evidence profile preserves
the previous 1.7 reviewer-package surface unchanged, apart from a generated
profile receipt.

## Build and verify

```bash
python3 tools/build_sidscope_release_candidate_archive.py \
  --profile runtime \
  --output /tmp/sidscope-v1.7.0.dev0-runtime.zip
python3 tools/build_sidscope_release_candidate_archive.py \
  --profile conformance \
  --output /tmp/sidscope-v1.7.0.dev0-conformance.zip
python3 tools/build_sidscope_release_candidate_archive.py \
  --profile evidence-full \
  --output /tmp/sidscope-v1.7.0.dev0-evidence-full.zip

python3 tools/smoke_sidscope_release_candidate_archive.py \
  /tmp/sidscope-v1.7.0.dev0-runtime.zip --profile runtime
python3 tools/run_sidscope_g8_fresh_env_smoke.py \
  --archive /tmp/sidscope-v1.7.0.dev0-runtime.zip --profile runtime
python3 tools/verify_sidscope_release_profiles.py
```

Every archive contains a deterministic `sidscope-release-profile.json`
receipt. It binds the product version, profile ID, profile-registry SHA-256,
source-manifest SHA-256, content-file count, and canonical content-path-set
SHA-256. Smoke and G8 reject a missing, mismatched, or tampered receipt.

## Release policy

- GitHub/PyPI users should be directed to the wheel or `runtime` asset.
- This guidance becomes public only after an explicitly authorized release;
  current 1.7/pre-2.0 profile builds remain local while GitHub stays on 1.1.x.
- Adapter developers may download `conformance` without the full trained
  evidence surface.
- `evidence-full` remains a separately named, immutable Release asset.
- The three large RPG/Latte/PSID traces remain tracked and auditable; they are
  not copied into the default runtime or conformance assets.
- A profile change is a release-surface change inside 1.7, not a reason to
  activate 1.8.

Rollback is additive: retain or rebuild `evidence-full`, remove the optional
smaller assets, and restore the prior explicit full-profile release command.
No contract, evidence, or source file needs to be deleted.
