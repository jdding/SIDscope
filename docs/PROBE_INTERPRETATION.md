# Interpreting SIDScope Diagnostics

SIDScope reports an interface-health profile, not one accept/reject score.
Interpret each signal against an artifact with the same catalog and interaction
scope, then follow the indicated check before training or deploying a generator.

| Probe | Signal | Risk indicated | Next check |
|---|---|---|---|
| D1 utilization | Low active-code use, low entropy, or strong imbalance | Codebook collapse or unused capacity | Compare per-level histograms and item coverage; confirm the configured codebook budget. |
| D2 aliasing | Multiple items share a full SID or a prefix contains excessive mass | Ambiguous item addresses or concentrated prefix load | Inspect alias groups by popularity and co-occurrence; require full-code uniqueness when the decoder needs one address per item. |
| D3 neighborhood alignment | Co-occurring items rarely share the evaluated prefix | Prefix organization exposes weak behavioral neighborhoods | Compare a same-dataset deterministic control, then run the optional candidate-exposure probe. Do not use a cross-dataset absolute threshold. |
| D4 popularity allocation | Head, mid, or tail items receive sharply different unique-code capacity | Capacity is concentrated in one popularity stratum | Inspect bucket-level uniqueness and prefix mass; determine whether the allocation is intended by the tokenizer objective. |
| D5 structural pressure | Long codes, many active prefixes, or high fan-out | Larger trie and decoding search surface | Compare structural counts under a fixed catalog and code budget. Measure latency separately in the actual generator and serving stack. |
| D6 refresh churn | Common items change codes or prefix neighborhoods across refreshes | Cache invalidation, unstable addresses, or migration cost | Separate unavoidable new-item churn from changes to common items and record the mapping revision used downstream. |
| D7 trace accounting | Unresolved paths, duplicate items or paths, ambiguous resolution, stale items, or target loss inside the recorded beam | Decoder-output observability or accounting failure | First distinguish constrained from unconstrained decoding, then inspect generated path, resolved item, rank, score, target, and mapping revision. In trained constrained beams, compare target-code survival with unique target-item resolution. |

## Decision Discipline

- Use D1-D5 to decide which artifact property needs inspection, not to declare a
  universal best tokenizer.
- Treat D3 as a within-protocol interface proxy. Current evidence does not make
  it a validated predictor of trained-generator Recall or NDCG.
- Treat D5 as structural pressure, not a serving-latency model.
- Treat D7 as a trace schema and accounting layer. The bundled G20 trained
  case repeatedly observes ambiguous paths and path-versus-item differences;
  a failure-mechanism claim still requires a separate intervention design.
