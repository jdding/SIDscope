# Generator Adapter Conformance

SIDScope keeps generator integration separate from the C0--C5 mapping
contract. C0--C5 establishes that an item-to-SID artifact is source-traced,
internally coherent, joinable, diagnosable, and eligible for named mapping
coverage. It does not establish that a generator, decoding overlay, or temporal
protocol can be reproduced and audited.

## Adapter Kinds

Generator integrations declare one of four kinds:

- `autoregressive_generator`: ordered prefix decoding, such as TIGER or PSID;
- `parallel_generator`: unordered or jointly predicted SID components, such as
  RPG;
- `diffusion_generator`: masked-state refinement and remasking, such as
  LLaDA-Rec;
- `decoder_overlay`: an external item scorer that changes candidate survival or
  final ranking without replacing the SID generator, such as ISD.

Temporal augmentation is recorded as `temporal_protocol` until an official
implementation binds both the tokenizer and generator stages.

## G0--G5 Protocol

| Level | Question | Required evidence |
| --- | --- | --- |
| G0 | Is the upstream implementation identifiable and reusable? | Official source URL, immutable revision, license state, configuration, and checkpoint or training boundary. |
| G1 | Does model-facing identity round-trip to the admitted mapping? | Source item ID, normalized item ID, SID representation, model vocabulary ID, and resolved item ID for a bounded fixture. |
| G2 | Is the decoding state represented without forcing autoregressive semantics? | Ordered prefixes, unordered token sets, masked states, or overlay-supported prefixes with method-specific state fields. |
| G3 | Are validity, ambiguity, collision, and item resolution explicit? | Valid-ID policy, duplicate or aliased target handling, candidate-resolution rule, and failure labels. |
| G4 | Are traces and ranked items exportable through stable schemas? | Deidentified trace rows, ranked-item rows, scores or confidence where available, target universe, and evaluation split identity. |
| G5 | Can another user reproduce the bounded route? | One CPU fixture, one bounded model smoke, expected failure fixture, command/config/log summary, input and output hashes, and a passing verifier. |

A complete named-method generator adapter passes G0--G5. A successful training
command, tokenizer cache, or one-off trace export is useful evidence but remains
below named-adapter status until the other levels close.

## Method-Specific Trace Surfaces

The common export carries route ID, trace ID, target item, resolved items,
ranked items, validity, ambiguity, and provenance. Method-specific fields remain
typed rather than being flattened into an autoregressive prefix:

- autoregressive routes record prefix depth and beam ancestry;
- RPG-style routes record predicted token sets and graph-valid completion;
- diffusion routes record mask state, refinement step, remasking decision, and
  confidence;
- decoder overlays record base candidates, support scores, pruning survival,
  and final reranking.

## Current Coverage

The machine-readable status ledger is
`docs/reproducibility/generator_adapter_coverage.csv`. It distinguishes released
reference evidence from complete named-method adapters and records the next
gate for TIGER/DACT, Latte/PSID, RPG, LLaDA-Rec, ISD, and ChronoSID.

Project-local workarounds may be attached as issue evidence, but they remain
non-canonical until the corresponding SIDScope adapter and verifier pass. This
prevents downstream projects from silently maintaining incompatible forks.

RPG currently has a pinned G0 source audit, a method-preserving G1--G4 bounded
fixture, and a G5 official-source class smoke over deterministic untrained
weights. It remains below named-adapter status because a real official-data
round-trip and trained checkpoint or fully recorded training-output smoke have
not passed. The exact boundary is in `docs/RPG_GENERATOR_ADAPTER.md` and
`docs/reproducibility/rpg_kdd2025_adapter_status.json`.

Latte/PSID has a real official-code-derived static cache round-trip and a
non-paper-counted C0--C5 report, plus a method-preserving latent-token fixture
and official tokenizer/aggregation class-method smoke. It remains below named
generator status because no trained checkpoint or recorded training output has
passed bounded inference and real trace export. The exact boundary is in
`docs/LATTE_PSID_GENERATOR_ADAPTER.md` and
`docs/reproducibility/latte_psid_adapter_status.json`.

LLaDA-Rec has a pinned source audit, an independent masked-state trace schema,
a deterministic CPU fixture, and an official class-method smoke for all-mask
initialization, confidence-selected position transfer, and position-valid beam
expansion. The pinned source monotonically unmasks positions and never remasks
filled positions. G0 is blocked because the code repository has no detected
license, while real-data identity and trained trace gates remain open. The
exact boundary is in `docs/LLADA_REC_DIFFUSION_ADAPTER.md` and
`docs/reproducibility/llada_rec_adapter_status.json`.
