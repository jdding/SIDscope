# Security and Privacy for Evidence Submissions

Status: active local 1.7 policy; the original submission protocol remains versioned independently.

SIDScope verifies declared evidence. It does not execute code, commands,
plugins, checkpoints or training payloads contained in a submission.

## Threat Boundary

`sidscope.pipeline --producer` explicitly executes caller-selected local code,
like the existing SDK; it is not a sandbox. Producer code cannot be selected by
submission or run-spec fields. Targets stay evaluator-side; the orchestrator
does not pass labels into the producer. Mapping preflight reports contain supplied
normalized inputs and must not be redistributed without input permission.

Canonical/SDK/native JSON loaders retain their default 8 MiB byte budget.
The untrusted submission package additionally caps 256 artifacts and 64 MiB total
before admission. Trusted local `sidscope.workflows` and the active RPG/PSID
export inspection entry instead accept caller-selected optional byte budgets;
their default has no application byte or row cap. Local workflows can also set
row and Parquet metadata-expansion budgets. These options are not read from the
input document and cannot change submission policy. All these JSON paths retain
depth 64, strict UTF-8, unique object keys and finite-number checks.
The historical family-specific verifier scripts have hash-pinned replay bytes;
they are not hardened arbitrary-input entry points and are not rewritten.
Use the bounded public native-payload loaders for untrusted intake; use the
supported export inspector for caller-owned local exports. Bundled schema
registries are trusted package resources protected
by the release content receipt, not arbitrary user input. In-memory dictionaries
passed directly to semantic validators are caller-owned; file budgets are not
a promise of sandboxing Python plugins or unrestricted legacy training tools.

Local workflows remain in-memory and can exhaust available RAM if the caller
does not budget inputs. A budget is not a process sandbox or a preemptive RAM
limit; Parquet metadata expansion is not an RSS prediction. Structural validity
checks remain mandatory; there is no arbitrary fixed SID-width limit. Workflows
do not deserialize checkpoint/pickle payloads. Actual missing native ranking,
generation or catalog facts remain unverified; resolution-array order is not
ranking evidence. Decoder overlays retain their explicit fused ranking.

A submission is untrusted input. The checker must reject:

- absolute paths, path traversal, symlink escape and members outside the
  submission root;
- content-hash mismatch, duplicate roles or undeclared files required by a
  profile;
- credentials, tokens, private keys, local private paths and checkpoint bytes;
- raw user or source item identities where the descriptor promises
  pseudonymous data;
- unsupported exact-rank claims beyond the published frontier;
- profile, dataset, catalog, target-universe, cutoff, publication-depth or
  slice incompatibility.

The checker reads bounded JSON artifacts and exact-byte hashes. It never
imports the submitted adapter, follows a packaged command, downloads an asset
or contacts an upstream service.

## Privacy Contract

DatasetProfileDescriptor declares the identity policy, allowed evaluator-side
slices, restricted-asset representation and whether raw identities are absent.
Private data, checkpoints, caches and full traces remain with the producer;
public evidence uses hashes, counts, metrics and deidentified bounded rows.

Dormancy buckets and target labels are evaluator-side joins. A profile must not
permit them to become generator input merely because they appear in a report.

## Reuse and Redistribution

License state, execution authorization and redistribution permission are
recorded separately. A missing upstream LICENSE is retained as a marker and
does not by itself block technical development or evidence verification. It
does block claims that SIDScope may redistribute upstream code or assets unless
another explicit permission covers that action.

## Failure Handling

A failed submission is not partially admitted. Preserve its failure report,
fix the producer output and create a new content hash. If an admitted object is
later found unsafe, quarantine it in the derived registry and publish a
superseding bundle; never rewrite the original object.

Security-sensitive reports should use the repository's private maintainer
contact or private vulnerability-reporting channel rather than a public issue
that exposes credentials, identities or restricted artifact locations.
