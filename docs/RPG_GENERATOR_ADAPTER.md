# RPG Generator Adapter Contract

Status: bounded contract and official-source smoke available; not a complete
named-method adapter.

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
`ambiguous_item_nodes`. A trace must retain source item ID, normalized item ID,
raw semantic codes, model-vocabulary tokens, the canonical unordered token
set, and all resolved item IDs.

## G0--G5 Field Map

| Gate | RPG field mapping | Current state |
| --- | --- | --- |
| G0 | source URL, revision, paper DOI, code/paper licenses, configuration, training/checkpoint boundary, source-file hashes | Pass with CC BY-NC reuse restriction; no released checkpoint/cache |
| G1 | `source_item_id`, `normalized_item_id`, `semantic_codes`, `model_vocabulary_tokens`, `resolved_item_ids` | Bounded fixture round-trip passes; official dataset/cache round-trip pending |
| G2 | `decode_state_kind=unordered_token_set_graph_propagation`, parallel token log probabilities, explicit initial item nodes, propagation steps and frontiers | Bounded fixture passes without prefix semantics |
| G3 | `graph_valid`, `resolution_status`, `ambiguity_count`, collision groups and typed failure labels | Positive ambiguity case and expected invalid-token-set case pass |
| G4 | deidentified trace ID, split ID, target universe, per-step candidates, ranked items, sum/mean log-probability scores and visited item nodes | Stable bounded export passes |
| G5 | CPU fixture, expected failure, pinned-input hashes, verifier, and optional official-source model smoke | Partial: official source class smoke passes on deterministic untrained weights; trained checkpoint/data smoke remains open |

## Reproduction

Run the hermetic contract verifier:

```bash
PYTHONPATH=src python3 tools/verify_rpg_generator_adapter.py
```

To replay the source-class smoke after checking out the exact official
revision in a separate environment:

```bash
PYTHONPATH=src python3 tools/run_rpg_official_source_smoke.py \
  --rpg-source /path/to/RPG_KDD2025 \
  --output /tmp/rpg_official_source_smoke.json
```

The bundled smoke uses a four-item, three-codebook dummy catalog and fixed
random seed. It verifies that the official `RPG` class performs parallel
per-codebook scoring and graph-valid item-node export on CPU. It is not a
trained recommendation result and cannot promote the route to a named adapter.

## Promotion Blockers

- Obtain or derive a real official-data item mapping with immutable raw-input
  hashes and pass C0--C5.
- Run the adapter over a trained official checkpoint or a fully recorded
  official training output.
- Export real split-bound traces and ranked items, then rerun G1--G5 over those
  assets.
- Preserve the CC BY-NC boundary; do not redistribute official code, raw data,
  `.sem_ids`, or checkpoints through the SIDScope MIT package.
