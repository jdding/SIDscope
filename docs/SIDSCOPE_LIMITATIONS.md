# SIDScope Limitations

Status: current TOIS manuscript and package limitation policy
Last updated: 2026-08-09

## Scope Limits

SIDScope is a resource for inspecting Semantic-ID artifacts. It does not train
new tokenizers, train generators, or optimize SID assignments. Claims should be
written as resource, diagnostic, reproducibility, and evaluation-interface
claims.

## Evidence Limits

- D1-D5 diagnostics describe artifact structure and mapping behavior.
- G2/G3/G4 support within-protocol calibration between D3 and
  prefix-structured candidate exposure under cluster-aware uncertainty.
- G9 strengthens that claim by evaluating candidate exposure and bounded
  fixed-reranker Recall@20/NDCG@20 on users disjoint from the users used to
  compute D3 co-occurrence alignment.
- G10 further tests non-prefix sampled-ranking candidates. The hard-negative
  popularity protocol supports a SID-prefix-affinity utility anchor, while the
  random-negative protocol is weak; report this as protocol-sensitive evidence,
  not a universal downstream-quality result.
- G11 bounds the Layer-C scoring-coupling concern with target-popularity
  residualization and co-occurrence/popularity-only ranker controls. It does not
  fully remove prefix scoring from the primary anchor.
- G11 replaces the SID-prefix-affinity scorer with a metadata-category scorer
  that does not use SID-prefix equality. The association is positive but weak
  (Recall@20/NDCG@20 rho `0.207`, confidence intervals cross zero), so G11 is a
  boundary result, not a claim that D3 predicts generic non-prefix ranking
  utility.
- G5-G7 support D7 schema, public-beam labeling, and bounded trace accounting;
  G20 observes trained trie-constrained ambiguity in two GRID/P5 folds and a
  DIGER portability sensitivity, with path-versus-item accounting. The folds
  are repeated observations, not an independent estimate of universal failure
  prevalence.
- G21 adds one released DACT TIGER/T5 checkpoint case. It validates D7
  portability and constrained-aware invalid-path accounting, not a universal
  failure rate or failure mechanism.
- G22 exercises D6 on one released DACT 0.6-to-0.7 refresh and follows the
  mapping repair into a preregistered three-seed generator handoff. It is a
  reproducible positive case, not universal repair effectiveness, causal
  diagnostic-to-quality evidence, or general D1-D5 predictivity.
- Current evidence does not support final trained downstream recommendation
  improvement, a generator failure mechanism, or D1-D5 trained-generator
  predictivity.

## Artifact Limits

- R138 is a local stress/reference artifact. It must not be described as
  faithful GRID coverage.
- Faithful GRID coverage currently comes from the R147-R151 P5 Beauty
  tokenizer-stage intake.
- CARD is no longer only a source-route audit: G15/R752 builds a complete
  12,101-item CARD RQ-VAE official-code-derived row over P5 Beauty and passes
  SIDScope normalization/preflight. The row must still be described with the
  local compatibility-shim boundary and must not be called an author-released
  CARD mapping or CARD's full image/card pipeline. The audited CARD clone has no
  local `LICENSE`/`COPYING`/`NOTICE` file, so raw artifact redistribution
  wording remains constrained.
- ReSOT is counted only after R759 as a released-archive text-index Instruments
  intake row. It uses completed item-to-code JSON files from the public
  `data.zip` archive and must not be described as a trained-generator result or
  as full coverage of every ReSOT branch. No GitHub license was detected in the
  audited source route, so reuse wording must remain conservative.
- DIGER is counted through official-code-derived Beauty (R763/R764) and Yelp
  (R828/R829) RQ-VAE rows. They are produced from public Hugging Face embeddings,
  interaction JSONL, and checkpoint files through the official
  `RQVAE.get_indices(...)` route. They must not be described as author-released item-to-SID tables, a
  trained-generator result, or full coverage of DIGER's differentiable
  assignment dynamics. No GitHub license was detected in the audited source
  route, so reuse wording must remain conservative. Yelp is the only
  non-Amazon route; it supports contract portability, not broad cross-ecosystem
  generalization or a causal domain comparison.

## Reproducibility Limits

The release separates three levels:

- `fully runnable`: bundled examples and package checks;
- `tracked snapshot`: compact paper-evidence values;
- `provenance only`: run records explaining how non-shipped artifacts were
  produced.

Raw datasets, AutoDL archives, checkpoints, large caches, and target-level
joined trace CSVs are intentionally omitted from the reviewer package.

## Venue And Prior-Version Limits

SIDInspector V0 was accepted at the CIKM 2026 Resources Track. SIDScope is now
developed as a disclosed TOIS substantial extension. The former independent
SIGIR resource branch is archived and is not an active submission route.

## Language To Avoid

Avoid language claiming that SIDScope:

- proves a causal generator failure mechanism;
- improves final recommender quality;
- universally predicts ranking quality across candidate protocols;
- fully resolves Layer-C scoring coupling in G10;
- turns G11 into a strong independent downstream-quality result;
- proposes a new tokenizer method;
- treats the R752 CARD row as an author-released CARD artifact;
- establishes universal superiority of any SID method;
- makes invalid/unresolved paths a constrained-decoding failure mode.
