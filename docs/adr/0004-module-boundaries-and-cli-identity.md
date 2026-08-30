# ADR-0004: Enforce Module Boundaries and Add the `sidscope` CLI Facade

## Status

Accepted on 2026-08-30.

## Context

ADR-0002 selected a modular monolith but did not define executable import rules
or settle how the public SIDScope command coexists with the released
`sidinspector` distribution and Python import. The 1.2 migration must not break
existing imports or let optional adapter runtimes leak into core verification.

## Goals

- make the target module graph testable;
- provide a product-named command without a disruptive package rename;
- keep legacy route CLIs runnable during migration;
- keep core contracts independent of optional GPU/runtime dependencies.

## Non-Goals

- renaming the Python distribution or import package in 1.x;
- removing route-specific tools before parity;
- creating independently deployed services.

## Constraints

- the package remains one Python 3.9+ distribution and local process;
- existing `import sidinspector` callers must continue to work;
- clean CPU verification cannot import upstream method runtimes;
- compatibility wrappers need owners and retirement conditions.

## Decision Drivers

| Priority | Driver | Measurement |
| ---: | --- | --- |
| 1 | Backward compatibility | Existing imports and legacy CLIs keep passing. |
| 2 | Boundary enforcement | Illegal target-module imports fail architecture tests. |
| 3 | Product clarity | Users receive one stable `sidscope` command facade. |
| 4 | Reversibility | One command/entity can return to the legacy path independently. |

## Options Considered

| Option | Advantages | Disadvantages | Reversibility |
| --- | --- | --- | --- |
| Rename distribution and import package immediately | Uniform name. | High breakage and migration cost before the new API is stable. | Hard. |
| Keep only route-specific Python commands | No packaging change. | No coherent product facade and continued CLI drift. | Easy but rejects the target. |
| Keep `sidinspector` distribution/import and add a `sidscope` console facade | Additive, compatible, and supports entity-by-entity migration. | Temporary dual identity must be documented. | High. |

## Decision

Through 1.x, the distribution and Python import remain `sidinspector`. The
console command is `sidscope`. A future import/distribution rename requires a
separate ADR and a deprecation window; it is not implied by 2.0.

The allowed target-module graph is machine-readable in
`docs/reproducibility/sidscope_module_dependencies.json` and explained in
`docs/SIDSCOPE_MODULE_DEPENDENCIES.md`. Architecture tests activate a module's
rules when its package directory exists. Legacy modules are explicitly listed
as compatibility authorities and are not silently treated as target modules.

The first facade command is:

```text
sidscope contract validate --type source-identity --input PATH
```

Each later command is added as a vertical slice with positive and typed-negative
fixtures plus legacy parity where a legacy authority exists.

## Architecture Impact

- `contracts` imports no legacy adapter/verifier or optional runtime;
- `cli` orchestrates public target-module APIs and contains no contract logic;
- core bundle verification will not import plugins or `adapters_core`;
- `pyproject.toml` is primary package metadata and `setup.py` remains a checked
  compatibility shim with the same version and console entry point.

## Rollout, Validation, and Rollback

Add the facade command without removing any legacy command. Validate direct
Python calls, installed console execution, archive smoke, and G8. If a shared
command changes legacy meaning, remove or reroute only that dispatch and retain
the old authority. The package/import identity remains unchanged.

## Consequences

Positive:

- SIDScope gains a stable user-facing command with no import break;
- dependency drift becomes a test failure;
- migration can proceed one entity and one route at a time.

Negative and tradeoffs:

- documentation must explain the temporary `sidscope`/`sidinspector` split;
- `setup.py` and `pyproject.toml` remain duplicated metadata until the minimum
  supported installer no longer needs the compatibility shim;
- legacy modules coexist with target modules through 1.5.
