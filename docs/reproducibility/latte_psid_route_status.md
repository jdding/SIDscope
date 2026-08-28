# Latte / PSID Route Status

Last audited: 2026-08-28

Current decision: `named_adapter`

## Closed Static Cache Route

The official Latte repository is pinned at
`05e4e6d983225bcb7172f148a076890e80c524d1` under the MIT license. SIDScope
generated one real official-code-derived PSID cache for Amazon Reviews 2023
Musical Instruments using:

- dataset revision `2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e`;
- 5-core `last_out` histories;
- Sentence-T5 revision `fc5d4628481afbbaaacd7af6bb07cf9d3865f781`;
- sentence metadata, PCA 192;
- `rqkmeans`, three codebooks, codebook size 256;
- the pinned official metadata-cleaning, RQ-kmeans, and PSID conflict-resolution methods.

The cache binds 57,439 users, 24,587 items, 511,836 interactions, and 24,587
metadata records. Its source item identity is Amazon `parent_asin`; the 1-based
Latte item token and zero-based SIDScope item identity are retained separately.
The external normalized route passes C0--C5 as a non-paper-counted
post-submission resource row.

The audited Amazon Reviews 2023 dataset card did not declare an explicit
license identifier. Consequently, raw histories, metadata text, sentence
embeddings, the real `.sem_ids` cache, and normalized tables are not
redistributed. SIDScope publishes the fixed revisions, exact configuration,
counts, SHA-256 hashes, and bounded C0--C5 diagnostics. The source and license
record is `latte_psid_source_audit.json`; cache and intake evidence are
`latte_psid_musical_cache_build.json` and
`latte_psid_musical_intake.json`.

## Closed Generator Route

The deidentified CPU fixture and pinned official-source class-method smoke
establish:

- PSID and Latte model-vocabulary offsets;
- source item to normalized item to SID to model vocabulary to resolved item;
- ordered autoregressive SID state;
- Latte's preceding latent token;
- `agg_max` and `agg_sum` latent-path aggregation;
- typed invalid-latent, unresolved-SID, collision, duplicate-key, and
  catalog-mismatch failures;
- stable beam and ranked-item exports.

The static evidence is supplemented by two downstream-owned, hash-bound
10,000-update checkpoints. PSID and Latte each passed a five-episode real smoke
with one episode from every frozen natural gap bucket, followed by a
250-episode diagnostic export with 50 episodes per bucket. The public smoke
bundles preserve all native beam rows and pass the v2 verifier on CPU.

PSID exports 12,500 beam rows and 2,500 raw evaluation slots in the full
diagnostic, including four invalid slots that retain their original ranks.
Latte exports both attempts for all 250 retry episodes, 37,500 beam rows, and
2,500 dense ranked items after latent-path aggregation. All four positive
smoke/full bundles pass, and all four derived missing-ancestry bundles fail
closed with `missing_beam_ancestry`.

The public package redistributes only the two deidentified five-episode smoke
bundles. The 250-episode bundles and checkpoints remain external; their hashes,
configuration, split identity, counts, and verifier results are frozen in
`latte_psid_trained_trace_evidence.json`. These balanced traces establish
adapter conformance, not full-population effectiveness and not evidence for the
frozen TOIS submission.

The authoritative machine-readable status and executable verifier are
`latte_psid_adapter_status.json` and
`tools/verify_latte_psid_adapter.py`. The combined route now passes G0--G5 and
is the first complete SIDScope named generator adapter. This promotion applies
to the verified PSID ordered-beam and Latte latent-retry configurations; it
does not turn an arbitrary tokenizer cache or incompatible checkpoint into a
verified generator.
