# ADR-0015: Separate the Public Maintenance, Local 2.0 Development, and TOIS Lines

- Status: Accepted
- Date: 2026-08-31
- Scope: SIDScope repository, release, and publication governance
- Owner: SIDScope maintainers

## Context

SIDScope now has three related but distinct change surfaces: the public GitHub
repository, the local system-engineering line evolving toward 2.0, and the
submitted TOIS manuscript/package. Treating one version label as the authority
for all three would either publish an immature 2.0 contract, freeze software
maintenance unnecessarily, or imply that every future TOIS revision must use
the historical `v1.0.2` software snapshot.

The current facts are:

- public GitHub `main` is the 1.1.x maintenance line;
- the latest public formal tag is `v1.1.0` and `main` currently identifies as
  `1.1.1.dev0`;
- post-1.1 architecture development is committed locally in the dedicated
  `SIDScope-v2` worktree and is not authorized for push;
- the submitted TOIS repository is frozen by its own branch, commit, tag, and
  submission package, not by a permanent product-version rule.

## Decision drivers

1. Public users should see a coherent maintained 1.1.x surface.
2. The 2.0 compatibility promise must not be published before its local
   development and certification are complete.
3. The submitted TOIS state must remain reproducible and untouched.
4. A later editorial revision must be able to select a compatible reviewed 1.x
   software snapshot without inheriting local 2.x development automatically.
5. Historical release records and tags must remain immutable.

## Options considered

| Option | Result |
|---|---|
| Push the local pre-2.0 branch to GitHub now | Rejected: exposes an unfinished compatibility line and blurs the supported public surface. |
| Freeze all TOIS work permanently to `v1.0.2` | Rejected: preserves the initial snapshot but incorrectly constrains a future authorized revision. |
| Keep GitHub on 1.1.x, keep 2.0 development local, and version TOIS revisions by their exact frozen package | Accepted: preserves all three authorities with explicit promotion gates. |

## Decision

- `sidscope/main` remains the public 1.1.x maintenance authority until the
  user explicitly authorizes a different public line.
- `codex/sidscope-v2` in the dedicated local `SIDScope-v2` worktree remains the
  only 1.2--2.0 development authority. Local commits do not imply publication,
  tag creation, or push authorization.
- The TOIS submission authority is its exact frozen repository branch, commit,
  tag, and archived package. `v1.0.2` remains an immutable historical release
  associated with the submitted snapshot, but it is not a permanent rule for
  all future TOIS revisions.
- A future TOIS revision may adopt an explicitly reviewed, claim-compatible 1.x
  software snapshot. It must never absorb the local 2.x development line by
  default.
- Every future authorized TOIS revision must record that selected software ref
  explicitly rather than inferring it from the newest local or public version.
- No historical changelog entry, tag, release packet, evidence object, or
  submitted manuscript is rewritten to reflect this prospective policy.

## Compatibility and failure behavior

- Public 1.1.x maintenance must retain its existing package and evidence
  compatibility rules.
- Local 2.0 development may change only under the documented pre-2.0 migration
  and certification gates.
- A proposed TOIS revision fails closed until its exact software commit,
  manuscript commit, artifact hashes, claim delta, and verifier results are
  recorded together.
- A local development closure is not a public release and is not TOIS revision
  authorization.

## Rollout and validation

1. Record this boundary in README, versioning, compatibility, maintenance,
   architecture, roadmap, release-checklist, release-packet, and handoff docs.
2. Verify GitHub and local branch identities before every release claim.
3. Keep tag/push steps behind explicit user authorization.
4. For an editorial revision, create a separate revision plan and validate the
   selected 1.x software/package against the manuscript claims before copying
   or rebuilding any submission material.

Success means documentation never equates a local commit with GitHub
publication, never presents `v1.0.2` as the only possible future TOIS software
version, and never routes 2.x changes into the frozen submission implicitly.

## Rollback

This is a governance boundary with no data migration. A future public-line or
TOIS-version decision requires a superseding ADR and explicit release or
revision authorization. Historical refs remain unchanged.

## Consequences

The three surfaces can temporarily carry different version labels, so every
status report must name the repository/ref as well as the package version. The
benefit is a reversible promotion path with no accidental public or manuscript
scope expansion.
