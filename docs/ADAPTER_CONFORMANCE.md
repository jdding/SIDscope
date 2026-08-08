# Adapter Conformance Protocol

SIDScope evaluates an artifact route in six ordered layers. Passing a file
schema is necessary but does not by itself authorize a paper-facing method row.

| Level | Question | Required evidence |
| --- | --- | --- |
| C0 | Is the source identity and reuse boundary explicit? | URL, immutable revision or retrieval record, derivation label, license status. |
| C1 | Are the normalized tables internally coherent? | Required columns, contiguous `sid_level_*` fields, exact `sid` reconstruction, expected item count. |
| C2 | Do mappings, metadata, and interactions join? | Existing SIDScope preflight and complete-coverage report unless partial coverage is explicitly allowed. |
| C3 | Can the route execute the diagnostic interface? | Bounded D1-D5 smoke, including explicit D1 per-level output, with recorded limits. |
| C4 | Can another user identify the command and exact inputs? | Command vector, runtime class, root-contained evidence, and predeclared SHA-256 hashes for all three normalized inputs. |
| C5 | May the route be promoted into the paper matrix? | Exact identity, dataset, depth, configuration, license, redistribution, and evidence match to the inventory; controls and partial-coverage routes cannot count. |

Run the protocol with:

```bash
PYTHONPATH=src python3 tools/check_adapter_conformance.py \
  --manifest docs/reproducibility/conformance/resot_instruments_manifest.json \
  --output docs/reproducibility/conformance/resot_instruments_report.json
```

The JSON schema is
`docs/reproducibility/conformance/adapter_manifest.schema.json`. The executable
checker is authoritative for semantic constraints that JSON Schema alone does
not express, including joins, SID reconstruction, input hashes, and inventory
promotion.

The current public evidence contains seven paper-counted C0-C5 executions:
`ReSID-GAOQ / Video`, `GRID / P5 Beauty`, `CARD RQ-VAE / P5 Beauty`,
`DIGER RQ-VAE / Beauty`, `ReSOT text-index / Instruments`, and `LETTER /
Instruments`, plus `LC-Rec / Instruments`. They cover a returned
official-code-derived route, a tokenizer-stage rebuild, checkpoint or
code-derived routes, and released index or archive routes. ReSID/Musical
remains the sole auditable snapshot without a complete reconstruction route.

The bundled negative fixture is intentionally inconsistent and must fail C1
only:

```bash
PYTHONPATH=src python3 tools/check_adapter_conformance.py \
  --manifest examples/conformance_failure_fixture/manifest.json \
  --allow-fail
```

Run `python3 tools/verify_adapter_conformance_assets.py` to validate all seven
frozen route reports, rerun the negative fixture, and check the inventory
evidence boundary without requiring non-redistributable upstream inputs.
