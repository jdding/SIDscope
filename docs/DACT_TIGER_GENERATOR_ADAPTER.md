# DACT / TIGER Generator Adapter

Status: G0--G5 pass; configuration-bound named adapter.

This route binds the official DACT Tools `0.6_cf` SID mapping and released
TIGER/T5 checkpoint to SIDScope's autoregressive generator contract. The
pinned repository contains no LICENSE or COPYING file and GitHub reports no
license; SIDScope records that state as `NOASSERTION`, not as a technical gate.
SIDScope ships links,
hashes, derived summaries, and an independently written deidentified fixture;
it does not vendor the upstream source, arrays, parquet data, or weights.

## Pinned Source And Assets

- official repository: `https://github.com/HomesAmaranta/DACT`;
- revision: `0b8d8cec88fee83b2384dd236628c2802f337d26`;
- paper: `https://arxiv.org/abs/2603.29705` and DOI
  `10.1145/3805712.3809645`;
- snapshot: Tools `0.6_cf`;
- released mapping: 9,610 four-code rows and 9,610 unique full SIDs;
- released TIGER checkpoint: 4,652,288 parameters;
- released test split: 11,693 history-target rows.

All asset, source, and configuration hashes are in
`docs/reproducibility/dact_tiger_source_audit.json`. The paper's arXiv
distribution license does not license the repository code or its assets.

## G0--G5 Field Mapping

| Gate | DACT/TIGER field mapping | Status |
| --- | --- | --- |
| G0 | Official repository, immutable commit/tree, paper/DOI, model configuration, released checkpoint/mapping/test hashes, and no-license finding. | **Pass**: source, method, configuration, and asset identity are fixed; `NOASSERTION` remains a non-redistribution marker. |
| G1 | Raw item key in `item_mapping.npy` -> one-based normalized ID -> row in `Tools_0.6_cf.npy` -> `raw_code + position * 256 + 1` -> reverse-resolved item. Official `GenRecDataset` preprocessing parity also passes. | **Pass** |
| G2 | `ordered_autoregressive_prefix_beam`; each transition records prefix depth, parent beam, appended token, ordered prefix, token log-probability, and cumulative/sequence score. The revised G21 exporter also records Hugging Face `beam_indices`. | **Pass** on the fixture and a four-target released-checkpoint CPU replay. The historical 500-target primary predates ancestry export. |
| G3 | A full path is valid iff it resolves in the snapshot catalog. Unresolved paths are `invalid_path`; multiple items for one full SID are `ambiguous_path`; resolution returns every matching item. Constrained and unconstrained G21 modes retain separate accounting. | **Pass** |
| G4 | The fixture exports stable trace, candidate, and ranked-item rows with scores and split identity. The released runner exports pseudonymous trace IDs, ordered prefixes, ancestry, sequence scores, resolved items, failure labels, and the released test protocol. The public compact D7 release removes identities, paths, and scores while preserving all 50,000 DACT label rows. | **Pass**, with upstream-dependent full outputs kept external. |
| G5 | Deterministic CPU fixture, typed invalid-position-token fixture, four-target/two-mode released-checkpoint CPU smoke, official preprocessing parity, primary G21/G22 summaries, input/output hashes, tests, and executable verifier. | **Pass** |

## Minimal Contract

The reusable contract is implemented in `sidinspector.adapters.dact` and is
exercised by `examples/dact_tiger_autoregressive_fixture/manifest.json`.
Unlike RPG or LLaDA-Rec, DACT/TIGER is genuinely autoregressive: a child beam
must equal its named parent prefix plus exactly one token from that position's
disjoint vocabulary range. Final candidate order is stable by descending
log-probability, then token path and beam ID. Item resolution never collapses a
full-SID collision.

Run the public verifier:

```bash
PYTHONPATH=src python3 tools/verify_dact_tiger_adapter.py
```

The optional real-asset replay uses `tools/run_v1_gate21_tiger_d7_trace.py`
with an external checkout and explicit checkpoint, mapping, test, and
expected-input paths. The public package intentionally does not make those
large or unlicensed files implicit dependencies.

## Promotion Boundary

The released Tools `0.6_cf` configuration is a `named_adapter`. A 2026-08-29
refresh reran the 500-target, beam-50 constrained and unconstrained primary and
exported ordered prefixes, parent ancestry, step log-probabilities, validity,
and item resolution for all 25,000 rows per mode. Full rows remain external;
`docs/reproducibility/dact_tiger_ancestry_refresh_evidence.json` binds their
hashes, counts, metrics, runtime, and frozen inputs. Historical aggregates are
retained as regression evidence rather than being relabeled retroactively.
