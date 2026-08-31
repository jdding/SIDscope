# SIDScope 1.7 Contract and Public-Surface Stabilization

Status: implementation complete on `1.7.0.dev0`; release gates pending; no tag
or public release implied

## Scope

Version 1.7 activates one bounded workstream identified by the architecture
review: make the pre-2.0 contract and integration surface discoverable,
two-stage validated, deliberately small, and mechanically enforced. It adds no
method implementation, training runtime, hosted service, mutable authority or
new scientific evidence.

The mandatory order is Draft 2020-12 structural validation followed by the
owning Python semantic validator.

## Public Authority

| Surface | Authority | Rule |
| --- | --- | --- |
| Public schema IDs | `sidinspector.schemas.catalog` | Every bundled `*.schema.json` ID has one resource, owner and semantic validator. |
| Structural validation | Draft 2020-12 bundled resource | Runs first and fails with `structural_schema_violation`. |
| Semantic validation | Owning public module validator | Runs second and preserves domain-specific typed failures. |
| CLI JSON | CLI envelope validator or the emitted domain-artifact validator | CLI envelopes require pass/fail consistency; domain artifacts retain their own status semantics. |
| Python integration | `sidscope` | Curated new-integration facade; `sidinspector` remains historical compatibility. |
| Producer identity | `contracts/producer_versions.py` | Advances only when artifact semantics change, not for package-only releases. |

The deterministic inventory is
`docs/reproducibility/sidscope_1_7_public_surface.json`. It currently binds 45
schema IDs, 27 schema resources, 19 CLI result IDs, 31 CLI leaf commands and 39
curated Python symbols.

## Commands

```bash
sidscope schema list
sidscope schema validate \
  --input examples/dataset_identity_fixture/dataset_identity.json
python3 tools/verify_sidscope_1_7_stabilization.py
```

## Compatibility and Rollback

The delta is additive. Existing schema IDs/revisions, producer versions,
artifact hashes, CLI leaves, `sidinspector` imports and 1.6 historical evidence
remain valid. Rollback pins the 1.6 surface and removes only additive 1.7 code;
it never rewrites a bundle, release tag, adapter status or frozen TOIS asset.

## Exit Gates

- focused positive and typed-negative schema/CLI/architecture tests;
- historical 1.6 hardening replay;
- complete test suite;
- resource-package verifier;
- deterministic archive smoke;
- G8 fresh-environment install and CLI/schema smoke.
