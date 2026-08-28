# RPG dataset-neutral non-AR bridge fixture

This synthetic fixture exercises the v1 prepared-dataset and explicit episode-
selection contracts plus the v2 trained-trace verifier. All item identities are
normalized rows and every episode key is pseudonymous. The duplicate-selection
fixture must fail with `duplicate_selection_row`.

```bash
python3 tools/verify_rpg_trained_trace_bundle.py \
  examples/rpg_non_ar_bridge_fixture/trained_trace_v2.json \
  --prepared-dataset examples/rpg_non_ar_bridge_fixture/prepared_dataset.json \
  --episode-selection examples/rpg_non_ar_bridge_fixture/episode_selection.json \
  --handoff-output /tmp/rpg_downstream_handoff.json
```
