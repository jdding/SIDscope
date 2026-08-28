# Real PSID/Latte trained-trace smoke

These two bundles are deidentified, checkpoint-backed five-episode smoke
exports from the pinned Latte source revision. Each bundle selects one episode
from each frozen natural gap bucket and passes
`sidscope.latte_psid_trained_trace_bundle.v2` on CPU.

- `psid_amazon_vg_1_per_bucket_s2024.json` preserves all 250 returned beams
  and the raw first-10 evaluation slots without backfilling.
- `latte_amazon_vg_1_per_bucket_s2024.json` preserves both decode attempts for
  all five retry episodes, 750 returned beams, and dense item ranks after
  latent-path aggregation.

The bundles contain normalized item identities only. Raw user IDs, source item
IDs, labels, checkpoint paths, and private filesystem paths are absent and are
rejected by the verifier. The corresponding 250-episode diagnostic bundles
remain external; their input/output hashes, counts, verifier results, and
expected-failure hashes are frozen in
`docs/reproducibility/latte_psid_trained_trace_evidence.json`.

Run:

```bash
PYTHONPATH=src python3 tools/verify_latte_psid_trained_trace_bundle.py \
  --bundle examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json

PYTHONPATH=src python3 tools/verify_latte_psid_trained_trace_bundle.py \
  --bundle examples/latte_psid_trained_trace_real_smoke/latte_amazon_vg_1_per_bucket_s2024.json
```

These are adapter-conformance artifacts, not full-population effectiveness
estimates and not evidence added to the frozen TOIS submission.
