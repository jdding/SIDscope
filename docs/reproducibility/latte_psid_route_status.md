# Latte / PSID Route Status

Last audited: 2026-08-27

Current decision: `close_named_adapter`

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

## Generator Boundary

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

They do not establish trained generator behavior. No checkpoint was released
in the official source, and SIDScope has not trained or admitted one. G2--G5
therefore remain partial until a configuration-bound checkpoint or fully
recorded training output passes bounded inference and real trace export.

The authoritative machine-readable status and executable verifier are
`latte_psid_adapter_status.json` and
`tools/verify_latte_psid_adapter.py`. Downstream projects may reuse the static
cache adapter contract, but must not describe the tokenizer cache or fixture as
a complete Latte named generator adapter.
