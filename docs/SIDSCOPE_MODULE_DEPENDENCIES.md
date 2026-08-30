# SIDScope Module Dependency Contract

Status: enforced SIDScope 1.2 boundary

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
adapters_core    -> contracts + sdk + trace
cli              -> all target-module public APIs
```

The names `conformance_core` and `adapters_core` distinguish the target shared
modules from the route-oriented `conformance.py` and `adapters/` compatibility
authorities that remain active during the 1.2--1.5 migration. Legacy modules
are grandfathered only until their inventory entries migrate or become archived.

## Rules

- `contracts` never imports legacy verifiers, adapters, GPU libraries, or
  optional upstream runtimes.
- Target modules never import `cli`.
- Core bundle verification never imports `adapters_core` or an external plugin.
- Cross-module imports use public module APIs; reaching into another module's
  private implementation is forbidden.
- A new target module or dependency edge requires an update to the
  machine-readable matrix, architecture tests, and an ADR when it changes the
  accepted topology.

`tests/test_architecture_boundaries.py` enforces the matrix. Contracts, SDK,
trace, evaluation, conformance_core, evidence, and CLI now have active package
surfaces. `adapters_core` remains planned for the 1.3 plugin lifecycle; current
route-specific `adapters/` modules remain compatibility authorities.
