# SIDScope Architecture Decision Records

Accepted ADRs are immutable decision records. A later decision supersedes an
earlier ADR rather than editing its rationale or consequences in place.

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](0001-product-boundary.md) | Own conformance and observability, not upstream methods | Accepted | 2026-08-30 |
| [0002](0002-local-first-modular-platform.md) | Use a local-first modular platform with adapter plugins | Accepted | 2026-08-30 |
| [0003](0003-canonical-identity-versioning-hashing.md) | Canonical identity, version axes, and non-self-referential hashing | Accepted | 2026-08-30 |
| [0004](0004-module-boundaries-and-cli-identity.md) | Enforce module boundaries and add the `sidscope` CLI facade | Accepted | 2026-08-30 |
| [0005](0005-contract-registry-and-dataset-identity.md) | Make the contract registry authoritative and bound dataset identity explicitly | Accepted | 2026-08-30 |
| [0006](0006-sid-space-and-prepared-dataset-boundary.md) | Separate SID space identity from prepared dataset bindings | Accepted | 2026-08-30 |
| [0007](0007-canonical-execution-report-and-sdk-boundary.md) | Canonicalize execution evidence and reports without owning training | Accepted | 2026-08-30 |
| [0008](0008-plugin-and-native-trace-ecosystem.md) | Add lazy adapter plugins and registered native trace families | Accepted | 2026-08-30 |
| [0009](0009-content-addressed-evidence-and-derived-registry.md) | Make immutable evidence objects authoritative and SQLite derived | Accepted | 2026-08-30 |
| [0010](0010-separate-hardening-from-2-0-stability.md) | Separate 1.6 hardening from the 2.0 stability declaration | Accepted; partially supersedes ADR-0004 timing | 2026-08-30 |
| [0011](0011-profile-governed-submission-admission.md) | Govern evidence admission through versioned profiles and reports | Accepted | 2026-08-30 |
| [0012](0012-freeze-pre-2-0-candidate-surface.md) | Freeze the pre-2.0 candidate surface through executable inventories | Accepted | 2026-08-30 |
| [0013](0013-unify-public-contract-authority.md) | Unify public contract authority before stable 2.0 | Accepted | 2026-08-31 |
| [0014](0014-tiered-release-profiles.md) | Publish additive runtime, conformance, and evidence-full assets | Accepted | 2026-08-31 |
| [0015](0015-separate-public-maintenance-development-and-tois-lines.md) | Separate the public maintenance, local 2.0 development, and TOIS lines | Accepted | 2026-08-31 |
| [0016](0016-quarantine-unverified-admission.md) | Quarantine unverified admission instead of treating declarations as facts | Accepted | 2026-09-08 |
| [0017](0017-executable-sdlc-acceptance-and-consumer-workflows.md) | Make SDLC acceptance and public consumers executable | Accepted | 2026-09-08 |
| [0018](0018-separate-local-input-budgets-from-submission-policy.md) | Separate optional local budgets from untrusted submission limits | Accepted | 2026-09-08 |
| [0019](0019-local-producer-orchestration-and-mapping-preflight.md) | Add local producer orchestration and mapping preflight | Accepted | 2026-09-08 |
| [0020](0020-observed-native-canonical-admission.md) | Admit observed native exports through canonical diagnostic evidence | Accepted | 2026-09-08 |
| [0021](0021-paired-regression-and-offline-review.md) | Add paired regression and offline diagnostic review | Accepted | 2026-09-09 |
| [0022](0022-bounded-sid-refresh-lifecycle.md) | Add bounded SID refresh lifecycle diagnostics | Accepted | 2026-09-09 |
| [0023](0023-stabilize-adapter-sdk-1-0.md) | Stabilize the Adapter SDK at 1.0 | Accepted | 2026-09-09 |
| [0024](0024-freeze-2-0-engineering-candidate.md) | Freeze the 2.0 engineering candidate before certification | Accepted | 2026-09-09 |
| [0025](0025-remove-independent-user-acceptance-gate.md) | Remove independent-user acceptance from current gates | Accepted | 2026-09-27 |
| [0026](0026-delivery-summary-and-application-boundaries.md) | Bind delivery summaries and application boundaries | Accepted | 2026-09-27 |
| [0027](0027-defer-linux-support-beyond-2-0.md) | Defer Linux support beyond 2.0 | Accepted | 2026-10-08 |
| [0028](0028-publish-2-0-on-an-independent-branch.md) | Publish 2.0 independently of the 1.1.x review line | Accepted | 2026-10-08 |

New ADRs must include context, decision drivers, viable options, the decision,
positive and negative consequences, migration, validation and rollback. Accepted
records may be marked superseded but not rewritten to make a later outcome look
inevitable.
