# Relationship to SIDInspector and SIDDuet

SIDScope is the substantial journal extension of **SIDInspector** (CIKM '26 Resource Track) and a companion resource to **SIDDuet** (search vs. recommendation dual-task SIDs):

| Dimension | **SIDInspector** (CIKM '26) | **SIDScope** (this repo, TOIS) | **SIDDuet** (Search & Rec) |
| --- | --- | --- | --- |
| **Core unit** | Static `item_id -> SID` mapping | Reusable SID interface: mapping + consumer exposure + generated traces + refresh handoff + package conformance | Shared SID mapping joined to paired `(S_i, R_i)` search and recommendation observations |
| **Mapping probes** | D1–D5 + optional D6 churn | D1–D5 + explicit `A_b` (stratum allocation) vs `S_b` (global singleton) separation + D3 estimand checks | Per-group allocation JSD, disjoint task leaders, band-matched & exact-total count-matched references |
| **Downstream / lifecycle** | Bounded fixed-reranker exposure probe; D7 input hook | Fixed-budget permutation controls (Beauty & Instruments), trained D7 beam-resolver accounting (125k deidentified rows), D6 4-gate refresh handoff (DACT 0.6→0.7) | Fixed-candidate coverage audit (UniSAR) & temporal pooling vs. task-conditioned exposure forecasting (Qilin) |
| **Governance** | Preflight gate + SHA-256 manifest | C0–C5 & G0–G5 conformance, Adapter SDK 1.0, 46 JSON schemas, 5 native trace families, immutable EvidenceBundles | Paired-observation contracts, RoleMapRecord schema, SHA-256 manifest |

## Compatibility

- SIDScope preserves the `sidinspector` Python import namespace for full backward compatibility with CIKM 2026 diagnostic scripts while exposing the curated `sidscope` facade and CLI for new integrations.
