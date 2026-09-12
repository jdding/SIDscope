# SIDScope algorithm-engineer quickstart

New approved local workflows: [paired multi-run regression, actionable offline
review and one-command observed-input analysis](SIDSCOPE_REGRESSION_WORKFLOWS.md).
These are optional development modules; existing commands and canonical output
contracts are unchanged. No complete actual-user adoption is claimed.

## Optional observed-native acceptance (source checkout / evidence-full)

After an explicitly authorized external observer produces `native.json`,
`selection.json`, `observations.json` and `preflight.json` in a caller-owned
directory, run the offline tool from the source checkout or evidence-full package:

```bash
python3 tools/verify_sidscope_native_observation.py \
  --input /tmp/my-native-observation --output /tmp/my-native-verified
```

This needs no model, key, checkpoint or network access. It checks native ranks,
real supplied labels, measured counts and full mapping joins. Output includes
explicit unavailable checks and a same-export recomputation comparison. The last
file, `complete.json`, is an observation receipt, not a canonical EvidenceBundle,
multi-run/seed comparison or independent execution/training certification.
Never upload or package the full normalized inputs or private runtime spec.

## Runtime workflows

### Canonical admission from observed native inputs (source / evidence-full)

The trusted external observer also supports `--metadata-only --output NEW.json`
to extract existing best-checkpoint progress without loading a model or using a key.
It requires the same explicit trusted runtime spec; this is not an untrusted
submission feature. No new training or inference is necessary for metadata.

From the source checkout or evidence-full package, with the normalized observation
directory and extracted metadata already available:

```bash
python3 tools/build_sidscope_native_submission.py \
  --input /tmp/my-native-observation --metadata /tmp/my-checkpoint-metadata.json \
  --output /tmp/my-native-canonical
python3 tools/build_sidscope_native_submission.py \
  --input /tmp/my-native-observation --metadata /tmp/my-checkpoint-metadata.json \
  --verify-submission /tmp/my-native-canonical/submission
```

No internal JSON or hashes need manual construction. The first command invokes
the SDK exporter, builds existing canonical identities and a submission, executes
diagnostic admission and a clearly labelled same-export comparison. The second
rebuilds from originals and rejects self-consistent rehashed forgeries. It does not
authenticate upstream training or turn the partial profile into a named adapter.
Keep original full data and private specs outside public submissions/releases.
See ADR-0020 for dataset/target-universe identity and checkpoint-progress semantics.

Active local version: `1.7.0.dev0`. Requires a regular runtime install. No core
edits, manual hashes, checkpoint loading or training assets are needed. Use
normalized item IDs; do not export raw user IDs or private paths. Each command
creates a new output and refuses to overwrite an existing one.

## 1. Is my mapping healthy?

Provide a CSV or integer-typed Parquet with one item per row and columns
`item_id,sid_level_0,sid_level_1,...`. Levels must be contiguous. Example:

```csv
item_id,sid_level_0,sid_level_1
1,0,1
2,0,1
3,1,0
```

```bash
python3 -m sidscope.workflows audit --input mapping.csv --output audit.json
```

The result reuses D1 utilization, D2 aliasing and D5 structural cost. The example
identifies the collision involving normalized items 1 and 2; no SID is repaired
automatically. D3, D4 and popularity weighting explicitly remain unavailable
without their additional inputs. Trusted local workflows have no application
row, file-byte, SID-width, cutoff or Parquet-expansion cap by default. They are
in-memory operations, not a promise of unlimited machine memory or streaming.

Python equivalent:

```python
from sidscope.workflows import audit
report = audit([{"item_id": 1, "sid": [0, 1]},
                {"item_id": 2, "sid": [0, 1]}])
# CSV, JSON (the same list format), and integer Parquet paths also work:
report = audit("mapping.csv")
```

