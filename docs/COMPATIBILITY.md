# SIDScope Compatibility Matrix

Status: Architecture Sprint 0 baseline

## Product and Entry Points

| Product line | Distribution | Python import | Product CLI | Status |
| --- | --- | --- | --- | --- |
| 1.0.2 | `sidinspector` | `sidinspector` | route-specific commands | Frozen TOIS-bound release |
| 1.1.0 | `sidinspector` | `sidinspector` | route-specific commands | Published maintenance release |
| 1.1.1.dev0 | `sidinspector` | `sidinspector` | `sidscope` facade plus legacy commands | Active development baseline |
| 1.2 planned | `sidinspector` | `sidinspector` | expanded `sidscope` facade | Canonical-contract milestone |

No import or distribution rename is planned during 1.x. The first implemented
facade command validates `SourceIdentity v1`; planned commands are not claimed
as available until their vertical slices pass.

## Version-Axis Baseline

| Axis | Current value | Compatibility rule |
| --- | --- | --- |
| Product/package | `1.1.1.dev0` | PEP 440 development version; not a public 1.1.1 release. |
| Adapter SDK | not released | No external SDK compatibility promise yet. |
| Canonical schema | `sidscope.source_identity.v1` revision `1.0.0` | Exact major and supported revision required. |
| Conformance profiles | legacy C0--C5 and G0--G5 authorities | Existing route verifiers remain authoritative until exact parity migration. |
| Evidence bundle | route-specific 1.1 schemas | Immutable; no automatic upgrade. |

## Schema Compatibility

- A schema ID suffix `vN` is the semantic major.
- `schema_revision` is semantic within that major.
- Compatible additive revisions require verifier-declared support.
- Removed fields, changed meaning, denominator changes, altered censoring, or
  new required semantics require a new major schema/profile.
- Unknown majors, unknown required dependencies, and unsupported revisions fail
  closed.
- Historical evidence is replayed by its original verifier or migrated into a
  new artifact with an explicit dependency; it is never rewritten in place.

## SourceIdentity v1 Migration

`sidscope.adapter_manifest.v1` remains a legacy authority. The shared converter
maps its source fields into `sidscope.source_identity.v1` and parity tests require
exact preservation of repository URL/revision, license marker/identifier,
redistribution policy, derivation, artifact name, source ID, and paper label.
The converter does not invent a paper URL, notices, or patches.

Rollback removes the shared dispatch and leaves the legacy manifest and report
unchanged.
