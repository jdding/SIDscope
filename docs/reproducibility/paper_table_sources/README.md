# Paper Table Sources

These compact CSV files, together with the released source inventory,
conformance records, ReSOT walkthrough JSON, and compact G20 trained-trace
summary are the inputs to
`tools/build_sidscope_paper_tables.py`. Each generated row records the value
shown in the paper together with its evidence source or provenance boundary.
The files make all ten manuscript-table reconstructions deterministic without
redistributing upstream raw datasets, checkpoints, cloud payloads, or local
experiment caches.

The generated snapshots live in `docs/reproducibility/paper_tables/` and are
checked row by row by `tools/verify_sidscope_paper_tables.py`.
