# ISD Decoder-Overlay Contract

## Audited boundary

The ISD paper, arXiv:2607.24995v1, links an anonymous official artifact at
`https://anonymous.4open.science/r/ISD-CF7C`. The artifact contains exact ISD
evaluation, registration, and test files, including SASRec and UniSRec provider
routes. SIDScope binds the relevant bytes by SHA-256 and runs four pure
functions from the external source in a CPU smoke.

The public artifact does not expose a Git commit or tag through its metadata
API, contains no root code license, and ships no data, checkpoints, SID cache,
trace output, or training log. Its root README is titled `Causal Representation
for Recommendation`, not ISD. The method files are therefore useful official
anonymous-snapshot evidence, but not a revision- and license-complete G0 source.
SIDScope does not vendor those files.

The complete evidence boundary is recorded in
`docs/reproducibility/isd_source_audit.json`.

## Overlay identity

ISD leaves the base semantic-ID generator intact. Before generation, an
external provider ranks the eligible item catalog once from target-free
observed history and retains a top-`J` shortlist `Q(h)`. For each candidate SID
prefix `p`, its item-support rank is the best rank of any shortlisted item whose
SID begins with `p`:

```text
r_item(p) = min rank_Q(i), for i in Q(h) whose SID begins with p
```

When no shortlisted item supports the prefix, `r_item(p)` is absent. Prefix
selection uses equal-weight reciprocal-rank fusion:

```text
F(p) = 1 / (kappa + r_native(p))
     + 1 / (kappa + r_item(p))  when supported
```

The audited route uses beam width 50, shortlist size 50, and `kappa = 60`.
At each semantic position it takes the union of the native top-`2B` pool and
reachable supported prefixes, then retains the best `B` fused candidates. The
collision suffix in the audited evaluator remains native-scored.

## Final item resolution

After generation, invalid SIDs and visited items are excluded. ISD reranks only
items resolved from the remaining complete generated SIDs:

```text
F_item(i) = 1 / (kappa + r_SID(i))
          + 1 / (kappa + rank_Q(i))  when i is in Q(h)
```

An item in the provider shortlist whose SID was not generated cannot enter the
final ranking. The fixture declares the final item set and fails with
`provider_only_item_insertion` if a provider-only item is added.

The audited evaluator uses a one-item `sid_to_item` map. SIDScope's independent
contract is stricter: a complete SID may resolve to zero, one, or multiple
catalog items. It exports `unresolved_semantic_id`, `unique_item`, or
`ambiguous_semantic_id` and never silently overwrites a collision.

## Stable trace schema

The schema is `sidscope.isd_decoder_overlay_trace.v1`. It retains:

- route, trace, split, target-universe, provider, and target-free context
  identity;
- the provider item ranking and best supporting item rank for every prefix;
- every base candidate's parent, prefix tokens, native cumulative score, dense
  native rank, RRF score, overlay rank, survival state, and pruning label;
- complete generated candidates with validity and collision-preserving item
  resolution;
- final item ranks, native SID ranks, provider ranks, RRF scores, and source
  item identities;
- explicit invariants that provider evidence is computed once, base scores and
  SIDs are preserved, and provider-only items are not inserted.

The overlay schema records an autoregressive base beam because the audited ISD
implementation wraps TIGER/LIGER. The overlay fields remain separate from the
base generator state so the same contract can be attached to another generator
without pretending ISD itself is a generator.

## Reproduction

Run the public deterministic fixture and verifier with:

```bash
PYTHONPATH=src python3 tools/verify_isd_adapter.py
```

Re-run the exact-function smoke after downloading the two audited files from
the official anonymous artifact:

```bash
python3 tools/run_isd_official_source_smoke.py \
  --unified-source <eval_sid_route_unified_tiger_liger_v1.py> \
  --provider-source <eval_sid_route_sasrec_isd_v1.py>
```

The runner requires the audited SHA-256 values, loads only `support_maps`,
`_native_top_indices`, `_select_owner`, and `final_rrf` by AST, and performs no
model or data access. The fixture and smoke are deterministic CPU checks, not
recommendation results.

## G0--G5 status and promotion boundary

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| G0 | Partial | Paper-linked, content-addressed anonymous source exists, but no immutable repository revision or coherent root method identity is available. `NOASSERTION` is a non-redistribution marker. |
| G1 | Bounded only | Deidentified source item to model-token SID to resolved-item round-trip passes; official-data identity remains absent. |
| G2 | Bounded pass | Base candidates, prefix support, native ranks, RRF scores, and survival are preserved; exact official pure-function smoke passes. |
| G3 | Bounded pass | Validity, collision ambiguity, support, pruning, resolution, and provider-only insertion failure are typed. |
| G4 | Bounded pass | Stable deidentified overlay trace and ranked-item export pass; no real official trace is released. |
| G5 | Partial | CPU fixture, expected failure, hashes, official pure-function smoke, and verifier pass; checkpoint/data-backed smoke is absent. |

ISD is now an active `close_named_adapter` route rather than source watch, but
it is not a named adapter. Promotion requires an immutable official revision,
fixed data/checkpoint/configuration assets,
an official-data item round-trip, and a real model-backed overlay trace.
