# Evidence Bundles, Object Storage, Registry and Comparison

Status: SIDScope `1.4.0.dev0` contract

## Responsibility

SIDScope owns the evidence record after an adapter has produced canonical
contracts and native traces. It does not own the upstream method, training
loop, dataset license, or restricted checkpoint. The evidence subsystem turns
validated outputs into an immutable, queryable, correction-safe record.

```text
canonical artifacts and native trace
  -> EvidenceBundle admission
  -> immutable SHA-256 object layout (authority)
  -> SQLite projection (disposable index)
  -> static export and compatibility-aware comparison
```

`EvidenceIndex v1` remains the deterministic dependency inventory introduced
in 1.2. `EvidenceBundle v1` adds packaging, result-card, object-storage,
supersession, and registry semantics. Neither format is silently converted into
the other.

## EvidenceBundle v1

The schema ID is `sidscope.evidence_bundle.v1`, revision `1.0.0`. A bundle
contains:

- producer, profile, adapter, and native method-family identity;
- dataset and target-universe hashes, evaluation cutoff, publication depth,
  and rank semantics used for compatibility decisions;
- artifact records and an acyclic source-to-conformance provenance graph;
- overall and slice metrics, typed failure counts, compute, and exact versus
  right-censored rank observations;
- zero or more prior bundle hashes in `supersedes`;
- explicit false-valued privacy declarations; and
- a canonical, non-self-referential `content_sha256`.

Each artifact keeps its canonical `content_sha256` separate from the
`object_sha256` of the exact stored or externally bound bytes. This preserves
the identity convention of canonical contracts without pretending that their
self-declaring JSON file bytes have the same digest. Artifact availability is
either `embedded_public` or `hash_reference_only`. The latter is the required representation for private
data, checkpoints, embeddings, or other restricted inputs. Verification uses
declared identities, hashes, sizes, counts, and derived evidence; it does not
require the restricted bytes.

## Object Layout and Admission

```text
<store>/
  bundles/sha256/ab/abcdef....json
  objects/sha256/cd/cdef....
  quarantine/...
  registry.sqlite3                 # derived; safe to delete
```

Admission validates the bundle hash, exact schema, provenance DAG, result-card
semantics, privacy declarations, forbidden content, and every supplied public
artifact against its exact-byte `object_sha256`. Writes use a temporary sibling
followed by `os.replace`. Re-admitting
identical content is idempotent; a conflicting object at the same identity
fails closed.

No absolute local path is stored. The two-character prefix is only a directory
shard derived from the hash and has no semantic meaning.

## Registry Semantics

The SQLite registry is a projection, not evidence authority. It supports add,
list, show, compare, supersede, import, export, and rebuild. A deterministic
static export contains sorted bundle, artifact, metric, and supersession rows
without database-specific IDs, timestamps, or paths. Deleting the database and
rebuilding from the same admitted bundle set must reproduce the same export.

Corrections never mutate an old bundle. The corrected bundle names the prior
hash in `supersedes`; the registry checks that the prior bundle exists and that
supersession remains acyclic. Quarantine can remove an object from ordinary
query results while preserving its bytes and audit identity.

## Comparison Contract

Comparison first checks profile ID/revision, dataset identity, target universe,
evaluation cutoff, publication depth, and rank semantics. Any mismatch yields a
typed `incompatible` result and no metric delta. This prevents configuration or
observation-depth changes from being presented as method improvements.

Compatible bundles receive deterministic deltas for overall and slice metrics,
typed failures, and compute. Exact ranks are accepted only when the bundle
declares exact-with-censoring semantics and the rank is within its publication
depth. A target outside the observed frontier remains right-censored; the
comparison never invents an exact rank.

## Operational Recovery

If SQLite is deleted or corrupt, remove it and run registry rebuild against the
object directory. If a bundle is wrong, quarantine it, build a corrected bundle,
and admit the correction with a supersession edge. Never edit an admitted JSON
object or move a public tag to disguise a correction.

The complete 1.4 acceptance command is:

```bash
python3 tools/verify_sidscope_1_4_evidence_system.py
```

It is CPU-only and uses temporary local storage.
