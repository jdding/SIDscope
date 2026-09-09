# Paired regression and offline review — local 1.7 development API

## Compare actual matched runs

Prepare ordinary normalized predictions/targets with `sidscope.workflows.evaluate`.
Keep each actual run separate. The same frozen target rows bind cohort and slices.
An input JSON for `python -m sidscope.regression --input runs.json --output diff.json`
contains:

```json
{
  "left": [{"run_id": "baseline-seed-1", "pair_id": "seed-1", "seed": 1,
    "controls": {"dataset_snapshot": "your-frozen-snapshot", "recipe": "matched-recipe"},
    "report": "baseline-seed-1.json"}],
  "right": [{"run_id": "candidate-seed-1", "pair_id": "seed-1", "seed": 1,
    "controls": {"dataset_snapshot": "your-frozen-snapshot", "recipe": "matched-recipe"},
    "report": "candidate-seed-1.json"}],
  "clusters": {"episode-a": "pseudonymous-user-a", "episode-b": "pseudonymous-user-b"},
  "degradation_budget": {"hit_at_cutoff": 0.01, "ndcg_at_cutoff": 0.01},
  "replicates": 2000, "confidence": 0.95, "random_seed": 0
}
```

Replace rows with actual reports and a complete cluster map. This deliberately
shows one pair: the result has **insufficient_paired_runs**, no interval and no
budget PASS. Add actual independently executed matched seeds, not duplicate
reports with new names. Run identities, controls and cluster labels are your
declarations; their hashes do not authenticate them. Shared clusters are resampled
together across all runs. Relative effect is unavailable at zero baseline.
Intervals are pointwise and approximate; inspect the per-slice sample counts.

Python: `from sidscope.regression import compare_runs`; pass report dictionaries
instead of paths. All inputs are recomputed, including supplied metric values.
The result includes source report/control/cluster bindings, absolute effects,
uncertainty, budget decisions and limitations. A computed report is not a global
statistical PASS or permission to claim method superiority.

## Produce an actionable review

```sh
python -m sidscope.diagnostic_review --candidate candidate.json \
  --baseline baseline.json --output /tmp/my-new-review
```

The output directory must not exist. Open `index.html` locally; `review.json`
contains machine-readable observations and `complete.json` binds completion.
No server is needed. Without a baseline, omit `--baseline`; differences remain
unavailable. Evidence pointers refer to the original candidate/baseline evaluation
reports identified by content hash. Keep those original reports separately.
`--max-examples` bounds examples per finding; totals and metrics remain complete.

Python: `diagnose(candidate, baseline=baseline, regression_spec=spec)` recomputes
optional uncertainty from embedded report inputs, checks arm membership and binds
it to the review. `write_review(output, candidate, ...)` saves JSON and HTML.
Never attach an unverified precomputed comparison as statistical evidence.

## One command for the approved native observations

From a conformance/evidence-full source package:

```sh
python tools/run_sidscope_observed_review.py --input OBSERVATION_DIRECTORY \
  --metadata CHECKPOINT_METADATA_JSON --output /tmp/my-new-observed-review
```

Inputs are the existing `native.json`, `preflight.json`, `selection.json` and
`observations.json`, plus checkpoint metadata from the documented observer.
No caller-written canonical JSON/hash is required. Outputs include canonical
submission, `evaluation.json`, local `clusters.json`, static review and a final
receipt. Cluster identities and full normalized observation inputs stay local;
share the bounded review or validated submission, not the whole work directory.
This command consumes observations and never invokes a model or opens identity keys.
It does not supply a missing second run. Duplicate native slots are not silently
removed; the optional ranked review fails with an explicit unsupported code.

## Measure the exact workload, without extrapolation

```sh
python tools/benchmark_sidscope_observed_review.py --input OBSERVATION_DIRECTORY \
  --metadata CHECKPOINT_METADATA_JSON --output /tmp/my-new-review-benchmark \
  --repeats 3 --timeout 60 --rss-mib 2048
```

These are execution guards, not production SLOs or product input restrictions.
Fresh-process peak RSS includes imports and full joins; existing native NFE is
reported separately from current CPU postprocessing. Compare only the recorded
machine, inputs and shapes. Five trace episodes do not establish large-trace scale.
Interrupted/failed outputs have no top-level completion marker; preserve them and
retry under a new path. Do not modify frozen originals to make acceptance pass.

## Independent actual use (N01/F09)

A non-implementing engineer should install the artifact, use their authorized
observation directory, execute the documented command, inspect a finding through
its source pointer and interpret the explicit missing multi-run evidence. Record
commands, outputs and usability defects; fix defects and rerun affected steps.
No signature policy is required. Developer automation is not independent use.