For a caller-controlled resource budget, use
`LocalInputBudget(max_rows=1000000, max_input_bytes=268435456)` as the keyword
`budget=` on `audit`, `evaluate` or `compare`. CLI equivalents are
`--max-rows`, `--max-input-bytes`, and `--max-parquet-bytes` (metadata-reported
expansion). All default to no application cap; configured values must be positive
integers. Bytes apply to file intake, rows to each input table. These are caller
options, never instructions accepted from an input JSON document. Budgets do not
change metric definitions, report identity, or native generation semantics.

Strict UTF-8, JSON depth 64, duplicate-key/nonfinite rejection, unique item and
episode IDs, consistent SID widths and typed negative failures remain active.
This policy does not relax canonical/SDK loader defaults or untrusted submission
limits; a locally inspected large report is not thereby submission-admissible.

## 2. Where did this checkpoint get worse?

For the complete mapping-first join check, use `sidscope.mapping_check.preflight`:

```python
from sidscope.mapping_check import preflight
report = preflight(
    [{"item_id": 1, "sid": [0]}, {"item_id": 2, "sid": [1]}], dataset="my-split",
    catalog=[{"item_id": 1, "category": "a"}, {"item_id": 2, "category": "b"}],
    splits=[{"episode_id": "e", "split": "test", "target_item_id": 2, "history_item_ids": [1]}],
    targets=[{"episode_id": "e", "split": "test", "target_item_id": 2, "sid": [1]}],
    interactions=[{"normalized_user_id": 0, "item_id": i, "split": "train"} for i in (1, 2)])
assert report["checks"]["target_split"]["status"] == "pass"
```

CLI: `python3 -m sidscope.mapping_check --input preflight.json --output report.json`.
The JSON uses the same argument names; `mapping` may be a path relative to that
JSON. Optional CLI budgets match the workflow flags. Inputs contain normalized
IDs only; reports retain them, so redistribution still requires permission.
Use `train`, `valid`, `test` split labels. The catalog must equal the mapping;
targets may select a subset of split episodes. Missing dependencies remain
`unavailable`. D3/D4 use only train events, never a fallback to held-out rows.
Only supplied identities are checked; temporal split correctness is not inferred.

### Explicit producer orchestration

```bash
python3 -m sidscope.pipeline --producer my_installed_adapter:make_producer --spec run.json
```

The caller-trusted zero-argument factory returns an object with
`get_capabilities()` and `produce(contract_type, output_path)`, following the
existing AdapterHarness protocol. `run.json` contains paths `source`, `selection`,
`output` and optional `baseline`, relative to the spec. `source` is an existing
provenance submission, never an automatically supplied template. The producer
exports `trace-envelope`; the runner validates bindings, recomputes diagnostics,
builds a new EvidenceBundle submission and compares to a baseline. Without a
baseline it explicitly performs only self-recomputation. `complete.json` marks
completion; partial I/O output without it is not a successful run. Retry with a
new output path; do not overwrite prior evidence.

This is the tested generic live-producer entry. The separate observed-native
bridge has also connected and exercised the approved RPG Beauty and PSID Video
Games inputs through canonical identity, trace, diagnostic admission and bundle
verification; N03's technical bridge is verified. Those observations do not
authenticate training, and the public PSID sample still lacks target labels.
Do not invent missing facts or pass a historical fixture as real provenance.
F09/N01 remain pending until an independent SID algorithm engineer completes
this own-producer journey; maintainer automation cannot satisfy that condition.

Use your already generated ranked items. Targets are evaluator-side, never
generator input. Null slots remain in their original positions; no backfilling.
Every exported ranking must cover the requested cutoff, and duplicate resolved
items are rejected rather than silently deduplicated. Native traces remain
available through the existing family-specific export/verification paths.

```python
from sidscope.workflows import evaluate, compare
targets = [{"episode_id": "e1", "target_item_id": 2, "slice": "cold"}]
before = evaluate([{"episode_id": "e1", "ranked_items": [None, 2]}],
                  targets, dataset="my-frozen-split", cutoff=2)
after = evaluate([{"episode_id": "e1", "ranked_items": [None, 1]}],
                 targets, dataset="my-frozen-split", cutoff=2)
change = compare(before, after)
assert change["overall_delta"]["hit_at_cutoff"] == -1
assert change["regressed_episodes"] == ["e1"]
```

