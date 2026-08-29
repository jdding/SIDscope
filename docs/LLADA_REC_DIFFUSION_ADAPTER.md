# LLaDA-Rec Diffusion Trace Contract

## Audited boundary

SIDScope pins the official public repository at
`83dbcd6061da9266adcd8f68b16d1de7cc2612f3`. The repository has no detected
license file, GitHub reports no license, and no tag, release, checkpoint,
semantic-ID cache, processed dataset, or training log is published. SIDScope
therefore records links and hashes only and does not vendor upstream source.
The paper is separately available as arXiv:2511.06254v1 under CC BY 4.0; that
paper license does not license the code repository.

The source audit is
`docs/reproducibility/llada_rec_source_audit.json`. The bounded official-source
smoke dynamically loads external class methods from a caller-supplied pinned
checkout and does not copy source or instantiate a model.

## Static identity

LLaDA-Rec uses four position-specific MultiHeadVQVAE codes by default. For code
`c_p` at position `p`, the model token is:

```text
token_p = c_p + sum(codebook_size_q for q < p) + 1
```

Token zero is padding, `sum(codebook_sizes) + 1` is EOS, and the next token is
MASK. Although all item-token positions are modeled bidirectionally, their
vocabulary partitions and positions remain distinct. They are not an RPG-style
unordered set and they are not an autoregressive prefix.

The official tokenizer attempts to reduce collisions during MultiHeadVQVAE
training but does not prove a collision-free final cache. The official
evaluator compares predicted and target semantic-token tuples directly; it
does not export source items or specify how duplicate tuples map to ranked
items. SIDScope therefore keeps every matching item identity and labels a
multi-item tuple `ambiguous_semantic_id`.

## Inference state

The pinned implementation initializes every target position with MASK. At each
of four default refinement steps it:

1. computes the argmax token and its softmax confidence at every position;
2. assigns negative infinity to already filled positions;
3. selects the highest-confidence still-masked position independently per
   beam;
4. expands the beam using only the valid vocabulary partition for that
   position;
5. writes the selected token and keeps it fixed in later steps.

This is adaptive-order, masked parallel generation with beam search. It is not
left-to-right decoding. It also is not remasking: no pinned inference path
turns a filled position back into MASK. The trace schema retains
`remasked_positions` so behavior remains auditable, but requires the field to
be empty for this revision. A non-empty field fails with
`unsupported_remasking_transition`.

## Stable trace schema

The schema is `sidscope.llada_rec_diffusion_trace.v1`. It retains:

- route, trace, split, target-universe, source-item, and normalized-item IDs;
- the all-mask initial target state;
- refinement-step and beam/parent-beam identity;
- pre-state and post-state tokens and masked positions;
- confidence-selected positions, predicted tokens, and confidence values;
- explicit remasked positions;
- cumulative beam log-probability and beam-specific generation order;
- final semantic-token candidate groups and resolved ranked items;
- unresolved and ambiguous candidate counts and typed failure labels.

Candidate groups with ambiguous or unresolved semantic IDs are never silently
converted into a single ranked item.

## Reproduction

Run the public CPU fixture and verifier with:

```bash
PYTHONPATH=src python3 tools/verify_llada_rec_adapter.py
```

Re-run the source-shaped method smoke against an external pinned checkout with:

```bash
python3 tools/run_llada_rec_official_source_smoke.py \
  --llada-rec-source <pinned-LLaDA-Rec-checkout>
```

The fixture is deidentified and deterministic. The source smoke uses
handcrafted logits to verify confidence selection, all-mask initialization,
and position-valid beam expansion. Neither is a trained recommendation result.

SIDScope also ships a recoverable, revision-bound wrapper for the official
MultiHeadVQVAE tokenizer:

```bash
python3 tools/run_llada_rec_resumable_tokenizer.py --help
```

A real two-epoch engineering smoke on the frozen VG train-only catalog passed
for 17,396 normalized items using PCA128 whitening and four 256-entry
position-specific codebooks. It strictly reloaded the checkpoint and exported
17,345 unique semantic tuples (51 collision excess). The compact, path-free
record is `docs/reproducibility/llada_rec_vg_tokenizer_smoke.json`. This result
tests the data shape, official tokenizer path, atomic state, and export; it is
not the frozen formal tokenizer asset and is not a generator result.

The formal tokenizer run is now frozen separately: the same 17,396-item
train-only VG catalog completed 10,000 epochs with an actual interrupted/resume
boundary, strict checkpoint reload, and four 256-entry position-specific
codebooks. Collision resolution retained all items and produced 17,344 unique
semantic tuples (52 collision excess; 48 collision groups; maximum group size
four). The path-free hash/count record is
`docs/reproducibility/llada_rec_vg_tokenizer_formal_evidence.json`; embeddings,
the semantic-ID cache, checkpoint payload, raw IDs, and private paths remain
external and are not distributed.

The dataset-neutral prepared-data, recoverable generator, trained-trace export,
and independent verifier entry points are:

```bash
python3 tools/finalize_llada_rec_prepared_contract.py --help
python3 tools/run_llada_rec_resumable_training.py --help
python3 tools/export_llada_rec_trained_trace.py --help
python3 tools/verify_llada_rec_trained_trace_bundle.py --help
```

The v2 trained trace records native confidence-guided adaptive unmasking: every
one-position action retains the pre/post mask state, position-specific token
top-k and log probabilities, parent beam, retained/pruned frontier, raw ordered
tuple, collision-aware resolution, dense published rank, right-censoring, and
compute. It does not synthesize autoregressive prefix ancestry and it does not
claim remasking for the pinned implementation. A deidentified positive fixture
and verifier-injected binding/ancestry failures are provided under
`examples/llada_rec_trained_trace_fixture/`.

## Promotion boundary

Source and method identity pass G0 with `NOASSERTION` retained solely as a
non-redistribution marker. The formal tokenizer and prepared item-to-SID-to-
model-vocabulary round-trip close the tokenizer side of G1. Promotion to a
configuration-bound named adapter still requires the in-progress formal
generator checkpoint plus final five-episode and 250-episode trained v2 traces
to pass the independent verifier. Missing license does not block that work or
compact derived-evidence delivery.
