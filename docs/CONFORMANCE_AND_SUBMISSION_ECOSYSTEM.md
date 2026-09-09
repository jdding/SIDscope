# Conformance and Submission Ecosystem

Status: SIDScope `1.5.0.dev0` development contract

Current 1.7 override: ADR-0016 requires recomputation for diagnostic admission and
default indexes; missing inputs remain rejected. The flow and acceptance
examples below describe historical structural replay only. A caller-written
pass row, receipt or self-hash does not verify gate execution. Profile CLI
output explicitly distinguishes the declared label from structure-only checks.

SIDScope 1.5 connects four independently versioned surfaces:

```text
DatasetProfileDescriptor
          |
          v
versioned profile catalog -> ProfileConformanceReport
                                      |
                                      v
EvidenceSubmission -> checker -> accepted EvidenceBundle
                                      |
                                      v
                   deterministic status/result indexes
```

The profile report decides conformance and the allowed public status label. The
EvidenceBundle remains the immutable evidence authority. A submission is a
portable admission package, and the indexes are disposable views. None of
these artifacts executes or replaces an upstream method.

## Public Contracts

| Contract | Schema | Purpose |
| --- | --- | --- |
| Profile catalog | `sidscope.conformance_profile_catalog.v1` | Owner, semantic revision, ordered gates, fixtures, lifecycle and status policy |
| Dataset profile | `sidscope.dataset_profile_descriptor.v1` | Split, catalog, target universe, cutoff, depth, slices and privacy boundary |
| Profile report | `sidscope.profile_conformance_report.v1` | Hash-bound gate outcomes and profile-derived status label |
| Submission | `sidscope.evidence_submission.v1` | Root-relative member paths, exact hashes and bounded claims |
| Check report | `sidscope.submission_check_report.v1` | Deterministic accepted/rejected result with typed failures |
| Status index | `sidscope.adapter_status_index.v1` | Active labels derived only from profile reports |
| Result index | `sidscope.adapter_result_index.v1` | Result cards copied from active immutable bundles |

Canonical JSON content hashes exclude only the top-level `content_sha256`.
Exact file hashes in a submission cover the full canonical JSON bytes including
the trailing newline.

## Governed Profiles

- `static_mapping_c0_c5@1.0.0`: static mapping and tokenizer artifact routes;
- `generator_g0_g5@1.0.0`: standalone generator routes;
- `overlay_g0_g5@1.0.0`: decoder overlays that do not insert provider-only items;
- `release_local@1.0.0`: local tests, resource package, archive and fresh-install
  readiness.

The older 1.3 family-composition registry remains supported for native trace
semantics. The 1.5 catalog governs evidence admission and status labels; it does
not silently reinterpret old family profiles.

## CLI Workflow

List governed profiles:

```bash
sidscope profile catalog
```

Validate one descriptor/report pair:

```bash
sidscope profile verify \
  --descriptor package/dataset_profile_descriptor.json \
  --report package/profile_conformance_report.json
```

Check an untrusted package without executing it:

```bash
sidscope submission check --root package --manifest submission.json
```

Generate deterministic views from one or more accepted roots:

```bash
sidscope submission indexes \
  --root package-a \
  --root package-b \
  --status-output generated/status-index.json \
  --result-output generated/result-index.json
```

The command exits with code `2` for a typed rejection. Generated indexes contain
no local paths or timestamps and can be deleted and rebuilt from accepted
submissions.

## Fail-Closed Checks

The checker validates root containment, member hashes, required and unique
roles, canonical JSON, descriptor/report/profile bindings, bundle compatibility,
cutoff/depth/rank semantics, required slices, embedded objects and privacy. It
rejects unsupported exact ranks, failing conformance, missing evidence
objects, checkpoint payloads and forbidden content.

`examples/conformance_ecosystem_fixture` contains the positive external-adapter
submission and a registered negative-package inventory. The 1.5 verifier must
prove every registered negative returns its declared typed failure.

## Legacy Coexistence

Legacy adapter ledgers remain read-only authorities for routes not yet migrated.
The parity API compares only adapter IDs and status labels and cannot feed data
back into generated indexes. Every 1.5-native index row is report-derived;
complete replay or immutable archival of all 1.1.1 routes is the 1.6 hardening
gate.

## Recovery

If a profile or checker revision is faulty, stop new admissions under it and
pin the prior passing revision. Preserve the rejected package and typed report,
delete and rebuild derived views, and fix the issue using a new artifact hash or
profile revision. Never rewrite an existing report, bundle or released tag.
