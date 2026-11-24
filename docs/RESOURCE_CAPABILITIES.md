# Resource Capabilities and Evidence Boundaries

| Workflow | Runs from release alone? | Runs in browser (Pyodide)? | Requires external inputs? |
| --- | --- | --- | --- |
| Deterministic rebuild & row-check of all 8 manuscript tables | Yes | Yes | No |
| 8 executable C0–C5 reports & 9-route inventory audit | Yes | Yes | No |
| C1 conformance failure fixture rejection (`sid` vs `sid_level_*`) | Yes | Yes | No |
| Live D1–D5 + `A_b` vs. `S_b` tail addressability & D7 resolver accounting | Yes | Yes | No |
| Live 4-condition D6 refresh handoff gate evaluation (DACT 0.6 → 0.7) | Yes | Yes | No |
| Bring-your-own CSV mapping audit (`D1–D5` + `A_b` vs `S_b` + triage) | Yes (user CSV) | Yes (client-side only) | User CSV |
| 125,000-row deidentified D7 trace label verification (`d7_labeled_trace_rows.csv.gz`) | Yes | No (local CPU CLI) | No |
| Canonical contracts, 46 JSON schemas, Adapter SDK 1.0 & EvidenceBundle registry | Yes | No (local CPU CLI) | User or fixture inputs |
| Upstream tokenizer/generator retraining or raw Amazon/Yelp replay | No | No | Upstream repos & datasets |

## Redistribution Boundary

- Upstream archives without explicit redistribution licenses (`no_license_detected` or restricted research terms) remain at their declared sources; SIDScope ships only code, compact summaries, deidentified trace labels, and SHA-256 hashes.
