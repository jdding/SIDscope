# Migrating SIDScope 1.x Evidence and Integrations to 2.0

Status: 1.6 candidate migration contract

## Who Must Act

- Core-only users keep the `sidinspector` import and move automation to the
  `sidscope` facade commands listed in the candidate API inventory.
- Adapter publishers use Adapter SDK `0.2.0-alpha`, a separately installed
  `sidscope.adapters` entry point, one registered native payload family, and a
  governed conformance profile.
- Evidence publishers package immutable EvidenceBundle v1 objects and derive
  registry/status/result views; they do not edit derived indexes.
- Historical-route maintainers either retain the bound legacy verifier or
  regenerate every missing canonical surface. They must not infer values from
  an incomplete 1.1 artifact.

## Migration Checklist

1. Record the source product/package, SDK, schema, profile, payload and bundle
   versions.
2. Run `python3 tools/verify_sidscope_1_6_hardening.py --gate compatibility`.
3. Locate the route in
   `docs/reproducibility/sidscope_1_6_legacy_migration_records.json`.
4. If `migration_state` is `canonical_replay_retained`, replay the canonical
   fixture and original verifier. If it is `immutable_historical_record`, keep
   the record read-only until the missing surfaces are regenerated.
5. Validate adapter capabilities and the method-native trace. Do not translate
   parallel, masked/diffusion, retry, or overlay behavior into invented AR
   ancestry.
6. Produce a governed profile report and independently validate the submission
   and EvidenceBundle.
7. Delete and rebuild disposable registry/index state and compare canonical
   bytes.
8. Check the candidate API inventory for ownership and lifecycle of every CLI,
   Python export, or compatibility wrapper used by the integration.
9. Run the archive and fresh-environment release rehearsal on supported Python
   versions before declaring migration complete.

## Compatibility and Deprecation Rules

The eleven canonical schema IDs, SDK, profiles, native payloads, and
EvidenceBundle are independent version axes. Matching a common TraceEnvelope
does not imply matching native payload semantics. A 1.x development version is
not a public release. Compatibility wrappers remain replay-supported through
2.x under their recorded owners; reconsidering them for 3.0 requires a new ADR
and migration window.

Unknown revisions, missing bindings, private paths/IDs, unsupported exact
ranks, profile drift, and provenance divergence fail closed. Corrections create
new immutable objects and explicit supersession edges.

## Rollback

Pin the last passing 1.x package, profile and CLI combination; quarantine only
new invalid objects; rebuild derived state from immutable bundles; and retain
the original route verifier. Never modify frozen TOIS software, released tags,
or historical evidence to make a migration appear complete.
