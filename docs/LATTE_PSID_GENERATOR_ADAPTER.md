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
`sidscope.latte_psid_trained_trace_bundle.v2`. The bundle is deliberately
stricter than an aggregate evaluation manifest. It binds the dataset manifest,
split, `.sem_ids` cache, checkpoint, training configuration, execution command,
and log summary by SHA-256. Every deidentified episode must preserve:

- whether the trace is PSID or Latte and its native decoder-state kind;
- every decode attempt, including an official Latte retry rather than only the
  final retry result;
- all returned final beams, raw generated-token slots, actual decoded and
  ancestry lengths, padded ancestry, typed termination, ordered semantic and
  model-vocabulary tokens, per-step log-probabilities, sequence scores, and
  compute accounting;
- validity, failure labels, normalized item resolution, ranked items, scores,
  and the number of latent paths supporting each item;
- one stable split identity and a hash computed over canonical deidentified
  `(normalized_item_id, ordered model-vocabulary SID tokens)` rows.

Early-ended or invalid Hugging Face beams remain first-class trace rows. Raw
PAD token `0`, `beam_indices=-1`, or their canonical `null` padding forms are
allowed only outside the declared decoded/ancestry lengths. Invalid SID slices
may retain PAD or sentinel codes, but they must have a null resolved item plus
typed failure labels. Valid beams must resolve to an exact canonical target
universe row. The verifier still requires exactly `num_beams` final rows for
every attempt.

PSID and Latte expose different ranking surfaces. PSID exports the exact first
top-k `evaluation_slots`, including typed invalid slots, because its evaluator
does not backfill past an invalid raw beam. A valid item after an invalid slot
therefore keeps its original rank. Latte continues to export dense
`ranked_items` after latent-path aggregation over the final attempt.

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

The Latte positive schema fixture is
`examples/latte_psid_trained_trace_fixture/manifest.json`; it retains one
early-ended PAD/`-1` beam. The companion `psid_evaluation_slots.json` keeps an
invalid rank-1 slot and a valid item at rank 2. Unit tests also remove beam
ancestry and inject a raw identity field to prove fail-closed behavior. Passing
the synthetic fixtures proves only the intake contract; gate status changes
only after a real checkpoint-bound bundle passes.

## Real Trained Closure

Two downstream-owned 10,000-update checkpoints now close the real generator
gates without redistributing checkpoint files. Each method first passed one
episode from each of five frozen natural gap buckets and then a 250-episode
diagnostic export with 50 episodes per bucket:

| Method | Public smoke | Full diagnostic | Native rows retained | Ranking surface |
| --- | ---: | ---: | ---: | --- |
| PSID | 5 episodes | 250 episodes | 250 smoke beams; 12,500 full beams | raw first-10 evaluation slots; four invalid full slots remain unbackfilled |
| Latte | 5 episodes | 250 episodes | 750 smoke beams; 37,500 full beams across both attempts | 10 dense ranked items after final-attempt latent-path aggregation |

All four positive bundles pass the v2 verifier. Four derived negative bundles
that remove beam ancestry are rejected as `missing_beam_ancestry`. The two
deidentified smoke bundles are shipped under
`examples/latte_psid_trained_trace_real_smoke/`; the full bundles remain
external and are bound by
`docs/reproducibility/latte_psid_trained_trace_evidence.json`.

The evidence binds the dataset manifest, split, SID cache, training
configuration, checkpoint, command, log summary, target universe, and bundle
by SHA-256. It contains normalized item identities only. The balanced full
traces are adapter-conformance diagnostics rather than full-population
effectiveness estimates, and they are not evidence for the frozen TOIS
submission.

### Migration from v1

Version 1 accepted only complete positive-token beams and contiguous dense
ranked items. It cannot faithfully encode HF early termination or PSID's raw
evaluation ranks and is rejected rather than silently reinterpreted. Producers
must migrate as follows:

1. Set the bundle schema to `sidscope.latte_psid_trained_trace_bundle.v2` and
   declare PAD, EOS, and ancestry padding IDs.
2. Preserve every returned final beam in its original order. Add
   `generated_token_slots`, `decoded_length`, `beam_ancestry`,
   `ancestry_length`, `step_log_probabilities`, and `termination_reason`.
   Preserve tail PAD/`-1` values or convert only those padding slots to `null`.
3. Retain invalid or partial SID slices with typed failure labels and null item
   resolution; do not drop, backfill, or fabricate them.
4. Hash the sorted canonical target-universe rows, not catalog cardinality, and
   bind the same hash at bundle evidence and episode levels.
5. For PSID, export the exact consumed top-k beams as `evaluation_slots`. For
   Latte, export aggregated dense `ranked_items` as before.

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
That distinction remains enforced, but the verified PSID and Latte
configurations now add real checkpoint-bound G2--G4 traces and G5 smoke/full
evidence to the existing G0/G1 closure. The combined route therefore passes
G0--G5 and is promoted to a complete named adapter. Promotion is limited to
the hash-bound source, cache, configurations, and checkpoints recorded above;
an arbitrary `.sem_ids` cache or incompatible checkpoint is not covered. The
authoritative status is
`docs/reproducibility/latte_psid_adapter_status.json`.
