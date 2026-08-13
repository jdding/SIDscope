# Paper Table Sources

These compact CSV files, together with the released source inventory,
conformance records, ReSOT walkthrough JSON, compact G20--G21 trained-trace
summaries, and the G22 released-refresh handoff
summary are the inputs to
`tools/build_sidscope_paper_tables.py`. Each generated row records the value
shown in the paper together with its evidence source or provenance boundary.
The files make all eight manuscript-table reconstructions deterministic without
redistributing upstream raw datasets, checkpoints, cloud payloads, or local
experiment caches.

The generated snapshots live in `docs/reproducibility/paper_tables/` and are
checked row by row by `tools/verify_sidscope_paper_tables.py`.

Several generated filenames retain pre-redesign numbering for manifest
stability. The manuscript uses `table10_g20_trained_trace.csv` for Table 6,
`table8_resot_walkthrough.csv` for Table 7, and
`table9_resource_contract.csv` for Table 8. The canonical table/figure ledger
records this mapping explicitly.

The earlier `table3_source_inventory.csv` and `table7_trace_accounting.csv`
snapshots remain package evidence for backward compatibility, but they are no
longer manuscript tables. Their detailed records are consumed through the
source inventory and D7 label-release verifiers instead.
