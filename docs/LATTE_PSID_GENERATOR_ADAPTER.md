# Latte / PSID Cache And Generator Contract

SIDScope treats Latte and PSID as related but distinct autoregressive
generator routes. They may share one conflict-free `.sem_ids` cache, but a
cache is not a Latte generator adapter: Latte adds a latent token before the
ordered SID and aggregates multiple latent paths that resolve to the same
item.

## Audited Source Boundary

- Official source: `https://github.com/hyp1231/Latte`
- Fixed revision: `05e4e6d983225bcb7172f148a076890e80c524d1`
- Source license: MIT
- Paper: `https://arxiv.org/abs/2605.06331v1`
- Released checkpoint: none found
- Released `.sem_ids` cache: none found
- Released processed dataset: none found in the source repository

The executable source and asset audit is
`docs/reproducibility/latte_psid_source_audit.json`. SIDScope does not vendor
the upstream code, raw Amazon data, metadata text, sentence embeddings, or a
checkpoint.

The official Amazon Reviews 2023 dataset card did not declare an explicit
license identifier in the audited surface. Therefore the real generated cache
and normalized tables remain external; the public package freezes their
source revisions, configuration, row counts, SHA-256 hashes, and bounded
diagnostic report only. Sentence-T5 is pinned separately and its model card
declares Apache-2.0.

## Static Cache Identity

The upstream processed state contains four coupled files:

| File | Identity role |
| --- | --- |
| `id_mapping.json` | `[PAD]=0`, source `parent_asin`, 1-based model item token, and inverse mapping |
| `metadata.sentence.json` | source item to cleaned metadata sentence |
| `all_item_seqs.json` | source user to longest ordered item history |
| `sentence-t5-base_rqkmeans_3x256_psid.sem_ids` | source item to three zero-based codebook values |

SIDScope normalizes one source item as:

```text
source parent_asin
  -> Latte item token (1..N; PAD is 0)
  -> normalized item_id = Latte item token - 1
  -> ordered semantic codes
  -> PSID or Latte model-vocabulary tokens
  -> conflict-free reverse lookup to the same source item
```

Admission rejects duplicate JSON keys, incomplete catalog coverage, mapping
inverse mismatches, wrong SID depth, non-integer or out-of-range codes, and any
post-resolution SID collision. These failures are typed by
`LatteCacheContractError`.

## Model Vocabulary

For codebook value `c_l`, codebook size `K`, level `l`, and `L` Latte latent
tokens:

```text
PSID token_l  = c_l + l*K + 1
Latte token_l = c_l + L + l*K + 1
```

Token 0 remains padding. Latte latent tokens occupy `1..L`; semantic tokens
begin at `L+1`. The static semantic codes are shared, but the model vocabulary
identities are not.

## Method-Specific Decode State

PSID emits an ordered semantic-ID prefix. Latte emits:

```text
decoder start -> latent token -> SID level 0 -> SID level 1 -> SID level 2 -> EOS
```

The stable Latte trace schema is
`sidscope.latte_autoregressive_trace.v1`. Each beam retains:

- beam and parent-beam identity;
- latent token;
- ordered semantic codes and offset model-vocabulary tokens;
- normalized log-probability;
- resolved source and normalized item identity;
- validity and failure labels.

Valid beams resolving to the same item are aggregated by either the maximum
beam score (`agg_max`) or log-sum-exp (`agg_sum`). Ranked items retain the
aggregated score and number of supporting latent paths. Invalid latent tokens,
out-of-range codes, wrong depth, unresolved SIDs, and cache collisions remain
explicit; they are not silently converted to zero rows.

## Trained-Trace Handoff

Downstream projects can submit a bounded checkpoint-backed handoff through
`sidscope.latte_psid_trained_trace_bundle.v1`. The bundle is deliberately
stricter than an aggregate evaluation manifest. It binds the dataset manifest,
split, `.sem_ids` cache, checkpoint, training configuration, execution command,
and log summary by SHA-256. Every deidentified episode must preserve:

- whether the trace is PSID or Latte and its native decoder-state kind;
- every decode attempt, including an official Latte retry rather than only the
  final retry result;
- final-beam ancestry, ordered semantic and model-vocabulary tokens, per-step
  log-probabilities, sequence scores, and compute accounting;
- validity, failure labels, normalized item resolution, ranked items, scores,
  and the number of latent paths supporting each item;
- one stable split identity and a hash of the target universe.

Raw user IDs, source item IDs, targets/labels, checkpoint paths, and absolute
local paths are rejected. Confidence summaries, aggregate metrics, or claims
that all steps were scored do not substitute for the actual ancestry and
per-step score rows. A handoff is intentionally bounded to at most 256
episodes, so it can be checked on CPU without redistributing a checkpoint.

Validate a candidate bundle with:

```bash
PYTHONPATH=src python3 tools/verify_latte_psid_trained_trace_bundle.py \
  --bundle <deidentified-trained-trace-bundle.json> \
  --result-json <verification-result.json>
```

The positive schema fixture is
`examples/latte_psid_trained_trace_fixture/manifest.json`. Unit tests also
remove beam ancestry and inject a raw identity field to prove fail-closed
behavior. Passing the synthetic fixture proves only the intake contract; gate
status changes only after a real checkpoint-bound bundle passes.

## Reproduction Commands

The full cache build is deliberately outside the core install:

```bash
python3 tools/build_latte_psid_cache.py \
  --upstream-root <pinned-Latte-checkout> \
  --train-csv <pinned-Musical_Instruments.train.csv> \
  --valid-csv <pinned-Musical_Instruments.valid.csv> \
  --test-csv <pinned-Musical_Instruments.test.csv> \
  --metadata-jsonl <pinned-meta_Musical_Instruments.jsonl> \
  --output-dir <external-processed-dir> \
  --model-cache-dir <external-model-cache> \
  --report <external-build-report.json> \
  --dataset-revision 2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e \
  --sent-emb-revision fc5d4628481afbbaaacd7af6bb07cf9d3865f781
```

Normalize and run bounded D1--D5 intake with:

```bash
PYTHONPATH=src python3 tools/normalize_latte_psid_cache.py \
  --processed-dir <external-processed-dir> \
  --output-dir <external-normalized-dir> \
  --summary <external-intake-summary.json>
```

The public deterministic fixture is
`examples/latte_psid_cache_fixture/manifest.json`. It is explicitly
deidentified and is not a substitute for the real cache. The official-source
smoke can be rerun without downloading model weights:

```bash
python3 tools/run_latte_official_source_smoke.py \
  --upstream-root <pinned-Latte-checkout>
```

## Promotion Boundary

Static cache admission and generator admission remain separate. A real
official-code-derived cache may pass C0--C5 without proving Latte generation.
The route remains below complete named-adapter status until a trained,
configuration-bound PSID/Latte checkpoint or fully recorded training output
passes bounded inference, exports real latent-path traces and ranked items,
and reproduces those outputs under G5. The authoritative status is
`docs/reproducibility/latte_psid_adapter_status.json`.
