# DiffGRM masked-diffusion fixture

This public-safe CPU fixture exercises the revision-bound DiffGRM adapter
without upstream code, data, embeddings, or weights. It binds a prepared-data
contract, an explicit ordered episode selection, adaptive all-mask decoding,
parent-beam ancestry, per-position token top-k values, retained and pruned
expansions, raw pre-filter beams, collision-preserving exact resolution, and a
ranked-item export whose evaluation cutoff remains 10.

The fixture is not a trained result. Its one episode is intentionally smaller
than the five-bucket checkpoint smoke and 250-episode diagnostic required for
G1--G5 closure.

Run:

```bash
python3 tools/verify_diffgrm_adapter.py
python3 tools/verify_diffgrm_trained_trace_bundle.py \
  --prepared examples/diffgrm_masked_diffusion_fixture/prepared_dataset.json \
  --selection examples/diffgrm_masked_diffusion_fixture/episode_selection.json \
  --bundle examples/diffgrm_masked_diffusion_fixture/trained_trace_fixture.json
```

The second command demonstrates the external three-file CLI without replaying
the source/license audit. This fixture remains schema v1 and is reported as a
legacy CPU contract fixture. Real checkpoint evidence migrates to
`sidscope.diffgrm_masked_trace_bundle.v2` with source-manifest, canonical
configuration, checkpoint, training-manifest, and SID-cache hashes.

`expected_failures.json` applies deterministic mutations to the positive
bundle and confirms fail-closed rejection of incompatible SID identity,
missing/duplicate/out-of-split/mismatched/unreachable selection,
autoregressive fields, broken ancestry, invalid raw-tuple success, and an
unsupported exact-rank claim.
