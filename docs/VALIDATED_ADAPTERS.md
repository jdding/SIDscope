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
- Boundary: the repository still has no detected LICENSE file. On 2026-08-29,
  the first author permitted SIDScope research use of the code, datasets, and
  SID index files with citation and acknowledgment of the CIKM 2024 paper and
  stated that a repository license would be added later. SIDScope retains its
  non-redistribution policy until that file is published.

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
  result. The repository still has no detected LICENSE file. On 2026-08-29,
  the first author permitted the released resources for noncommercial academic
  research with citation of the KDD 2026 paper. SIDScope preserves the existing
  no-archive-redistribution policy because redistribution was not separately
  granted in a repository license.

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
  full coverage of DIGER's differentiable assignment dynamics. On 2026-08-29,
  the first author identified the code as MIT, stated that the Hugging Face
  artifacts may be used for research under the same terms, and said the
  repository LICENSE would be added shortly. Until that file is published,
  the inventory retains `no_license_detected` and summary-only redistribution.
  Beauty and Yelp are separate checkpoints and configurations, so their
  diagnostic contrast is descriptive.

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
G0--G5 as a configuration-bound named adapter. Its released
source-item/mapping/checkpoint round-trip, ordered prefix and beam-ancestry
contract, real checkpoint smoke, public deidentified labels, and executable
verifier are joined to a refreshed 500-target, beam-50 primary whose full
external traces contain ordered prefixes, parent ancestry, and step log
probabilities. The upstream `NOASSERTION` license state is a redistribution
marker, not an experiment or evidence blocker.
Latte/PSID now passes G0--G5 as a configuration-bound named generator adapter:
the real static cache and vocabulary round-trip are joined to public
deidentified PSID/Latte checkpoint-backed smoke bundles, external 250-episode
hash-bound diagnostics, typed expected failures, and a passing CPU verifier.
RPG passes G0--G5 as a configuration-bound named generator adapter. Its pinned
non-commercial source audit and real official-code-derived Beauty cache are
bound to a fully recorded trained output, a public five-episode deidentified
parallel graph trace, and an external 250-episode trace with complete target-
universe hash/count evidence. The route retains unordered token sets and graph
item nodes; it is not represented as an autoregressive prefix trace.
LLaDA-Rec now has a pinned source audit with a `NOASSERTION` license marker,
bounded adaptive-unmasking trace fixture, official class-method smoke, and a
real two-epoch project tokenizer engineering smoke with strict checkpoint
reload. It remains below named-adapter status because the formal frozen
tokenizer asset, complete item/SID/vocabulary round-trip, generator checkpoint,
and trained trace do not yet exist. ISD has moved
off source watch: its paper-linked anonymous artifact now supports an exact-
function smoke and bounded decoder-overlay contract. It remains below named-
adapter status because the snapshot lacks an immutable revision, released
assets, official-data round-trip, and real model-backed trace. Its license is
also retained only as a redistribution marker.

DiffGRM passes G0--G5 independently as configuration-bound VG and Steam named
adapters. Its The Web
Conference 2026 publication and immutable source revision are bound, while its
license state remains a `NOASSERTION` redistribution marker. The independent
dataset-neutral fixture verifier, real five-bucket checkpoint trace, typed
negative bundle, recoverable-training provenance, and external 250-episode
diagnostic are accepted by compact hashes and counts without redistributing the
upstream source, checkpoints, prepared data, or full traces.

See `docs/GENERATOR_ADAPTER_CONFORMANCE.md` and
`docs/reproducibility/generator_adapter_coverage.csv` for the typed status and
next gate of each route.
