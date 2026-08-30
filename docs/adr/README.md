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

New ADRs must include context, decision drivers, viable options, the decision,
positive and negative consequences, migration, validation and rollback. Accepted
records may be marked superseded but not rewritten to make a later outcome look
inevitable.
