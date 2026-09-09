# ADR-0019: Local producer orchestration and mapping preflight

Status: accepted implementation boundaries, 2026-09-08. Local 1.7.0.dev0 only.
Accountable: jdding, with existing SDK/Evidence/Diagnostics ownership roles.

## Decision and alternatives

Reuse the modular monolith, Python AdapterHarness, canonical validators,
recomputed submission builder and evidence comparison. Add `sidscope.pipeline`
as a synchronous caller-owned orchestration module, and `sidscope.mapping_check`
as a local preflight over existing pandas D1--D5 kernels. No service, database,
second metric framework or changed native generation algorithm is needed.

A run spec names source provenance, selection, output and optional baseline.
Executable producer code is selected separately by the caller (`--producer`),
never by a submission/run-spec field. The producer must export a canonical trace
through the existing SDK; it is NOT satisfied by silently copying a legacy export.
Run/checkpoint/family/subject bindings are checked before recomputed admission.
Targets are evaluator-side inputs, not arguments supplied to the producer.
Declared provenance is preserved, not independently authenticated. New canonical
native exporters and real material bindings are still needed for RPG/PSID F09/N03.

Rejected: use an unrelated fixture as default source provenance, infer unknown
catalog/generation facts as booleans, fabricate PSID target labels, or promote a
generic orchestrator test to two real producer integrations. Current real compact
exports do not establish all inputs needed for that acceptance. F09/N03 stay partial.

## Mapping contract

Catalog, split, target/SID and interaction joins validate normalized IDs before
metric execution. A supplied catalog must match the mapping exactly. Selection
may be an explicit subset of supplied split episodes, but split/item/SID must
agree. Duplicates and unknown references are typed failures, never silent repair.
Missing optional inputs are listed as unavailable, not reported as passed checks.

Only explicit `train` interactions enter collaborative D3, weighted D2 and D4.
The old kernel falls back to all events when train is empty; the wrapper must
never invoke it with held-out-only interactions. Existing D3 sampling parameters
remain disclosed in the report (top K 20, max pair events 2M, max user items 200),
not a new ingestion limit. Category purity is conditional; unavailable statistics
use null/absent fields, never a made-up zero. No temporal authenticity is inferred.

## Failure, recovery, compatibility and acceptance

Keep existing audit/evaluate/compare report identities and curated 39-symbol
facade unchanged. New optional modules use existing exception and content-hash
conventions. Local resource budgets follow ADR-0018. No version bump or new
public native schema is necessary.

Validate before creating final pipeline output; write `complete.json` last.
An interrupted I/O operation may leave an incomplete directory; preserve it for
inspection and retry with a new output directory. Existing paths are not replaced.
Rollback consists of not invoking the new optional modules; previous workflows
and immutable bundles remain unchanged. No runtime topology migration occurs.

Acceptance: CLI/API parity, deterministic ordering, explicit budget failures,
catalog/split/target/SID corruptions, held-out contamination rejection, real bounded
RPG mapping with missing-target rejection, actual producer-call count in synthetic
SDK tests, provenance/baseline mismatch rejection and installed wheel/sdist replay.
Synthetic orchestration and installed tests do not establish native execution,
training authenticity or independent user use. Real two-family completion remains
a separate necessary gate. N05/N04/N08 development is deferred in this batch.

## Follow-up: native rank projection, not invented canonical observations

The approved next sequence is real RPG Beauty and PSID Video Games integration
with mapping preflight, then N05 comparison, N04 reports and N08 scale acceptance.
Each frozen dataset has its own protocol; no cross-dataset method ranking is made.
`tools/project_sidscope_native_export.py` is an evidence-full, pure-data tool:
it calls the unchanged native verifiers and existing Hit/NDCG kernel, retains
invalid and duplicate slots, and binds optional labels to exact native bytes,
checkpoint, split and target universe. Cluster identities are retained in the
selection identity for later pairing; absent cluster IDs stay unavailable.

Rejected: fill unavailable latency/NFE or target-generation flags to satisfy
TraceEnvelope v1, borrow fixture provenance, or treat this rank projection as a
complete EvidenceBundle submission. The local projection/selection `format`
markers are developmental tool documents, not additions to the stable public
schema registry or SDK. Existing contracts, native exporters and verifiers remain
unchanged. Same-file comparison explicitly means recomputation, not independent
run/seed evidence. Missing target labels disable metric comparison.

The initial external execution step was rejected by safety review. The user then
explicitly authorized scratch source/cache copies, in-place identity-key use and
five-episode CPU inference for each frozen checkpoint. Both observations now
completed without training, GPU use or original asset writes. Keys never leave
the runtime. Failed attempts remain distinct evidence, not overwritten successes.

The optional trusted-runtime observer is not a submission loader. Its explicit
caller-supplied spec selects executable code; no public bundle may invoke it.
The separate offline verifier imports no model and executes no external command.
It joins exact native bytes, selected labels, measurements and full mapping inputs.
Dataset display names are explicitly converted to non-path local IDs; originals
remain recorded. The receipt is a developmental tool format, not a public schema
or EvidenceBundle. Measurement consistency is not independent execution or training
authentication. Full normalized inputs/specs remain ignored and never ship.
F09/N03 still require the canonical integration and actual user workflow acceptance.
