# RPG trained parallel-decoding smoke

This directory contains a five-episode, deidentified trace exported from a
fully recorded Beauty training run of the pinned RPG architecture. The trace
preserves RPG's parallel 32-codebook prediction and unordered graph-propagation
state; it does not introduce autoregressive prefix semantics.

Run the fail-closed verifier with:

```bash
python3 tools/verify_rpg_trained_trace_bundle.py \
  examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json
```

The public smoke contains only the 43 normalized-item/SID rows required to
verify ranked-item and collision resolution for these episodes. The complete
12,101-row target universe and 250-episode trace remain external and are bound
by hashes and counts in
`docs/reproducibility/rpg_kdd2025_trained_trace_evidence.json`. No upstream
source, raw review or metadata row, embedding, checkpoint, `.sem_ids` cache,
source item identity, or user identity is redistributed.
