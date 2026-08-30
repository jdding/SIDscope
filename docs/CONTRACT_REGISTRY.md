# SIDScope Contract Registry

Status: active in `1.2.0.dev0`

The bundled `sidscope.contract_registry.v1` document is the authority for
canonical contract discovery and dispatch. It records, for each public
contract type, the schema major and supported revisions, owner, JSON Schema
2020-12 resource, canonical fixture, typed negative fixtures, dependencies,
and result identity field.

```bash
sidscope contract list
sidscope contract show --type dataset-identity
sidscope contract validate \
  --type prepared-dataset \
  --input examples/prepared_dataset_fixture/prepared_dataset.json
python3 tools/verify_sidscope_contract_registry.py
python3 tools/verify_sidscope_sprint2_contracts.py
```

Registry order and paths are canonical. Unknown dependencies, dependency
cycles, unsupported revisions, duplicate schema IDs, missing resources,
schema-resource mismatches, and registry content-hash drift fail closed. The
registry is bundled with the installed package, while repository verification
also checks every declared fixture and schema file.

## DatasetIdentity Boundary

`sidscope.dataset_identity.v1` owns dataset name/category/profile, ordered
train/validation/test split identities, catalog identity, target-universe
identity, and pseudonymous item-identity policy. A `fully_bound` artifact must
bind all of those surfaces with counts and SHA-256 values.

Legacy `sidscope.adapter_manifest.v1` files do not contain those complete
bindings. Their migration therefore produces `legacy_partial`, enumerates the
unbound fields, and makes no split or universe-hash claim. The legacy
`sid_depth` value is returned as a deferred migration field for the future
`SIDSpaceIdentity`; it is deliberately not owned by DatasetIdentity.

Neither migration mode rewrites historical evidence. Legacy route verifiers
remain authoritative until their complete prepared-data surfaces are migrated
and parity-tested.

## SIDSpaceIdentity and PreparedDataset Boundaries

`sidscope.sid_space_identity.v1` owns SID tuple ordering, length/depth,
hierarchy, position vocabularies and offsets, special tokens, tokenizer/cache
identity, collision behavior and de-duplication. It does not own dataset splits
or decoder traces. Legacy adapter manifests become `legacy_partial`: known SID
depth and cache hash are retained while missing semantics remain enumerated.

`sidscope.prepared_dataset.v1` depends on fully bound DatasetIdentity and
SIDSpaceIdentity revisions. It binds pseudonymous normalized sequences,
ordered splits, interaction/mapping/SID-cache artifacts, catalog and target
universe. Source IDs and evaluator labels are forbidden. Training, checkpoint,
episode selection and model behavior belong to later contracts.

The RPG bridge is the first complete migration and retains its
parallel/unordered identity. Existing DiffGRM and LLaDA prepared v1 artifacts
do not contain all canonical counts and bindings; their typed outcome is
`legacy_prepared_regeneration_required`, not inferred compatibility.
