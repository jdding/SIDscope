# SIDScope deferred platform support

Decision: ADR-0027, project owner, 2026-10-08.

Schedule only after relevant user feedback and a new support decision.

| Backlog | State | Priority | Re-entry trigger | Acceptance |
| --- | --- | --- | --- | --- |
| Linux CPython 3.9–3.12 installation and four-cell verification | Deferred; unsupported in 2.0; no release prerequisite or scheduled execution | Feedback-driven | Concrete Linux user demand followed by an explicit support-scope decision | Real clean-candidate clone; target-runtime dependencies; wheel/sdist and installed consumers; full suite and required verifiers per declared cell; valid same-source receipts and a new gate catalog |

Historical Linux passes and current preparation regressions remain historical
evidence. They do not establish support for the 2.0 candidate. Reuse
tools/run_sidscope_linux_matrix_cell.sh and docs/SIDSCOPE_LINUX_MATRIX_RUNBOOK.md
when this backlog is activated; record actual OS, architecture, interpreter,
source identity and limitations. Do not infer support from requires-python.

Current 2.0 acceptance covers macOS arm64 / CPython 3.9.6. Windows support is
also unverified and outside the current acceptance promise. N09/N10 remain
unscheduled as previously decided.
