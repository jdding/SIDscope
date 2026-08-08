# Conformance Failure Fixture

This fixture intentionally makes the second row's `sid` disagree with its
`sid_level_0` and `sid_level_1` values. C0, C2, C3, C4, and C5 remain valid;
C1 must fail. It demonstrates that paper promotion is blocked by normalized
mapping incoherence even when joins and bounded metrics can still execute.

```bash
PYTHONPATH=src python3 tools/check_adapter_conformance.py \
  --manifest examples/conformance_failure_fixture/manifest.json \
  --allow-fail
```
