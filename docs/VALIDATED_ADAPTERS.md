# Validated Adapter Status

SIDInspector counts a named-method adapter as validated only when an official
method source provides or can produce item-level SID codes that join to item
metadata or interactions, and the normalized tables pass preflight plus D1-D5.

## Validated Official Artifacts

### LETTER

- Source: official LETTER repository.
- Artifact shape: JSON item-index mapping plus item metadata and interactions.
- SIDInspector entry point: `python3 -m sidinspector.adapters.letter`.
- Validation status: preflight and D1-D5 pass on official Instruments artifact.

### LC-Rec

- Source: official LC-Rec repository and its linked Google Drive datasets.
- Artifact shape: JSON item-index mapping plus item metadata and interactions.
- SIDInspector entry point: `python3 -m sidinspector.adapters.lcrec`.
- Validation status: preflight and D1-D5 pass on official Instruments artifact.

### ReSOT Text Index

- Source: official ReSOT repository and linked `data.zip` archive.
- Artifact shape: released `Instruments.index_lemb.json` item-index mapping,
  `Instruments.item2id`, item metadata, and interaction sidecars.
- SIDInspector entry point: `python3 tools/run_v1_gate17_resot_intake.py`.
- Validation status: R759 preflight and bounded D1-D5 smoke pass on the
  released Instruments text-index artifact; the journal-extension C0-C5
  conformance report also passes source, schema, join, metric, provenance, and
  promotion checks with three pinned normalized-input hashes.
- Boundary: this is released-archive text-index intake, not a trained-generator
  result; preserve the no-license-detected reuse caveat.

### DIGER RQ-VAE

- Source: official DIGER repository, Hugging Face processed Beauty or Yelp
  embeddings and interaction JSONL, plus the matching public RQ-VAE checkpoint.
- Artifact shape: official-code-derived item-to-code export produced by running
  `RQVAE.get_indices(...)` over `Beauty.emb-llama.npy`, joined through
  `beauty.emb_map.json`.
- SIDInspector entry point: `python3 tools/run_v1_gate17_diger_intake.py`.
- Validation status: R763/R764 validate and promote Beauty; R828/R829 validate
  and promote Yelp after independent review, C0--C5, and G2/G3/G4 refresh.
- Boundary: this is tokenizer-stage official-code-derived intake, not an
  author-released item-to-SID table, not a trained-generator result, and not
  full coverage of DIGER's differentiable assignment dynamics; preserve the
  no-license-detected reuse caveat. Beauty and Yelp are separate checkpoints
  and configurations, so their diagnostic contrast is descriptive.

Example:

```bash
python3 -m sidinspector.adapters.lcrec \
  --index-json path/to/Instruments.index.json \
  --item-json path/to/Instruments.item.json \
  --inter-json path/to/Instruments.inter.json \
  --dataset-name LCRec_Instruments \
  --output-dir runs/lcrec_instruments

python3 -m sidinspector.preflight \
  --sid-assignments runs/lcrec_instruments/sid_assignments.parquet \
  --item-metadata runs/lcrec_instruments/item_metadata.parquet \
  --interactions runs/lcrec_instruments/interactions.parquet \
  --run-metric-smoke

python3 -m sidinspector.metrics \
  --sid-assignments runs/lcrec_instruments/sid_assignments.parquet \
  --item-metadata runs/lcrec_instruments/item_metadata.parquet \
  --interactions runs/lcrec_instruments/interactions.parquet \
  --output-dir runs/lcrec_instruments/diagnostics
```

## Local-Only Adapter Checks

Some method-specific code paths are useful engineering checks but are not
listed here until an official item-code artifact passes the validation
standard above. These local-only records are kept out of the public validated
adapter catalog so they are not mistaken for named-method evidence.

## Generator Coverage

Generator evidence uses a separate G0--G5 contract. DACT/TIGER now passes
G1--G5 with a released source-item/mapping/checkpoint round-trip, an ordered
prefix and beam-ancestry contract, real checkpoint smoke, public deidentified
labels, and an executable verifier. It is not a named adapter because G0 is
blocked by the upstream repository's absent code and asset license; the frozen
500-target primary also predates ancestry export and is not described otherwise.
The verified Latte/PSID tokenizer cache likewise remains below full generator
closure. RPG has a pinned non-commercial source audit, a bounded parallel
trace fixture, and an untrained official-source class smoke; its real-data
round-trip and trained asset smoke remain open, so it is not a named adapter.
LLaDA-Rec now has a pinned no-license source audit, bounded adaptive-unmasking
trace fixture, and official class-method smoke. It remains below named-adapter
status because G0 is blocked by the absent code license and no released cache,
checkpoint, official-data round-trip, or trained trace exists. ISD has moved
off source watch: its paper-linked anonymous artifact now supports an exact-
function smoke and bounded decoder-overlay contract. It remains below named-
adapter status because the snapshot lacks an immutable revision, code license,
released assets, official-data round-trip, and real model-backed trace.
ChronoSID remains on source watch.

See `docs/GENERATOR_ADAPTER_CONFORMANCE.md` and
`docs/reproducibility/generator_adapter_coverage.csv` for the typed status and
next gate of each route.
