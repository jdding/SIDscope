# Latte / PSID Route Status

Last audited: 2026-08-27

Current decision: `close_named_adapter`

The official Latte repository is pinned at commit
`05e4e6d983225bcb7172f148a076890e80c524d1` under the MIT license. Its
tokenizer path can generate or load item-keyed `.sem_ids` caches for PSID and
Latte configurations. The cache is suitable for normalization into the
SIDScope item-to-code contract, but no upstream released mapping or checkpoint
was identified in the audited source.

SIDScope therefore records this route below named-adapter status. The current
repository supports the tokenizer-only runtime boundary through the optional
`latte` dependency group (`faiss-cpu` and `sentence-transformers`), accepts
legal local Sentence-T5 paths without relying on name heuristics, and does not
require HuggingFace `datasets` for tokenizer-only intake.

Promotion requires all of the following:

1. generate and freeze one official-code-derived `.sem_ids` cache with source,
   configuration, item identity, and hashes;
2. normalize the cache and pass C0--C5;
3. run one bounded generator smoke and export method-facing traces;
4. pass G0--G5 with a failure fixture and a public verifier.

Until those gates pass, downstream projects should cite this record as a
verified integration route, not as a complete Latte/PSID named adapter.
