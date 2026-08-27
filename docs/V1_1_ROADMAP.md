# SIDScope 1.1 Development Roadmap

Version: `1.1.0.dev0`
Branch: `codex/sidscope-v1.1`
Base: public `v1.0.2` at
`6ae5c4f02da3eae0cf187683d9af4c7c66e8cfa0`

## Boundary

SIDScope 1.1 is a software and resource-maintenance line. The submitted TOIS
manuscript is frozen in its paper repository and is not part of this worktree.
New adapters, fixes, and evidence may inform a future revision, but they do not
retroactively change submitted claims or tables.

## Objectives

1. Make tokenizer intake robust in hermetic downstream environments.
2. Separate static mapping admission (C0--C5) from generator and decoder
   admission (G0--G5).
3. Replace project-local workarounds with reusable named-method adapters and
   bounded public fixtures.
4. Keep the core package CPU-friendly and isolate optional method runtimes.

## Adapter Queue

| Priority | Route | Next closure |
| --- | --- | --- |
| P0 | RPG | Real official-data C0--C5 round-trip and trained checkpoint or recorded-training-output G5 smoke; bounded unordered contract is complete. |
| P0 | Latte / PSID | Static closure complete: one real official-code-derived cache is hash-frozen and passes non-paper-counted C0--C5; next train or bind one checkpoint and close real G2--G5 inference traces. |
| P1 | LLaDA-Rec | Define masked-state, refinement-step, confidence, and remasking trace schemas before implementation. |
| P1 | TIGER / DACT | Backfill the released reference trace into a complete method-facing G0--G5 report. |
| P2 | Item-Supported Decoding | Treat as a decoder overlay; reopen when official source or a versioned reproduction route is available. |
| P2 | ChronoSID | Keep on source watch until official tokenizer and generator assets are available. |

The machine-readable state is
`docs/reproducibility/generator_adapter_coverage.csv`.

## Promotion Rule

A route becomes a named adapter only after its source identity, model-facing
item round-trip, method-specific decode state, validity and resolution policy,
trace and ranked-item exports, CPU fixture, bounded model smoke, hashes, and
verifier pass. A successful training command or one-off cache remains evidence,
not adapter closure.

## Release Gate

Before `v1.1.0`:

- all focused and package tests pass in a clean environment;
- the release archive contains only manifest-approved files;
- optional dependencies remain isolated from the core install;
- each promoted adapter has positive and expected-failure fixtures;
- public URL smoke is rerun against the final tag;
- the TOIS paper directory remains unchanged.
