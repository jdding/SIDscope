# SIDScope Datasheet

Status: current TOIS journal-extension resource datasheet
Last updated: 2026-08-08

## Resource Identity

- Name: SIDScope
- Paper title: SIDScope: Artifact-Level Diagnostics for Semantic-ID
  Generative Recommendation
- Software package: `sidinspector`
- Resource type: artifact-level diagnostic and reproducibility resource
- Primary users: researchers building, comparing, or reviewing Semantic-ID
  tokenizer artifacts for generative recommendation.

## Intended Use

SIDScope is intended to inspect existing item-to-Semantic-ID mappings before or
alongside downstream generative recommender experiments. It supports:

- adapter normalization into a shared `item_id -> SID` schema;
- preflight validation over item metadata and interactions;
- D1-D5 mapping diagnostics;
- optional D6 refresh/churn diagnostics;
- optional prefix-candidate calibration analysis;
- D7 constrained-aware generator-trace labeling and bounded trace accounting.

SIDScope is not a tokenizer trainer, generator trainer, or downstream
recommendation benchmark.

The current paper-facing matrix spans ReSID, GRID, CARD, LETTER, LC-Rec,
ReSOT, and DIGER source routes. DIGER/Yelp adds the only non-Amazon route, so
the current coverage is seven named families, nine routes, and two data
ecosystems. Controls and stress/reference rows are reported separately and do
not count as additional named families.

## Inputs

Required diagnostic inputs:

- `sid_assignments`: one row per item, with `item_id`, `sid`, `dataset`,
  `method`, and `sid_level_<k>` columns.
- `item_metadata`: one row per item, with at least `item_id`; optional fields
  include `dataset`, `category`, `title`, `brand`, and `text`.
- `interactions`: user-item interactions with `user_id` and `item_id`;
  optional fields include `dataset`, `timestamp`, and `split`.

Optional inputs:

- old/new SID assignments for churn;
- candidate-exposure manifests;
- generator beam/trace rows for D7 labeling.

## Outputs

Core outputs:

- D1 utilization reports;
- D2 aliasing/collision reports;
- D3 neighborhood alignment reports;
- D4 popularity allocation reports;
- D5 structural cost reports;
- optional D6 churn reports;
- optional D7 trace-label summaries.

The reviewer package includes compact evidence snapshots under
`docs/reproducibility/` and CPU-only examples under `examples/`.

## Coverage

The current SIDScope evidence chain covers:

- official upstream snapshot rows for LETTER and LC-Rec style artifacts;
- official-code-derived ReSID GAOQ rows for Musical Instruments and Video
  Games;
- faithful GRID/P5 Beauty tokenizer-stage intake;
- bounded local reference/control rows;
- an explicit R138 local stress/reference row that is not faithful GRID
  coverage.

The paper-facing coverage must remain tied to the exact run records and
limitations in `experiments/v1_evidence_chain/CLAIM_LEDGER.md` and
`experiments/v1_evidence_chain/G7_LITE_CLAIM_PACKAGE_BOUNDARY.md`.

## Data And Privacy

The reviewer package does not include private data, credentials, SSH targets,
cloud logs, raw Amazon/P5/HF datasets, or model checkpoints. It ships small
synthetic/example CSVs and compact evidence snapshots.

Users are responsible for ensuring that any external item metadata or
interaction logs they inspect with SIDScope are legally shareable and
appropriately anonymized.

## Compute

The packaged quickstart, verifier, preflight checks, and D1-D5 diagnostics are
CPU-only. Full regeneration of some evidence rows depends on upstream public
artifacts or prior tokenizer training and is intentionally represented as
tracked snapshots or provenance rather than fresh-checkout regeneration.

## Known Limitations

- Candidate-exposure analysis is a proxy/triage signal, not a trained
  downstream quality claim.
- D7 includes public-beam accounting and a repeated-observation trained
  trie-constrained ambiguity case. It supports path-versus-item observability,
  not a generator failure mechanism or D1-D5 predictivity claim.
- Some evidence rows are snapshots because raw artifacts are too large or
  depend on external upstream pipelines.
- CIKM V0 is accepted; SIDScope is being prepared as a disclosed TOIS
  substantial extension with a final overlap audit before submission.

See `docs/SIDSCOPE_LIMITATIONS.md` for the paper-facing limitation policy.
