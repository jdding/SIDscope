# RPG Generator Adapter Contract

Status: G0--G5 pass for the pinned Beauty configuration; complete
configuration-bound named generator adapter.

For dataset-neutral prepared training, explicit episode selection, v2 trace
verification, and the compact downstream table, see
`docs/RPG_NON_AR_BRIDGE.md`. This 1.1.1 bridge preserves the Beauty schema-v1
bundle as a regression and does not broaden the configuration-bound Beauty
named-adapter claim to an unrun dataset.

## Source Boundary

The official implementation is
`https://github.com/facebookresearch/RPG_KDD2025` pinned at
`7dcf95ce9e08601810efdd1c850ed6dada5f97c2`. Its code is licensed
CC BY-NC 4.0. SIDScope does not vendor that code, its datasets, semantic-ID
caches, or model weights. The independently implemented adapter contract in
`src/sidinspector/adapters/rpg.py` remains under SIDScope's MIT license.

The paper is *Generating Long Semantic IDs in Parallel for Recommendation*,
KDD 2025, DOI `10.1145/3711896.3736979`. The detailed source, license,
configuration, hash, and asset audit is recorded in
`docs/reproducibility/rpg_kdd2025_source_audit.json`.

## Method-Preserving Identity

RPG assigns one code to each OPQ codebook and maps those values into disjoint
model-vocabulary ranges. SIDScope therefore serializes identity as an
unordered set containing exactly one vocabulary token from every codebook.
Sorting that set is only canonical serialization; it is never treated as a
left-to-right generation order or an autoregressive prefix.

Every decoding-graph node is an item, not a unique token set. If two items
share the same set, both item nodes remain visible and the resolution status is
`ambiguous_item_nodes`. The external identity audit binds source item ID to
normalized item ID, semantic codes, model-vocabulary tokens, and all resolved
item IDs. Public traces omit source identity and retain only normalized
identity, codes, tokens, and collision-aware resolution.

The generic C0--C5 static diagnostic report serializes codebook positions into
`sid_level_*` columns. Its reported `prefix_counts` describe only that stable
table serialization; they are not RPG decoding prefixes and are never used as
G2 parallel-generation evidence.

## G0--G5 Field Map

| Gate | RPG field mapping | Current state |
| --- | --- | --- |
| G0 | source URL, revision, paper DOI, code/paper licenses, configuration, training/checkpoint boundary, source-file hashes | Pass with CC BY-NC reuse restriction and a fully recorded local training boundary |
| G1 | `source_item_id`, `normalized_item_id`, `semantic_codes`, `model_vocabulary_tokens`, `resolved_item_ids` | Passes on all 12,101 Beauty items from a real official-code-derived cache; 2 token-set collisions covering 4 item nodes are retained |
| G2 | `decode_state_kind=unordered_token_set_graph_propagation`, parallel token log probabilities, explicit initial item nodes, propagation steps and frontiers | Real trained public and external traces pass without prefix semantics |
| G3 | `graph_valid`, `resolution_status`, collision groups and typed failure labels | Real trained item-node resolution plus positive and negative fixtures pass |
| G4 | deidentified trace ID, split ID, target universe, per-step candidates, ranked items, sum/mean log-probability scores and visited item nodes | Public 5-episode and external 250-episode exports pass |
| G5 | CPU fixture, expected failure, pinned-input hashes, fully recorded training, public smoke, external primary, and verifier | Pass; 127 epochs and 12,827 updates are hash-bound, with best epoch 107 and patience-20 early stopping |

## Reproduction

Run the hermetic contract verifier:

```bash
PYTHONPATH=src python3 tools/verify_rpg_generator_adapter.py
```

To build and normalize an external cache, use
`tools/build_rpg_opq_cache.py`,
`tools/generate_rpg_opq_from_embeddings.py`, and
`tools/normalize_rpg_opq_cache.py`. The public build/intake summaries and
C0--C5 report are under `docs/reproducibility/`; the raw Amazon files,
metadata text, embeddings, generated cache, and normalized parquet tables are
not redistributed.

To replay the source-class smoke after checking out the exact official
revision in a separate environment:

```bash
PYTHONPATH=src python3 tools/run_rpg_official_source_smoke.py \
  --rpg-source /path/to/RPG_KDD2025 \
  --output /tmp/rpg_official_source_smoke.json
```

The bundled smoke uses a four-item, three-codebook dummy catalog and fixed
random seed. It verifies that the official `RPG` class performs parallel
per-codebook scoring and graph-valid item-node export on CPU.

The real trained smoke is verified with:

```bash
python3 tools/verify_rpg_trained_trace_bundle.py \
  examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json
```

The public bundle contains five episodes and only 43 target-universe rows
needed for their collision resolution. It shares a complete 12,101-row target
universe hash with an external 250-episode bundle. Training, checkpoint,
runner, exporter, verifier, input, public bundle, external bundle, and target
universe hashes are recorded in
`docs/reproducibility/rpg_kdd2025_trained_trace_evidence.json`.

## Maintenance Boundary

- Preserve the CC BY-NC boundary; do not redistribute official code, raw data,
  `.sem_ids`, or checkpoints through the SIDScope MIT package.
- Keep the complete target universe and 250-episode trace external; publish
  only their hashes, counts, verifier result, and the bounded smoke.
- Rerun training closure only when the pinned source, data hash, cache hash, or
  Beauty configuration changes.
