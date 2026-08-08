# SIDScope Usage Demo

Status: G14 resource-use walkthrough
Last updated: 2026-06-20

This demo shows the intended resource use pattern: a researcher inspects
compact SID artifact diagnostics, separates promotable artifacts from
stress/control rows, and records what should or should not move to more
expensive downstream training. It is a reproducible usage demonstration,
not a claim that SIDScope predicts final recommender quality.

## Inputs

- `docs/reproducibility/table2_musical_diagnostic.csv`
- `docs/reproducibility/official_adapter_metrics_snapshot.csv`
- `docs/reproducibility/table1_evidence_catalog.csv`
- `docs/reproducibility/extension_checks_snapshot.csv`

## Walkthrough Outcome

- Artifact rows inspected: `11`
- Promote candidates: LETTER, ReSID
- Blocked or stress-only rows: GRID-style cap, GRID-style ft, Hash-collide
- Manual-review rows: RQ-min ref

## Decision Table

| Artifact | Decision | Question Answered | Answer | Risk Flags |
| --- | --- | --- | --- | --- |
| Cat-prefix | diagnostic_control_not_method_coverage | Should this control row be promoted as method coverage? | No. Use it to interpret diagnostic behavior, not as a named artifact candidate. | usable_prefix_exposure_proxy |
| Pop-balanced | diagnostic_control_not_method_coverage | Should this control row be promoted as method coverage? | No. Use it to interpret diagnostic behavior, not as a named artifact candidate. | usable_prefix_exposure_proxy |
| RQ-min ref | manual_review_before_claim | Can this artifact support a paper-facing claim without inspection? | Not yet. Inspect provenance, exposure, and addressability before promotion. | moderate_full_code_aliasing;weak_prefix_exposure_proxy |
| LETTER | candidate_for_training_or_comparison | Is this a reasonable artifact to promote to training/comparison? | Yes, with normal provenance checks and task-specific validation. | usable_prefix_exposure_proxy |
| ReSID | candidate_for_training_or_comparison | Is this a reasonable artifact to promote to training/comparison? | Yes, with normal provenance checks and task-specific validation. | usable_prefix_exposure_proxy |
| DIGER RQ-VAE | intake_pass_monitor_exposure | Can this artifact be kept in the matrix? | Yes, but monitor candidate-exposure and refresh-specific diagnostics. | weak_prefix_exposure_proxy |
| LC-Rec | intake_pass_monitor_exposure | Can this artifact be kept in the matrix? | Yes, but monitor candidate-exposure and refresh-specific diagnostics. | weak_prefix_exposure_proxy |
| ReSOT text-index | intake_pass_monitor_exposure | Can this artifact be kept in the matrix? | Yes, but monitor candidate-exposure and refresh-specific diagnostics. | weak_prefix_exposure_proxy |
| GRID-style cap | stress_only_exclude_from_named_coverage | Should this artifact be used as a named method row? | No. Keep as a stress/control row and do not train expensive generators on it. | high_full_code_aliasing;low_addressability;tail_addressability_loss;weak_prefix_exposure_proxy |
| GRID-style ft | stress_only_exclude_from_named_coverage | Should this artifact be used as a named method row? | No. Keep as a stress/control row and do not train expensive generators on it. | severe_full_code_aliasing;low_addressability;tail_addressability_loss;weak_prefix_exposure_proxy |
| Hash-collide | stress_only_exclude_from_named_coverage | Should this artifact be used as a named method row? | No. Keep as a stress/control row and do not train expensive generators on it. | severe_full_code_aliasing;low_addressability;tail_addressability_loss;weak_prefix_exposure_proxy |

## Boundary

The demo uses deterministic thresholds only to illustrate resource
operation. The thresholds are not universal acceptance rules, and the
output should be read as a reproducible triage walkthrough rather than
a downstream performance result.

Regenerate with:

```bash
python3 tools/run_sidscope_usage_demo.py
```