The corresponding CLI accepts an evaluation JSON containing `predictions`,
`targets`, `dataset`, and `cutoff`; these are user inputs, not internal contracts:

```bash
python3 -m sidscope.workflows evaluate --input evaluation.json --output evaluation-report.json
python3 -m sidscope.workflows compare --input comparison.json --output comparison-report.json
```

`comparison.json` contains `left` and `right` evaluation reports. Python and CLI
produce identical report content. Reports retain normalized inputs and content
hashes for deterministic recomputation. Only export/share them when those inputs
are permitted; this tool does not authorize data redistribution.

## 3. Is the comparison fair?

Comparison independently rebuilds both reports. Dataset name, exact target
selection (including slices), cutoff and metric policy must match. Rehashing
a changed metric does not pass. Changed cohort/slices fail with
`evaluation_protocol_mismatch`. A matching observed cohort returns `qualified`,
not a blanket fair-experiment certificate: a dataset name does not prove full
catalog identity or matched experimental controls. Use the existing strict
evidence-bundle comparison for identity-bound conformance comparisons.
Outputs identify regressed episodes and slices;
they do not claim causality, significance, native execution authenticity or
training reproducibility. Input evidence does not support those conclusions.

## Acceptance and recovery

Repeat the same inputs: report bytes are deterministic. Change an existing
output filename to keep both immutable results. A deliberately duplicated item
fails with `duplicate_mapping_item`; no data are silently repaired. Missing
target rows fail with `evaluation_population_mismatch`.

Automated consumer tests and installed-package replay are engineering acceptance,
not independent user adoption. A real user's trial must record the operation,
input scope, result and any manual intervention. No signature or maintainer
sign-off is requested or accepted as a substitute for running the workflow.

The separate local `tools/inspect_sidscope_native_export.py` consumer likewise
has no file-byte cap by default and offers `--max-input-bytes`. It reuses the
existing native verifiers without changing their semantics or frozen bytes.
Existing RPG/PSID export inspection is only part of F09/N03 acceptance, not the
complete external producer-to-bundle/comparison workflow.

For native ranked-slot projection in the evidence-full checkout/archive:

```bash
python3 tools/project_sidscope_native_export.py \
  examples/rpg_generator_trained_trace_real_smoke/rpg_beauty_trained_smoke_5.json \
  --output /tmp/sidscope-rpg-rank-projection.json
```

The output must not exist. PSID without `--selection` produces null metrics and
`target_labels_unavailable`, not a successful target evaluation. An optional
selection JSON has exactly `format` (`sidscope.native_selection.v1`),
`native_sha256`, `checkpoint_sha256`, `split_id`, `target_universe_sha256` and
`rows`. Each row contains `episode_id` (the native trace ID),
`target_normalized_item_id`, `slice` and nullable pseudonymous `cluster_id`.
Labels must come from the matched evaluator input, never from the predicted item.
PSID slices must equal native gap buckets. These are developmental tool formats,
not new stable SDK schemas; callers still require a producer-side label exporter
for the full no-handwritten-JSON workflow.

`compare_exports(left, right, left_selection=..., right_selection=...)` in that
tool recomputes both native inputs and rejects differing split bytes, catalog,
selection, cutoff, publication depth or pairing identities. Invalid and duplicate
PSID slots retain their original ranks; the first target occurrence determines
Hit/NDCG. Same-file comparison is labeled `same_export_recomputation`, not multiple
training seeds. Native execution, label authenticity, generation state and compute
remain unverified; this output is not a complete TraceEnvelope or EvidenceBundle.

Scale reproduction (CPU only; writes a new independent output directory):

```bash
python3 tools/benchmark_sidscope_local_workflows.py --output-dir /tmp/sidscope-scale-run
```

The 10k/100k/1M synthetic matrix is a correctness/resource smoke, not a native
workload SLO or a new input limit. Reports retain inputs: at 1M episodes the
observed report is about 266 MB and process peak RSS about 3.72 GiB, including
fixture generation and imports. Plan memory and output storage accordingly.
