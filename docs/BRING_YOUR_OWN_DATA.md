# Bring Your Own Mapping, Traces, or Refresh Pair

SIDScope inspects exported mappings, ranked-item outputs, generated beams, and refresh pairs without modifying or retraining your upstream model.

## Option 1 · Zero-Install Browser Workbench (Client-Side CSV)

Serve [`index.html`](../index.html) locally (`python3 -m http.server 8768`, or open `https://jdding.github.io/SIDscope/` once GitHub Pages is enabled) and switch to **Tab 5 · Inspect Your Own Mapping**. Paste CSV text or pick local `.csv` files (`item_id,sid_0,sid_1,...` + optional `interactions.csv` and `item_metadata.csv`). Note: if `interactions.csv` declares an explicit `split` column (`train`/`valid`/`test`), SIDScope uses `train` rows only and fails closed when zero `train` rows are present. Pyodide runs D1–D5, the RQ1 **Stratum Allocation (`A_b`) vs. Global Singleton (`S_b`)** split, and actionable triage cards 100% client-side — zero bytes leave your browser.

## Option 2 · Algorithm-Engineer Workflows (`sidscope.workflows`)

For full CSV/Parquet mapping audits, ranked-item evaluation, and compatibility-checked EvidenceBundle comparisons, follow [docs/SIDSCOPE_USER_WORKFLOWS.md](SIDSCOPE_USER_WORKFLOWS.md):

```sh
sidscope contract list
sidscope schema validate --input path/to/dataset_identity.json
```

## Option 3 · Mapping Refresh Audit (`ordered_prefix`, `parallel_positions`, `unordered_set`)

To compare two mapping revisions before re-deploying a generator checkpoint, see [docs/SIDSCOPE_SID_REFRESH.md](SIDSCOPE_SID_REFRESH.md) and `src/sidscope/refresh.py`.

## Option 4 · Register a New Tokenizer or Generator Adapter (`C0–C5` / `G0–G5`)

- Static item-to-SID exports follow [docs/ADAPTER_CONFORMANCE.md](ADAPTER_CONFORMANCE.md) (`C0–C5`).
- Generator, diffusion, and decoder-overlay traces follow [docs/GENERATOR_ADAPTER_CONFORMANCE.md](GENERATOR_ADAPTER_CONFORMANCE.md) (`G0–G5`) and [docs/ADAPTER_SDK.md](ADAPTER_SDK.md) (`Adapter SDK 1.0.0`).
- External plugins load lazily via the `sidscope.adapters` entry point without core edits; see [examples/reference_adapter_plugin/](../examples/reference_adapter_plugin/).
