# ADR-0027: Defer Linux support and its matrix beyond 2.0

Status: accepted, project-owner decision, 2026-10-08.

## Decision

Linux CPython 3.9, 3.10, 3.11 and 3.12 support is outside the 2.0 release
scope. Its matrix is removed from required certification, RC and delivery
gates and moved to the feedback-driven backlog. Linux is unsupported in 2.0,
not verified or declared passing. Current executed acceptance covers macOS
arm64 / CPython 3.9.6; requires-python >=3.9 is an installation constraint,
not acceptance evidence for every OS or Python version.

The frozen catalog v1 and historical Linux/candidate evidence remain intact.
Catalog v2 lists ten required gates and linux_matrix as deferred. Delivery
summary v2 binds that scope, the catalog digest and every required receipt.
The validator rejects removed technical gates, altered platform declarations,
missing receipts, unapproved skips and fabricated Linux PASS entries.
Producer chains, recomputation, installation, resource safety and performance
stay required. ADR-0025's independent-adoption exclusion remains unchanged.

## Backlog and re-entry

See docs/SIDSCOPE_DEFERRED_PLATFORM_SUPPORT.md. Keep the existing Linux runner,
assembler, shared validators and negative tests for later reuse. Re-entry
requires relevant user feedback, an explicit support decision, and real
same-source Linux installation, full-suite and verifier results. No Linux
execution or container recovery is scheduled for this 2.0 closeout.

## Consequences and Rollback

Supersedes ADR-0024/0026 only for the Linux release prerequisite. No runtime
schema, SDK or algorithm semantics change. The product stays 1.7.0.dev0 until
the separately authorized RC transition. Publication remains separately
authorized. A new clean candidate must regenerate all delivery evidence;
old records must never be relabeled to the new policy.

Rollback requires a new versioned catalog restoring the Linux gate plus
actual Linux receipts. Deleting the deferred declaration or editing catalog
v1 does not restore support.
