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

New ADRs must include context, decision drivers, viable options, the decision,
positive and negative consequences, migration, validation and rollback. Accepted
records may be marked superseded but not rewritten to make a later outcome look
inevitable.
