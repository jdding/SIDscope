# SIDScope Native Trace Payloads

Status: five registered payload families in `1.3.0.dev0`

TraceEnvelope provides common provenance and bounded observations. Its bound
native payload preserves method-family semantics rather than forcing every
generator into autoregressive beam ancestry.

| Method family | Schema | Native invariant |
| --- | --- | --- |
| Autoregressive prefix | `sidscope.trace_payload.autoregressive_prefix.v1` | Ordered prefix transitions, real parent ancestry, and per-step top-k. |
| Parallel graph/token-set | `sidscope.trace_payload.parallel_graph_token_set.v1` | Unordered token sets, parallel scores, visited nodes, and graph frontier; synthetic AR ancestry is forbidden. |
| Masked diffusion | `sidscope.trace_payload.masked_diffusion.v1` | Mask states, selected unmask positions/order, per-position top-k, retained/pruned beams, and final raw tuples. |
| Latent retry | `sidscope.trace_payload.latent_retry.v1` | Ordered retries, latent-state hashes, true beam candidates, acceptance, and failure state. |
| Decoder overlay | `sidscope.trace_payload.decoder_overlay.v1` | Base ranking, provider support, fused ranking, and non-inserting overlay semantics. |

Every payload also binds payload ID, family, schema revision, privacy flags,
resolution events, termination/failure state, and canonical content SHA-256.
The machine authority is `sidscope.trace_payload_registry.v1`; registry and
profile registries are themselves hash verified.

The reusable fixture manifest covers five positive round trips and seven typed
failures: ancestry, privacy, termination, resolution, rank censoring,
capability, and payload binding. Conformance profiles compose
`common.generator.v1` with exactly one family profile and produce a
deterministic dependency order.

```bash
sidscope trace payload list
sidscope trace payload validate \
  --input examples/native_trace_payload_fixtures/masked_diffusion.json
sidscope profile list
sidscope profile compose --profile family.masked_diffusion.v1
```

These payloads are additive 1.3 contracts and do not rewrite route-specific
1.1 evidence. Immutable EvidenceBundle storage and SQLite projection remain a
1.4 concern.
