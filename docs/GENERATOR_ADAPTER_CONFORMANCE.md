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

RPG now has a pinned G0 source audit, a real official-code-derived Beauty OPQ
cache that passes non-paper-counted C0--C5 and a 12,101-item G1 round-trip, a
method-preserving G2--G4 bounded fixture, and a G5 official-source class smoke
over deterministic untrained weights. It remains below named-adapter status
because no trained checkpoint or fully recorded training output has passed
real parallel decoding and ranked-item export. The exact boundary is in
`docs/RPG_GENERATOR_ADAPTER.md` and
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

DACT/TIGER now has a complete method-facing report: the released source-item
mapping, Tools `0.6_cf` SID array, official preprocessing, checkpoint,
constrained/unconstrained primary traces, item resolution, and split identity
are hash-bound. A deterministic ordered-prefix fixture and a real four-target
CPU replay preserve parent-beam ancestry and step log-probabilities. G1--G5
pass, while G0 remains blocked because the official repository declares no
code or asset license. The route therefore remains below named-adapter status.
See `docs/DACT_TIGER_GENERATOR_ADAPTER.md` and
`docs/reproducibility/dact_tiger_adapter_status.json`.

ISD now has a paper-linked anonymous-source audit, an exact-function CPU smoke,
and an independent decoder-overlay fixture. The trace preserves base candidate
scores and ancestry, best supporting item ranks, prefix RRF survival,
collision-aware item resolution, and final RRF without inserting provider-only
items. G0 remains blocked because the anonymous artifact exposes no Git
revision or root code license and ships no data, checkpoints, SID cache, or
traces. G1 and the real-model portions of G4--G5 remain open. See
`docs/ISD_DECODER_OVERLAY_ADAPTER.md` and
`docs/reproducibility/isd_adapter_status.json`.
