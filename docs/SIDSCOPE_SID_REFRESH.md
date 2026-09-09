# SID refresh lifecycle diagnostics

Status: opt-in local workflow in `1.7.0.dev0`; candidate input to SIDScope 2.0.
This workflow does not modify SIDs, run a model or establish a causal effect.

## Purpose

`python -m sidscope.refresh` compares two caller-supplied mapping snapshots and
separates literal code churn from changes to item grouping. It reports common,
added and removed items, split/merge structure, bounded pseudonymous examples
with JSON pointers, and an explicit interpretation limit. Optional evaluation
bindings associate two recomputed ranked-evaluation reports with the snapshots;
the resulting metric deltas are observations, not proof that the refresh caused
them.

## Snapshot contract

Each JSON snapshot has exactly these fields:

```json
{
  "dataset": "beauty",
  "item_namespace": "normalized-items-v1",
  "sid_namespace": "rqvae-refresh-a",
  "semantics": "ordered_prefix",
  "mapping": [{"item_id": 0, "sid": [12, 7, 91]}]
}
```

`dataset`, `item_namespace`, and `semantics` must match across snapshots. Item
IDs and SID tokens are non-negative integers. Duplicate items, malformed rows,
inconsistent widths and implicit namespace alignment fail closed.

Choose semantics from:

- `ordered_prefix`: autoregressive/hierarchical positions; prefix and full-code
  partitions are reported.
- `parallel_positions`: independent position-specific codebooks; only the full
  vector is structural and repeated integer values across positions are valid.
- `unordered_set`: membership is structural; token order is representation only
  and duplicate members are invalid.

The caller must choose semantics from the producer contract. SIDScope does not
infer it from token values.

## CLI

```bash
python3 -m sidscope.refresh compare \
  --old old-snapshot.json \
  --new new-snapshot.json \
  --output refresh-review
```

The output directory is new and contains `report.json`, `report.md`, and a final
`complete.json` receipt. Existing paths are never overwritten. `--max-rows` and
`--max-input-bytes` are optional local resource policies; omitted means no
application-imposed local cap. JSON depth, duplicate-key and non-finite-number
checks remain active.

To bind a recomputed `sidscope.workflows.evaluate` report without hand-writing a
snapshot hash:

```bash
python3 -m sidscope.refresh bind \
  --snapshot old-snapshot.json \
  --evaluation old-evaluation.json \
  --output old-binding.json
```

Pass `{"old": ..., "new": ...}` bindings to `compare` with `--downstream`.
The datasets, catalog membership, protocol, cohort, cutoff and publication depth
must agree; stale or tampered bindings are rejected.

## Evidence and limits

The technical gate includes typed negative tests, an independent small-case
partition oracle, installed-package execution, and same-input controls on the
actual returned RPG Beauty (12,101 items, parallel positions) and PSID Video
Games (17,396 items, ordered prefix) mapping shapes. Same-input controls prove a
zero-change invariant only; they are not a before/after refresh experiment. No
checkpoint, training history, model authenticity, geometry, unseen-item
alignment, author intent or causal downstream effect is verified.
