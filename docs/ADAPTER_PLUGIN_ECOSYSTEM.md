# SIDScope Adapter Plugin Ecosystem

Status: implemented in `1.3.0.dev0`

## Boundary

SIDScope discovers external adapter packages through the
`sidscope.adapters` entry-point group. Discovery enumerates package metadata
without importing the adapter. Only `sidscope plugin preflight --name NAME`
loads the selected entry point. Core contract, payload, report, and evidence
verification never requires the producing plugin to be installed.

An entry point returns an object with `plugin_api_version = "1.0"` and two
methods: `get_capabilities()` and `get_payload_fixture()`. The capability
descriptor must use `sidscope.adapter_capabilities.v1`, support SDK `0.2.0`,
and bind its method family to the exact registered payload schema. The payload
fixture must pass its native family validator and canonical content hash.

## Failure and lifecycle rules

- duplicate entry-point names, missing plugins, load failures, API mismatch,
  protocol mismatch, invalid capabilities, and invalid payloads are typed;
- plugin discovery never imports GPU or upstream dependencies;
- runtime requirements are declarations, not an instruction for SIDScope to
  install or execute a model stack;
- plugin removal is the rollback path and does not invalidate existing
  canonical artifacts;
- a plugin passing preflight does not promote a named adapter or scientific
  result; those remain governed by conformance profiles and evidence.

## External-package proof

`examples/reference_adapter_plugin/` is installed into a temporary isolated
environment by `tools/verify_sidscope_1_3_plugin_ecosystem.py`. The verifier
first proves that core payload verification passes with no plugin installed,
then installs the external package, discovers `reference-parallel`, and runs
its full preflight. No RecBole import occurs: `probe_optional_backend()` checks
only module availability, leaving a future RecBole integration outside core.

```bash
python3 tools/verify_sidscope_1_3_plugin_ecosystem.py
```
