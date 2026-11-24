# SIDScope

**A diagnostic, conformance, and observability resource for Semantic-ID interfaces in generative recommendation.**

[Release v2.0.0](https://github.com/jdding/SIDscope/releases/tag/v2.0.0) |
[Browser Workbench (`index.html`)](index.html) |
[CIKM '26 Foundation (SIDInspector)](https://doi.org/10.1145/3799682.3840174) |
[SIDDuet (Search & Rec)](https://jdding.github.io/SIDDuet/) |
[MIT License](LICENSE)

SIDScope (`v2.0.0`, resource portal upgrade) is an open-source diagnostic toolkit, conformance suite, and reproducibility package for inspecting Semantic-ID (`item_id -> SID`) mappings as reusable recommendation interfaces. It does not reimplement upstream tokenizer or generator training; it audits mappings, prefix consumers, generated beams, and refresh handoffs across **three core research workflows**:

| Workflow / Research Question | Core question | Entry point |
| --- | --- | --- |
| **RQ1 · Mapping Structure (`D1–D5`)** | How do released mappings differ in code use, shared addresses, prefix alignment (`D3`), tail allocation (`A_b`) vs. global singleton addressability (`S_b`), and trie structure? | `sidscope` workflows · [Algorithm-engineer quickstart](docs/SIDSCOPE_USER_WORKFLOWS.md) |
| **RQ2 · Downstream Consumers (`Exposure` & `D7`)** | When do prefix assignments beat capacity- & popularity-matched controls at a fixed candidate budget, and how much of the path-survival vs. singleton-credit gap does an explicit resolver recover? | `tools/verify_sidscope_paper_tables.py` · [D7 trace release](docs/reproducibility/d7_labeled_trace_release.json) |
| **RQ3 · Refresh & Model Handoff (`D6`)** | When a mapping refresh closes catalog coverage gaps but introduces code churn, can an existing generator checkpoint reuse the new mapping or must it be adapted under a 4-condition handoff gate? | `src/sidscope/refresh.py` · [SID refresh guide](docs/SIDSCOPE_SID_REFRESH.md) |

See [what this release supports](docs/RESOURCE_CAPABILITIES.md) for package-only, browser-only, and own-data workflows, and [how SIDScope relates to SIDInspector and SIDDuet](docs/RELATION_TO_SIDINSPECTOR_AND_SIDDUET.md).

## Browser Workbench (Zero-Install Pyodide & Local HTTP)

Serve [`index.html`](index.html) from a local static server (`python3 -m http.server 8768`) — or open the hosted GitHub Pages URL (`https://jdding.github.io/SIDscope/`, pending Pages activation after this branch is published) — to run SIDScope directly in your browser using a pinned standard-library Pyodide runtime (`v314.0.7`):

- **Tab 1 · RQ1 Mapping Diagnostics & `A_b` vs `S_b`:** Executes live Python D1–D5 diagnostics with an interactive **Stratum Allocation (`A_b`) vs. Global Singleton (`S_b`)** comparison and runs `tools/build_sidscope_paper_tables.py` live to rebuild and verify the 8-route Table 3 / Table 5 matrix.
- **Tab 2 · RQ2 Exposure Controls & D7 Beam Resolvers:** Runs live resolver comparisons (Path Survival vs. Singleton Credit vs. Uniform Draw vs. Popularity Resolver) on ambiguous beams alongside verified Table 4, Table 5 (fixed-budget Beauty/Instruments), Table 6, and Table 7 summaries.
- **Tab 3 · RQ3 Refresh Audit & Handoff Gate (D6):** Evaluates the 4-condition preregistered handoff gate live and verifies the DACT Tools `0.6 -> 0.7` refresh audit (5,364 held-out targets, Table 8A aggregate + Table 8B post-hoc target-code stratification).
- **Tab 4 · Conformance Gates (`C0–C5` & `G0–G5`):** Executes the public C1 failure fixture live (proving inconsistent `sid` vs `sid_level_*` rejection), inspects all 8 frozen C0–C5 reports, and checks the 9-route source/license inventory.
- **Tab 5 · Inspect Your Own Mapping (BYO CSV):** Paste or pick local CSV files (`item_id,sid_0,sid_1,...` + optional interactions & metadata) to run full D1–D5, `A_b` vs `S_b` tail audit, and interactive triage cards **100% client-side** — nothing leaves your browser.

All executed scripts and evidence summaries are SHA-256 verified against `PACKAGE_MANIFEST.json` before execution.

## Install and Quickstart

CPU-only (Python 3.9+, accepted baseline macOS arm64 / CPython 3.9.6; no GPU required). The historical Python import package remains `sidinspector` for CIKM compatibility; new integrations should use the curated `sidscope` Python facade and `sidscope` CLI.

```sh
git clone --branch codex/sidscope-v2 https://github.com/jdding/SIDscope.git
cd SIDscope
python3 -m pip install --upgrade "pip>=21.3"
python3 -m pip install .

# 1. Rebuild & verify all 8 manuscript tables row-by-row from compact sources
python3 tools/verify_sidscope_paper_tables.py

# 2. Run the full resource-package verifier & C0-C5 conformance checks
python3 tools/verify_sidscope_resource_package.py
python3 tools/verify_adapter_conformance_assets.py

# 3. Validate canonical contracts & inspect available public schemas
sidscope contract list
sidscope schema list

# 4. Launch the isolated local browser workbench
python3 tools/serve_demo.py --port 8765
```

For auditing your own CSV/Parquet mappings and ranked-item outputs, start with [docs/BRING_YOUR_OWN_DATA.md](docs/BRING_YOUR_OWN_DATA.md) and [docs/SIDSCOPE_USER_WORKFLOWS.md](docs/SIDSCOPE_USER_WORKFLOWS.md). See [ARTIFACT_QUICKSTART.md](ARTIFACT_QUICKSTART.md) for the complete command reference and `evidence-full` archive instructions.

## Measured CPU Runtime and Memory

Single-machine CPU benchmarks (macOS arm64, Python 3.9.6, no GPU required):

| Workload | Scale | Wall time | Peak RSS |
| --- | --- | ---: | ---: |
| `tools/verify_sidscope_paper_tables.py` | 8 manuscript tables + 8 C0–C5 reports + G22 | 0.07 s | 15 MiB |
| `tools/verify_adapter_conformance_assets.py` | 9-route inventory + 8 C0–C5 + C1 failure fixture | 0.49 s | 87 MiB |
| `tools/validate_resource_portal.py` | Portal SHA-256 manifest + pure-Python workbench | 0.16 s | 23 MiB |
| `tools/verify_sidscope_resource_package.py` | Full package, quickstart, D7 labels & evidence gates | 35.6 s | 125 MiB |

## Relationship to SIDInspector and SIDDuet

| Resource | Core Scope | Status & Relationship |
| --- | --- | --- |
| **[SIDInspector](https://github.com/jdding/sidinspector)** | Mapping-first D1–D5 diagnostics + optional D6 churn on single-task `item_id -> SID` exports. | Published at **CIKM '26 Resource Track** (`10.1145/3799682.3840174`). |
| **SIDScope** (this repo) | Substantial extension adding source-traced C0–C5/G0–G5 conformance, `A_b` vs `S_b` addressability separation, fixed-budget exposure controls, trained D7 beam-resolver accounting, D6 4-gate refresh handoffs, Adapter SDK 1.0, 46 JSON schemas, and immutable EvidenceBundles. | **TOIS** manuscript under review (`v2.0.0` resource release). Retains `sidinspector` import compatibility. |
| **[SIDDuet](https://github.com/jdding/SIDDuet)** | Dual-task **search vs. recommendation** shared-SID allocation calibration, count-matched references, and temporal pooling. | Companion two-task resource. |

See [docs/RELATION_TO_SIDINSPECTOR_AND_SIDDUET.md](docs/RELATION_TO_SIDINSPECTOR_AND_SIDDUET.md).

## Artifact and Evidence Coverage

| Surface | Verified Scope |
| --- | --- |
| Named tokenizer inventory | 9 source-traced exports across 7 families (`ReSID`, `ReSID-GAOQ`, `GRID`, `CARD`, `DIGER` Beauty & Yelp, `ReSOT`, `LETTER`, `LC-Rec`); 8 executable C0–C5 reports + 1 auditable snapshot |
| Fixed-budget exposure controls | 2,000 validation users × 19 popularity-stratified permutations on `GRID/Beauty`, `CARD/Beauty`, and `ReSOT/Instruments` (budgets 50 / 100 / 200) |
| Trained D7 trace release | 125,000 deidentified labeled beam rows (`GRID/P5` folds 0 & 1, `DIGER` sensitivity, `DACT/TIGER` constrained vs. unconstrained) |
| Refresh & handoff case | DACT Tools `0.6 -> 0.7` (275 coverage gaps closed, 23.6% churn, 5,364 held-out targets, 3 seeds passing 4/4 gates in 4,999/4,999 draws + changed-code subgroup audit) |
| Platform & conformance core | 11 canonical contracts, 46 public JSON schemas, Adapter SDK `1.0.0`, 5 native trace payload families, immutable SHA-256 `EvidenceBundle v1` + rebuildable SQLite registry |

## Architecture, Governance & Historical Boundaries

- System architecture & roadmap: [docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md](docs/SIDSCOPE_SYSTEM_ARCHITECTURE.md) · [docs/V1_2_TO_V2_ROADMAP.md](docs/V1_2_TO_V2_ROADMAP.md)
- Versioning & compatibility policy: [docs/VERSIONING.md](docs/VERSIONING.md) · [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) · [docs/MIGRATING_1_X_TO_2_0.md](docs/MIGRATING_1_X_TO_2_0.md)
- Release profiles (`runtime` / `conformance` / `evidence-full`): [docs/SIDSCOPE_RELEASE_PROFILES.md](docs/SIDSCOPE_RELEASE_PROFILES.md) · [docs/SIDSCOPE_RESOURCE_PACKAGE.md](docs/SIDSCOPE_RESOURCE_PACKAGE.md) · [docs/SIDSCOPE_DATASHEET.md](docs/SIDSCOPE_DATASHEET.md) · [docs/SIDSCOPE_MAINTENANCE.md](docs/SIDSCOPE_MAINTENANCE.md)
- Conformance & SDK: [docs/ADAPTER_CONFORMANCE.md](docs/ADAPTER_CONFORMANCE.md) · [docs/GENERATOR_ADAPTER_CONFORMANCE.md](docs/GENERATOR_ADAPTER_CONFORMANCE.md) · [docs/ADAPTER_SDK.md](docs/ADAPTER_SDK.md) · [docs/EVIDENCE_BUNDLES_AND_REGISTRY.md](docs/EVIDENCE_BUNDLES_AND_REGISTRY.md)

Note on historical structure-only submissions:

```sh
# This historical structure-only fixture is an expected rejection after
# diagnostic recomputation became mandatory:
sidscope submission check \
  --root examples/conformance_ecosystem_fixture/submission/positive
# status=rejected; code=independent_gate_verification_required
```

For a current recomputed positive submission and own-producer workflow, follow [docs/SIDSCOPE_USER_WORKFLOWS.md](docs/SIDSCOPE_USER_WORKFLOWS.md).

<details>
<summary>Machine-checked SDLC &amp; 2.0.0 release governance snapshot (ADR-0025 / ADR-0028)</summary>

Build and smoke-test a `runtime` archive outside the repository:

```sh
python3 tools/build_sidscope_release_candidate_archive.py \
  --profile runtime --output /tmp/sidscope-runtime.zip
python3 tools/smoke_sidscope_release_candidate_archive.py \
  /tmp/sidscope-runtime.zip --profile runtime
python3 tools/run_sidscope_g8_fresh_env_smoke.py \
  --archive /tmp/sidscope-runtime.zip --profile runtime \
  --result-json /tmp/sidscope_g8_fresh_env_smoke.json
```

<!-- SIDSCOPE:CURRENT:BEGIN -->
Current package: `2.0.0`; GitHub main remains 1.1.x; 2.0 publication uses `codex/sidscope-v2` (ADR-0028).
Current diagnostic admission and comparison require input-bound recomputation; declarations alone do not pass.
Unclosed SDLC requirements: F09.
Requirement snapshot: `d84f1b924e203550bd953ad5254467d09079fc49aee229ed85e189e890ac0e2c`.
Acceptance scope: `docs/reproducibility/sidscope_acceptance_scope.v1.json` revision 2 snapshot `fc0ab4a29822290d43eb190364443c5afbc7d288de57ed30988f0269f26db9db`.
Acceptance scope decision: independent_user_actual_use excluded from current gates (2026-09-27, docs/adr/0025-remove-independent-user-acceptance-gate.md); the adoption fact stays not_verified.
Historical route decisions (not newly recomputed training): dact_tiger=named_adapter; diffgrm_www2026=named_adapter; isd=close_named_adapter; latte_psid=named_adapter; llada_rec=named_adapter; rpg_kdd2025=named_adapter.
Historical route snapshot: `cb51983ca33506c4c00f1722eda8e5eb9eb452409ce026f9810a76fe1cf02a92`.
Independent user actual use is excluded from current certification, RC and delivery gates by acceptance scope policy revision 2; it remains not verified and is not a current prerequisite. The project owner authorized the 2.0 RC-to-release sequence on 2026-10-08 (ADR-0028); automated checks do not grant publication authority. Main, origin and frozen TOIS mutations remain unauthorized.
<!-- SIDSCOPE:CURRENT:END -->

</details>

## License and Citation

SIDScope code is released under the [MIT License](LICENSE). Upstream checkpoints, raw Amazon/Yelp datasets, and archives without explicit redistribution licenses remain at their declared sources (`docs/reproducibility/sidscope_source_license_config_inventory.csv`).

```bibtex
@article{ding2026sidscope,
  author  = {Jiandong Ding and Huijie Qin and Tiandeng Wu and Yi Cao},
  title   = {{SIDScope}: A Diagnostic Resource for Semantic-ID Interfaces in Generative Recommendation},
  journal = {Author-prepared preprint (extension of CIKM 2026 SIDInspector)},
  year    = {2026},
  url     = {https://github.com/jdding/SIDscope/releases/tag/v2.0.0}
}
```

[`CITATION.cff`](CITATION.cff) provides both the SIDScope citation and the foundational CIKM 2026 SIDInspector reference (`10.1145/3799682.3840174`).
