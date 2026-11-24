# Artifact Quickstart

Use Python 3.9+ on CPU (no GPU required; accepted 2.0 baseline: macOS arm64 / CPython 3.9.6). Install via `python3 -m pip install .` (or `-e .` for development).

The browser workbench ([`index.html`](index.html), served locally via `python3 -m http.server 8768` or at `https://jdding.github.io/SIDscope/` once GitHub Pages is activated) executes the released Python scripts directly in your browser (pinned Pyodide `v314.0.7`, SHA-256 verified against `PACKAGE_MANIFEST.json`) across RQ1–RQ3, C0–C5 conformance, and client-side BYO CSV audits with zero installation.

## 1. Rebuild and verify all 8 manuscript tables

```sh
python3 tools/verify_sidscope_paper_tables.py
```

Rebuilds all 8 manuscript tables from `docs/reproducibility/paper_table_sources/`, the 8 frozen C0–C5 reports, and the DACT G22 handoff summaries, comparing every row against the frozen snapshots.

## 2. Verify adapter conformance & C1 rejection fixture

```sh
python3 tools/verify_adapter_conformance_assets.py
python3 tools/verify_resot_resource_walkthrough.py
```

Checks the 9-route source/license/config inventory, verifies the 8 frozen C0–C5 reports and their input hashes, confirms the public failure fixture fails C1 only, and deterministically rebuilds the ReSOT walkthrough.

## 3. Run the full resource-package verifier

```sh
python3 tools/verify_sidscope_resource_package.py
```

Validates package importability, reviewer quickstart, paper tables, D7 125,000-row deidentified trace labels, reproducibility matrix, and governance boundaries.

## 4. Audit your own mapping & ranked-item outputs

Use the public `sidscope` workflows (`docs/SIDSCOPE_USER_WORKFLOWS.md`) or run the local interactive web workbench (`docs/BRING_YOUR_OWN_DATA.md`):

```sh
python3 tools/serve_demo.py --port 8765
```

Open <http://127.0.0.1:8765> to run isolated SHA-256 verification of all RQ1–RQ3 workflows or audit a custom CSV in memory.

## 5. Inspect canonical contracts & schemas

```sh
sidscope contract list
sidscope schema list
sidscope schema validate --input examples/dataset_identity_fixture/dataset_identity.json
```

See [docs/SIDSCOPE_USER_WORKFLOWS.md](docs/SIDSCOPE_USER_WORKFLOWS.md) and [docs/SIDSCOPE_SID_REFRESH.md](docs/SIDSCOPE_SID_REFRESH.md) for own-producer EvidenceBundles and refresh comparisons.
