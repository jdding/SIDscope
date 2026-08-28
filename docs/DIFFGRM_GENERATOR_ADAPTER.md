# DiffGRM Generator Adapter

## Scope and method identity

SIDScope stages DiffGRM as the representative masked/diffusion generator
family for the dormant-user generator screen. The method is a research-track
paper at The Web Conference 2026 (DOI `10.1145/3774904.3792156`) and is bound
to the official repository revision
`ad7b971c7e525e9fea6fb8e362a5c49dccb2473c`.

The official repository currently has no root `LICENSE`. SIDScope therefore
uses a revision-bound, non-vendoring contract and does not import, execute, or
redistribute upstream code before explicit author permission is recorded and
audited. Publication identity and source identity pass; G0 permission remains
open. The route is not a named adapter yet.

## Versioned interfaces

- adapter: `sidscope.diffgrm_adapter.v1`
- prepared data: `sidscope.diffgrm_prepared_dataset.v1`
- episode selection: `sidscope.diffgrm_episode_selection.v1`
- masked trace: `sidscope.diffgrm_masked_trace_bundle.v1`
- staged preflight: `sidscope.diffgrm_staged_preflight.v1`
- verifier output: `sidscope.diffgrm_adapter_verification.v1`

The prepared contract binds dataset, category, profile, train/validation/test
hashes, a dense train-only catalog, target universe, pseudonymous normalized
item identities, semantic codes, model tokens, and tokenizer configuration.
Episode selection is explicit and ordered. First-N fallback is forbidden;
duplicate, missing, out-of-split, mismatched, or catalog-unreachable episodes
must fail closed in a real converter.

Gap bucket and target label are evaluator-side fields. They are never model
inputs.

## SID identity and compatibility

The pinned DiffGRM identity is four code positions, 256 entries per position,
with `PAD=0`, `BOS=1`, `EOS=2`, inference `MASK=-1`, and `SID_OFFSET=3`.
For code `c` at position `p`, the model-facing token is
`c + 3 + p * 256`. The formal tokenizer route is
`OPQ4,IVF1,PQ4x8` over the train-observed catalog.

The existing frozen RPG VG cache uses 32 positions and is therefore
incompatible. SIDScope rejects it rather than cropping, padding, offsetting,
or reordering. The future VG run must freeze a separate official DiffGRM OPQ4
cache over the same frozen train-only catalog. This preserves the data and
target universe but makes tokenizer identity a declared second factor; the
comparison is not described as a pure generator-only intervention.

## Native masked trace

DiffGRM is not represented as an autoregressive prefix trace. Each episode
records:

- forward OCN noising views, mask positions, mask weights, and timesteps;
- the all-mask reverse state and each adaptive denoising step;
- per-parent, per-position token top-k log probabilities and confidence;
- selected unmask position and code, pre/post states, cumulative score;
- genuine parent ancestry, expanded candidates, retained/pruned beams, NFE,
  forward calls, logits, visited states, and latency;
- the complete raw final frontier before legality filtering, de-duplication,
  and short-list padding;
- exact catalog resolution with every collision retained, invalid and duplicate
  candidates, dense ranked items and scores, target state, and typed failure.

The official route performs exact SID lookup rather than nearest-token
projection. Invalid raw tuples remain unresolved and cannot become raw
generation successes. `projection_state` is therefore
`projection_not_applicable`.

Evaluation remains Hit@10 and NDCG@10. In a single-target protocol,
Recall@10 is labeled only as a Hit@10 alias. A deeper published rank is valid
only when the captured native frontier supports it; otherwise target rank is
typed `right_censored_beyond_published_depth`.

## Current gates

| Gate | Current state |
| --- | --- |
| G0 | Publication and immutable source identity pass; explicit code permission pending. |
| G1 | Dataset-neutral prepared/selection fixture passes; real frozen VG OPQ4 round-trip pending. |
| G2 | Native OCN/noising and adaptive masked-state trace fixture passes; trained trace pending. |
| G3 | Raw validity, collision resolution, duplicate policy, and typed failures pass on CPU fixture. |
| G4 | Ranked-item and right-censoring contract passes; checkpoint-bound export pending. |
| G5 | Non-executing staged preflight and verifier pass; upstream runtime/GPU work is prohibited until G0 closes. |

## Commands

The current allowed commands are CPU-only and do not load upstream code:

```bash
python3 tools/preflight_diffgrm_adapter.py
python3 tools/verify_diffgrm_adapter.py
python3 -m pytest -q tests/test_diffgrm_adapter.py
```

`--source` on the staged preflight performs only Git revision, file-hash, and
root-license inspection. `--require-execution-ready` exits nonzero while G0 is
open.

## Migration and unlock sequence

Downstream consumers should generate the two manifest files first, then export
the trace bundle with their canonical hashes. No raw user IDs, source item IDs,
private paths, checkpoint bytes, embeddings, or source code enter the bundle.

After explicit code permission is recorded, the sequence is:

1. re-audit G0 and run CPU import/config/prepared compatibility preflight;
2. freeze VG OPQ4 and a recoverable training manifest with atomic
   model/optimizer/scheduler/RNG/epoch/global-step/config/source hashes;
3. run a checkpoint-bound five-episode VG smoke, one episode per natural gap
   bucket, plus typed expected failure;
4. run the 250-episode balanced VG diagnostic, 50 episodes per bucket;
5. unlock Steam only after VG identity, trace, metrics, and verifier all pass.

No current RPG or other live run needs to be modified or interrupted.
