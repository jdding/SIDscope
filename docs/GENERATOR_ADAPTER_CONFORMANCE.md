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
  LLaDA-Rec, or confidence-guided adaptive position filling, such as DiffGRM;
- `decoder_overlay`: an external item scorer that changes candidate survival or
  final ranking without replacing the SID generator, such as ISD.

## G0--G5 Protocol

| Level | Question | Required evidence |
| --- | --- | --- |
| G0 | Is the upstream implementation and method boundary identifiable? | Official source URL, immutable revision or content-addressed snapshot, recorded license state, configuration, and checkpoint or training boundary where available. |
| G1 | Does model-facing identity round-trip to the admitted mapping? | Source item ID, normalized item ID, SID representation, model vocabulary ID, and resolved item ID for a bounded fixture. |
| G2 | Is the decoding state represented without forcing autoregressive semantics? | Ordered prefixes, unordered token sets, masked states, or overlay-supported prefixes with method-specific state fields. |
| G3 | Are validity, ambiguity, collision, and item resolution explicit? | Valid-ID policy, duplicate or aliased target handling, candidate-resolution rule, and failure labels. |
| G4 | Are traces and ranked items exportable through stable schemas? | Deidentified trace rows, ranked-item rows, scores or confidence where available, target universe, and evaluation split identity. |
| G5 | Can another user reproduce the bounded route? | One CPU fixture, one bounded model smoke, expected failure fixture, command/config/log summary, input and output hashes, and a passing verifier. |

A complete named-method generator adapter passes G0--G5. A successful training
command, tokenizer cache, or one-off trace export is useful evidence but remains
below named-adapter status until the other levels close.

License state is metadata and a redistribution boundary, not an experiment or
derived-evidence gate. `NOASSERTION` therefore does not by itself fail G0 or
block execution, verification, compact evidence delivery, or named promotion.
SIDScope still fails closed on vendoring or redistributing upstream source,
weights, data, or assets without explicit terms. Missing immutable source
identity, configuration identity, real model-facing round-trip, checkpoint, or
trained trace remains a technical gate independently of license state.

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
gate for TIGER/DACT, Latte/PSID, RPG, LLaDA-Rec, DiffGRM, and ISD.

Project-local workarounds may be attached as issue evidence, but they remain
non-canonical until the corresponding SIDScope adapter and verifier pass. This
prevents downstream projects from silently maintaining incompatible forks.

RPG now passes G0--G5 as a configuration-bound named generator adapter. Its
pinned CC BY-NC source, real official-code-derived Beauty OPQ cache,
non-paper-counted C0--C5 report, and 12,101-item G1 round-trip are joined to a
fully recorded 127-epoch trained output. A public five-episode smoke and an
external 250-episode primary preserve parallel codebook scores, unordered
item-node graph propagation, collisions, ranked items, and a shared complete
target-universe hash without exposing source identities or forcing prefix
semantics. The exact boundary is in
`docs/RPG_GENERATOR_ADAPTER.md` and
`docs/reproducibility/rpg_kdd2025_adapter_status.json`.

Latte/PSID has a real official-code-derived static cache round-trip and a
non-paper-counted C0--C5 report. Downstream-owned, hash-bound 10,000-update PSID
and Latte checkpoints each pass a public five-episode real smoke and an
external 250-episode diagnostic export. The v2 traces preserve every returned
beam, PSID's unbackfilled raw rank slots, Latte's retry attempts and latent-path
aggregation, per-step scores, item resolution, split identity, and typed
failures. G0--G5 pass, making this the first complete SIDScope named generator
adapter. The exact boundary is in
`docs/LATTE_PSID_GENERATOR_ADAPTER.md` and
`docs/reproducibility/latte_psid_adapter_status.json`.

LLaDA-Rec has a pinned source audit, an independent masked-state trace schema,
a deterministic CPU fixture, and an official class-method smoke for all-mask
initialization, confidence-selected position transfer, and position-valid beam
expansion. The pinned source monotonically unmasks positions and never remasks
filled positions. Its source-identity G0 passes with `NOASSERTION` recorded as
a non-redistribution marker, while real-data identity, fixed project-bound
assets, and trained trace gates remain open. The
exact boundary is in `docs/LLADA_REC_DIFFUSION_ADAPTER.md` and
`docs/reproducibility/llada_rec_adapter_status.json`.

DiffGRM is staged as the publication-prioritized masked/diffusion route. Its
The Web Conference 2026 paper, DOI, official repository, immutable revision,
four-position OPQ identity, and non-vendoring boundary are bound. A
dataset-neutral CPU contract preserves forward noising, adaptive reverse
masked states, real beam ancestry, raw pre-filter tuples, exact collision-aware
resolution, and typed rank censoring. Its missing root license is recorded as a
`NOASSERTION` marker and does not block development, experiments, verification,
or derived-evidence delivery; upstream redistribution remains outside the
adapter. An independent three-file CLI now verifies real prepared, selection,
and checkpoint-bound v2 trace bundles without replaying source/license audit.
The real frozen-VG OPQ4 round-trip, 10,000-step checkpoint, five-bucket native
v2 smoke, typed failure, and external 250-episode balanced diagnostic now pass.
DiffGRM is therefore a configuration-bound named adapter; the full traces stay
external and are bound by compact hashes, counts, metrics, and verifier output.
See
`docs/DIFFGRM_GENERATOR_ADAPTER.md` and
`docs/reproducibility/diffgrm_www2026_adapter_status.json`.

DACT/TIGER now has a complete method-facing report: the released source-item
mapping, Tools `0.6_cf` SID array, official preprocessing, checkpoint,
constrained/unconstrained primary traces, item resolution, and split identity
are hash-bound. A deterministic ordered-prefix fixture and a real four-target
CPU replay preserve parent-beam ancestry and step log-probabilities. G1--G5
pass, including source/configuration/checkpoint identity with `NOASSERTION` as
a non-redistribution marker. A refreshed 500-target dual-mode primary now
exports ordered prefixes and ancestry for all 25,000 rows per mode, making the
released Tools configuration a named adapter.
See `docs/DACT_TIGER_GENERATOR_ADAPTER.md` and
`docs/reproducibility/dact_tiger_adapter_status.json`.

ISD now has a paper-linked anonymous-source audit, an exact-function CPU smoke,
and an independent decoder-overlay fixture. The trace preserves base candidate
scores and ancestry, best supporting item ranks, prefix RRF survival,
collision-aware item resolution, and final RRF without inserting provider-only
items. G0 remains partial because the anonymous artifact exposes no immutable
repository revision and has a mismatched root method identity; license is only
a non-redistribution marker. It also ships no data, checkpoints, SID cache, or
traces. G1 and the real-model portions of G4--G5 remain open. See
`docs/ISD_DECODER_OVERLAY_ADAPTER.md` and
`docs/reproducibility/isd_adapter_status.json`.
