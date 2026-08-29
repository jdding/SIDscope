# DiffGRM Generator Adapter

## Scope and method identity

SIDScope stages DiffGRM as the representative masked/diffusion generator
family for the dormant-user generator screen. The method is a research-track
paper at The Web Conference 2026 (DOI `10.1145/3774904.3792156`) and is bound
to the official repository revision
`ad7b971c7e525e9fea6fb8e362a5c49dccb2473c`.

The official repository currently has no root `LICENSE`. SIDScope records that
state as `NOASSERTION` and retains a revision-bound, non-vendoring contract.
The license marker is independent of adapter development, downstream execution,
experiment verification, evidence delivery, and named promotion; it does not
block those surfaces. SIDScope still does not vendor or redistribute upstream
source, weights, data, or assets. The frozen VG configuration now passes
G0--G5 and is a configuration-bound named adapter.

## Versioned interfaces

- adapter: `sidscope.diffgrm_adapter.v1`
- prepared data: `sidscope.diffgrm_prepared_dataset.v1`
- episode selection: `sidscope.diffgrm_episode_selection.v1`
- masked trace fixture/legacy interface: `sidscope.diffgrm_masked_trace_bundle.v1`
- checkpoint-bound masked trace: `sidscope.diffgrm_masked_trace_bundle.v2`
- staged preflight: `sidscope.diffgrm_staged_preflight.v2`
- verifier output: `sidscope.diffgrm_adapter_verification.v1`
- real-bundle verifier output:
  `sidscope.diffgrm_trained_trace_bundle_verification.v1`
- processed-cache manifest: `sidscope.diffgrm_processed_cache_manifest.v1`
- recoverable training state: `genrec_dormant.diffgrm_recoverable_state.v1`

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
or reordering. The accepted VG run freezes a separate official DiffGRM OPQ4
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

Schema v2 adds a mandatory `evidence` object with the pinned source revision
and lowercase SHA-256 bindings for the source manifest, canonical
configuration, checkpoint, training manifest, and Semantic-ID cache. The
configuration contains the training/sampling seed, and
`evidence.configuration_sha256` must equal the canonical hash of that exact
configuration object. Optional evidence hashes such as command or run-log
hashes are accepted only when they are valid SHA-256 values. Schema v1 remains
accepted for the packaged deterministic contract fixture, but it is reported
as `legacy_v1_contract_fixture` and cannot claim checkpoint-bound closure.

## Current gates

| Gate | Current state |
| --- | --- |
| G0 | Publication and immutable source identity pass; license is a `NOASSERTION` marker and non-redistribution boundary, not an experiment gate. |
| G1 | Real frozen-VG OPQ4 item/SID/model-vocabulary round-trip and explicit five-bucket selections pass. |
| G2 | Real checkpoint-bound OCN/noising, adaptive masked-state transitions, beam ancestry, expansion, and pruning pass. |
| G3 | Real pre-filter validity, duplicate handling, collision-preserving resolution, and typed failure pass. |
| G4 | Five-episode smoke and external 250-episode ranked-item, exact-rank, and right-censoring exports pass. |
| G5 | Recoverable 10,000-step training, checkpoint smoke, typed negative, external diagnostic, compact evidence, and both verifiers pass. |

The compact authority is
`docs/reproducibility/diffgrm_www2026_trained_trace_evidence.json`. The full
five-episode and 250-episode bundles remain external and are bound by byte and
canonical hashes, counts, metrics, compute totals, and verifier output.

## Commands

The SIDScope verification commands are CPU-only and do not load upstream code:

```bash
python3 tools/preflight_diffgrm_adapter.py
python3 tools/verify_diffgrm_adapter.py
python3 tools/verify_diffgrm_trained_trace_bundle.py \
  --prepared <prepared_dataset.json> \
  --selection <episode_selection.json> \
  --bundle <trained_trace_bundle.json> \
  --result-json <verification.json>
python3 tools/materialize_diffgrm_protocol_train_surface.py --help
python3 tools/prepare_diffgrm_protocol.py --help
python3 tools/finalize_diffgrm_prepared_contract.py --help
python3 tools/run_diffgrm_runtime.py --help
python3 tools/run_diffgrm_resumable_training.py --help
python3 tools/export_diffgrm_masked_trace.py --help
python3 -m pytest -q \
  tests/test_diffgrm_adapter.py \
  tests/test_diffgrm_trained_trace_bundle.py \
  tests/test_diffgrm_dataset_bridge.py
```

The real-bundle CLI calls the same `validate_trace_bundle` contract directly
and deliberately does not run the source or license audit. Its result records
canonical prepared/selection/bundle hashes, byte hashes, episode and five-bucket
counts, trained bindings, overall and bucket metrics, exact/censored ranks,
raw validity/duplication/resolution counts, and compute totals. The existing
`unknown_parent_beam` fixture and real-CLI tests for
`prepared_binding_mismatch` and `configuration_binding_mismatch` preserve typed
fail-closed behavior.

## Migration and unlock sequence

Downstream consumers should generate the two manifest files first, then export
the trace bundle with their canonical hashes. No raw user IDs, source item IDs,
private paths, checkpoint bytes, embeddings, or source code enter the bundle.

The VG closure sequence completed as follows:

1. record source/revision identity and run CPU import/config/prepared
   compatibility preflight; keep license state as a separate marker;
2. freeze VG OPQ4 and a recoverable training manifest with atomic
   model/optimizer/scheduler/RNG/epoch/global-step/config/source hashes;
3. run a checkpoint-bound five-episode VG smoke, one episode per natural gap
   bucket, plus typed expected failure;
4. run the 250-episode balanced VG diagnostic, 50 episodes per bucket;
5. unlock Steam only after VG identity, trace, metrics, and verifier all pass.

VG now satisfies that unlock rule. Steam does not inherit VG evidence. Its
dataset-neutral train-only materialization, prepared contract, official OPQ4
round-trip, explicit 5/250 selections, and 8-update five-bucket checkpoint
smoke pass. Compact pre-training evidence is recorded in
`docs/reproducibility/diffgrm_steam_bridge_preflight_evidence.json`; formal
recoverable training and native trace verification remain configuration-local
gates.

No current RPG or other live run needs to be modified or interrupted.
