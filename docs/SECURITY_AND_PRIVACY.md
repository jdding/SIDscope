# Security and Privacy for Evidence Submissions

Status: active policy for SIDScope 1.5

SIDScope verifies declared evidence. It does not execute code, commands,
plugins, checkpoints or training payloads contained in a submission.

## Threat Boundary

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
