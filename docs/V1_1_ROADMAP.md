# SIDScope 1.1 Development Roadmap

Version: `1.1.1.dev0` (post-1.1.0 maintenance)
Branch: `codex/sidscope-v1.1`
Base: TOIS-submission software/resource version, public `v1.0.2` at
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
| P0 | RPG | Closed: full Beauty training, real parallel/unordered G2--G4 traces, public five-episode smoke, external 250-episode primary, and G5 verifier pass; configuration-bound `named_adapter`. 1.1.1 also provides a dataset-neutral prepared-data/explicit-selection v2 bridge; each new dataset still requires its own trained verification. |
| P0 | Latte / PSID | Complete named adapter: real static C0--C5/G1, PSID ordered-beam and Latte latent-retry G2--G4 traces, public checkpoint-backed five-episode smoke bundles, external 250-episode hash-bound diagnostics, expected failures, and G5 verifier all pass. |
| P1 | LLaDA-Rec | Source audit and bounded adaptive-unmasking schema/fixture complete; next obtain an explicit code license plus fixed tokenizer/checkpoint assets before real G1 and trained G4--G5. |
| P1 | DiffGRM | Publication-prioritized masked/diffusion route staged: WWW 2026 identity, revision, dataset-neutral OPQ4/prepared/selection/native-trace contracts, positive/negative fixtures, and non-executing verifier pass. Record explicit author code permission before import/execution; then VG five-episode and 250-episode closure before Steam. |
| P1 | TIGER / DACT | Method-facing report complete: G1--G5 pass; obtain an explicit upstream code/asset license and rerun the 500-target primary with ancestry export to unblock G0 and promotion. |
| P2 | Item-Supported Decoding | Paper-linked anonymous source, exact-function smoke, and bounded overlay contract are complete; obtain an immutable official revision and code license, then bind data/checkpoints and a real trace. |
| P2 | ChronoSID | Keep on source watch until official tokenizer and generator assets are available. |

The machine-readable state is
`docs/reproducibility/generator_adapter_coverage.csv`.

## Promotion Rule

A route becomes a named adapter only after its source identity, model-facing
item round-trip, method-specific decode state, validity and resolution policy,
trace and ranked-item exports, CPU fixture, bounded model smoke, hashes, and
verifier pass. A successful training command or one-off cache remains evidence,
not adapter closure.

Latte/PSID and RPG are promoted under this rule. Both promotions are
configuration-bound and do not alter the submitted TOIS paper. RPG retains
parallel unordered token sets and item-node graph propagation; it is not
represented as a TIGER-style autoregressive prefix trace.

## Release Gate

Status: annotated `v1.1.0` publication and unauthenticated public URL smoke
pass. The post-release `1.1.1.dev0` maintenance tree closes RPG P0 and must pass
its own tests, package verifier, archive smoke, and G8 before a future release.

Before `v1.1.0`:

- all focused and package tests pass in a clean environment;
- the release archive contains only manifest-approved files;
- optional dependencies remain isolated from the core install;
- each promoted adapter has positive and expected-failure fixtures;
- public URL smoke is rerun against the final tag;
- the TOIS paper directory remains unchanged.
