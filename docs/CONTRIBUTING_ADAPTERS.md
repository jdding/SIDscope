# Contributing an Adapter and Evidence Submission

Status: public onboarding path for SIDScope 1.5

An adapter contribution translates an upstream method into SIDScope contracts.
It does not reimplement or approximate the method, alter training, fabricate
telemetry or require a project-specific change to the shared verifier.

## What the Adapter Package Owns

The adapter or external plugin supplies:

1. a capability descriptor and immutable source identity;
2. validated prepared-data and explicit episode-selection artifacts;
3. a native trace payload registered for the real method family;
4. a DatasetProfileDescriptor declaring evaluation and privacy boundaries;
5. a positive fixture and at least one typed expected failure;
6. a ProfileConformanceReport and independently verifiable EvidenceBundle;
7. an EvidenceSubmission index containing root-relative paths and exact hashes.

The package must not include raw private IDs, credentials, checkpoints, private
filesystem paths or upstream code/assets that cannot be redistributed.

## Onboarding Sequence

1. Install SIDScope core and keep the upstream runtime in its own environment.
2. Run adapter capability preflight and validate every canonical contract.
3. Export the native trace; do not map parallel, diffusion or overlay behavior
   onto synthetic autoregressive ancestry.
4. Generate the diagnostic and profile report under an active profile.
5. Build the immutable evidence bundle and root-relative submission index.
6. Run the independent submission checker in a clean CPU environment.
7. Verify every registered negative package fails with its expected typed code.

The reference external plugin and
`examples/conformance_ecosystem_fixture/submission/positive`
are the executable onboarding examples. They demonstrate that no
file under SIDScope core needs an adapter-specific edit.

The reference plugin can be replayed from a clean core install with the public
CLI only:

```bash
python3 -m pip install /path/to/sidscope-source
sidscope plugin list
python3 -m pip install examples/reference_adapter_plugin
sidscope plugin list
sidscope plugin preflight --name reference-parallel
```

The 1.6 adoption gate performs this sequence without core edits in an isolated CPU environment,
checks that the plugin is absent before its package is installed, and compares
the SIDScope core tree hash before and after onboarding.

## Review Checklist

- Source, data, SID/tokenizer, run, checkpoint and trace identities are
  hash-bound where applicable.
- Dataset, catalog, target universe, cutoff, publication depth, slices and
  privacy policy agree across descriptor, report and bundle.
- Target ranks are exact only inside the published frontier; deeper claims are
  right-censored.
- Status is derived from the selected profile rather than written into a
  registry or Markdown table.
- Positive and negative fixtures are deterministic and CPU-verifiable.
- License/reuse metadata is explicit and redistribution remains no broader than
  the recorded permission.

## Changes to the Trusted Core

A new adapter normally changes only its own package, examples and evidence. A
core change is justified only when the method exposes a genuinely missing
family-semantic contract. Such a change needs an architecture/profile review,
versioned schema, migration policy, positive and negative fixtures, and a
rollback that preserves earlier reports and bundles.
