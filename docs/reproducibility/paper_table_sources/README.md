# Paper Table Sources

These compact CSV files, together with the released source inventory,
conformance records, ReSOT walkthrough JSON, compact G20--G21 trained-trace
summaries, and the G22 released-refresh handoff
summary are the inputs to
`tools/build_sidscope_paper_tables.py`. Each generated row records the value
shown in the paper together with its evidence source or provenance boundary.
The files make all ten manuscript-table reconstructions deterministic without
redistributing upstream raw datasets, checkpoints, cloud payloads, or local
experiment caches.

The generated snapshots live in `docs/reproducibility/paper_tables/` and are
checked row by row by `tools/verify_sidscope_paper_tables.py`.

Three generated filenames retain pre-TOIS numbering for manifest stability:
manuscript Table 8 is `table10_g20_trained_trace.csv`, manuscript Table 9 is
`table8_resot_walkthrough.csv`, and manuscript Table 10 is
`table9_resource_contract.csv`. The canonical table/figure ledger records this
mapping explicitly.
