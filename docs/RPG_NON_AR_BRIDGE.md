# RPG dataset-neutral non-autoregressive bridge

SIDScope 1.1.1 exposes a prepared-data bridge for applying the pinned RPG
architecture to a downstream frozen protocol without changing RPG into an
autoregressive generator. The existing Amazon Reviews 2014 Beauty bundle
remains schema v1 and is still the configuration-bound G0--G5 named-adapter
regression. The generic bridge uses these new schemas:

- `sidscope.rpg_prepared_dataset.v1`;
- `sidscope.rpg_episode_selection.v1`;
- `sidscope.rpg_trained_trace_bundle.v2`;
- `sidscope.rpg_downstream_handoff.v1`.

## Why a loader bridge is required

At official RPG revision `7dcf95ce9e08601810efdd1c850ed6dada5f97c2`,
`genrec.pipeline.Pipeline` appears to accept an `AbstractDataset` instance, but
then evaluates `get_dataset(dataset_name)(config)`. `get_dataset` returns an
instance unchanged, so the pipeline attempts to call that instance. The
upstream dataset registry contains only `AmazonReviews2014`, whose constructor
also fixes the cache layout to `AmazonReviews2014/<category>`, downloads SNAP
reviews/metadata, restricts categories to its static Amazon list, and builds a
leave-one-out split.

Changing only `dataset_name`, `category`, or the Beauty cardinality therefore
does not create a valid VG/Steam interface. SIDScope's prepared runtime bypasses
that constructor defect and instantiates the unmodified official
`RPGTokenizer` and `RPG` classes over an `AbstractDataset` implementation made
from hash-bound normalized files. It does not patch or vendor upstream source.

## Prepared data

The prepared manifest binds dataset/category/profile, source revision/license,
train/validation/test split IDs and file hashes, dense normalized catalog size,
canonical target-universe hash, pseudonymous item mapping, normalized
interaction sequences, semantic-ID cache, model/graph configuration and seed.
Every artifact path is relative and every file is SHA-256 checked before the
runtime is built.

The local files have these public shapes:

```json
[{"normalized_item_id": 0, "prepared_item_key": "pseudonym"}]
```

```json
[{"normalized_item_id": 0, "semantic_codes": [0, 1]}]
```

```json
[{"episode_id": "pseudonym", "normalized_item_ids": [0, 1, 2]}]
```

The train and validation files are training rows; the test file is the exact
inference split. A pending manifest may use `training.status=pending` and null
checkpoint/training-manifest hashes. After training,
`tools/finalize_rpg_prepared_dataset.py` creates the completed contract bound to
the actual files. A v2 trace rejects any non-complete training binding.

No raw item/user identity, private path, embedding, checkpoint byte, dormant
bucket or target label belongs in a public manifest or trace.

## Exact episode selection

The selection manifest supplies ordered `episode_id`, zero-based
`split_row_index`, and expected normalized target. It binds the completed
prepared-contract hash and the exact test split ID/hash. All five policies are
fixed to `reject`: missing, duplicate, out-of-split, target-mismatched and
catalog-unreachable rows. The exporter has no first-N fallback in prepared v2
mode and rejects `--episodes` there.

Dormant gap buckets and target labels remain evaluator-side joins. They are
explicitly rejected if inserted into selection rows.

## Runner and export sequence

First perform a CPU-only contract preflight:

```bash
python3 tools/run_rpg_resumable_training.py \
  --rpg-source <pinned-rpg-checkout> \
  --prepared-dataset <prepared-pending.json> \
  --prepared-root <prepared-root> \
  --output-dir <run-output> \
  --run-id <run-id> \
  --preflight-only
```

Remove `--preflight-only` and supply the desired signed training arguments for
the actual run. The runner retains epoch-boundary model, optimizer, scheduler
and RNG resumability. Each completed epoch is committed in this order:

1. atomically replace `last_state.pt` using
   `sidscope.rpg_resumable_state.v2`, including all continuous epoch records;
2. atomically replace `epoch_ledger.json` using
   `sidscope.rpg_epoch_ledger.v1`, binding the checkpoint hash and the same
   epoch records;
3. on normal invocation exit, atomically replace `run_manifest.json`.

This order permits recovery if the container stops after an epoch checkpoint
but before the invocation manifest is written. The v2 checkpoint is the
authority; an exact ledger is cross-checked, and a ledger or prior manifest
that is a strict continuous prefix is recorded as stale and recovered from the
newer checkpoint. Divergent records or hashes fail closed. The final manifest
retains the complete epoch/global-step/model-state-hash chain and identifies
which source supplied pre-resume records.

Legacy `sidscope.rpg_trained_closure_run.v1` checkpoint files remain readable
only when a matching continuous legacy `run_manifest.json` supplies their
epoch records. A legacy checkpoint with completed epochs but no matching
manifest is intentionally rejected because its missing audit history cannot be
reconstructed. Existing completed manifests and public Beauty evidence need no
migration; new or resumed long runs should retain `last_state.pt`,
`epoch_ledger.json`, and `run_manifest.json` together.

Then complete the contract:

```bash
python3 tools/finalize_rpg_prepared_dataset.py \
  --prepared-dataset <prepared-pending.json> \
  --checkpoint <best-model-state> \
  --training-manifest <run-manifest.json> \
  --output <prepared-complete.json>
```

Export only the explicitly selected rows:

```bash
python3 tools/export_rpg_trained_trace.py \
  --rpg-source <pinned-rpg-checkout> \
  --prepared-dataset <prepared-complete.json> \
  --prepared-root <prepared-root> \
  --episode-selection <episode-selection.json> \
  --checkpoint <best-model-state> \
  --training-manifest <run-manifest.json> \
  --target-universe-mode complete \
  --output <trained-trace-v2.json>
```

The exporter retains parallel per-codebook top-k scores, initial item nodes,
each propagation candidate/frontier, visited nodes, unordered SID collisions,
dense ranked items and sum/mean log-probability accounting. Prefix, beam-parent
and ancestry fields are forbidden.

Finally verify and write the compact evaluator-neutral handoff:

```bash
python3 tools/verify_rpg_trained_trace_bundle.py <trained-trace-v2.json> \
  --prepared-dataset <prepared-complete.json> \
  --episode-selection <episode-selection.json> \
  --handoff-output <rpg-downstream-handoff.json>
```

The handoff table reports catalog reachability, target SID generation, graph
reachability, resolution loss, target rank, Hit@10, NDCG@10, valid/unique and
duplicate candidates, visited nodes, parallel-score count and graph-candidate
score count. It contains no dormant labels.

## Downstream ownership and acceptance boundary

SIDScope owns these contracts, the upstream-compatible prepared loader, the
resumable runner surface, exporter, verifier and handoff. A downstream project
owns conversion of its frozen data, its episode manifest, GPU training, result
analysis and evaluator-side labels.

The bundled synthetic positive trace passes and the duplicate-selection fixture
fails closed with `duplicate_selection_row`. The Beauty v1 public five-episode
bundle remains PASS. A downstream protocol is admitted only after its own
completed prepared contract and selected trained bundle pass this verifier; the
synthetic fixture is not trained evidence for that dataset.
