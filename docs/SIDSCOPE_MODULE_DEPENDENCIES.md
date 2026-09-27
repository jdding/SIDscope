# SIDScope Module Dependency Contract

Status: enforced SIDScope boundary including opt-in workflows and tools (2026-09-27)

Machine-readable authority:
`docs/reproducibility/sidscope_module_dependencies.json`

SIDScope remains one Python distribution and one local process. The target
modules use public APIs and the following allowed dependency direction:

```text
contracts        -> standard library
sdk              -> contracts
trace            -> contracts
evaluation       -> contracts + trace
conformance_core -> contracts + trace + evaluation
evidence         -> contracts + evaluation + conformance_core
submission       -> contracts + conformance_core + evidence
adapters_core    -> contracts + sdk + trace
cli              -> all target-module public APIs
```

The names `conformance_core` and `adapters_core` distinguish the target shared
modules from the route-oriented `conformance.py` and `adapters/` compatibility
authorities that remain active during the 1.2--1.5 migration. Legacy modules
are grandfathered only until their inventory entries migrate or become archived.

## Workflow and application layers

`sidscope_modules` records the opt-in `src/sidscope` workflow modules
(`workflows`, `mapping_check`, `regression`, `diagnostic_review`, `refresh`,
`pipeline`, `native_bridge`, `observed_review`). Each module lists its allowed
core imports, allowed same-layer workflow imports and allowed legacy imports
(`sidinspector.metrics`, `sidinspector.churn`, `sidinspector.adapters.latte`).
The directions are one-way:

```text
sidscope workflows -> declared core facades + declared workflow modules
core (sidinspector) -> never sidscope workflows, CLI, or tools
sidscope workflows  -> never tools
tools              -> sidinspector facades + sidscope workflows; never reversed
```

`application_rules` additionally freezes:

- `tool_to_tool_imports`: every production tool-to-tool import edge. A new or
  removed edge must update the matrix; the test fails on both unrecorded and
  stale edges.
- `producer_plugin_entry` (`sidscope.pipeline`) as the only runtime module
  allowed to dynamically load a caller-selected producer module
  (`importlib.import_module`/`__import__`). `importlib.metadata` and
  `importlib.resources` remain the sanctioned discovery and resource APIs.
- Dynamic producer loading by ordinary input artifacts is forbidden; only the
  explicit producer entry executes caller-selected plugins.

## Rules

- `contracts` never imports legacy verifiers, adapters, GPU libraries, or
  optional upstream runtimes.
- Target modules never import `cli`.
- Core bundle verification never imports `submission`, `adapters_core` or an
  external plugin. The submission application service orchestrates public
  contract, profile and evidence APIs; it owns no canonical identity, profile
  decision or bundle semantics.
- Cross-module imports use public module APIs; reaching into another module's
  private implementation is forbidden.
- A new target module or dependency edge requires an update to the
  machine-readable matrix, architecture tests, and an ADR when it changes the
  accepted topology.

`tests/test_architecture_boundaries.py` enforces the matrix over core, the
sidscope workflow layer and production tools, including relative and
function-level imports; violation fixtures run from temporary directories, and
an in-process check confirms the imported facades never pull torch, upstream
model runtimes or external plugin modules. Static checking cannot prove every
runtime path: installed-package isolation is additionally exercised by the
G8 fresh-environment consumers. All target modules, including `adapters_core`,
now have active package surfaces. Plugin discovery loads only the selected
entry point during explicit preflight; current route-specific `adapters/`
modules remain compatibility authorities.
