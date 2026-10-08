# ADR-0028: Publish 2.0 Independently of the 1.1.x Review Line

- Status: Accepted
- Date: 2026-10-08
- Owner: Project owner
- Supersedes: ADR-0015 local-only publication restriction, not its frozen-ref boundaries

## Context and decision drivers

The project owner authorized the proposed RC-to-release sequence while 1.1.x
is under review. Publishing 2.0 must not change the review line, historical
tags, or frozen TOIS materials. Passing tests alone never authorizes publication.

## Options and decision

Replacing main with 2.0 now is rejected because it moves the review entry point.
A separate repository is unnecessary. Use the existing independent
`codex/sidscope-v2` branch in `jdding/SIDscope`, through the `sidscope` remote;
keep main at its current 1.1.x authority. Do not push to the old `origin`.

The explicit authorization covers governance updates, `2.0.0rc1`, fresh
same-source acceptance, public content/history review, the independent branch
push, and then `2.0.0`, immutable `v2.0.0`, GitHub Release assets and anonymous
download smoke. A passing RC may also be retained as immutable `v2.0.0-rc.1`.
PyPI publication, main/default-branch changes, force pushes, old-tag changes,
maintenance-worktree edits and frozen TOIS writes are outside this authorization.

## Migration and validation

Keep the frozen 1.7 surface and public consumer contract bytes unchanged;
package-version changes do not alter semantic producer versions or native
generation. The current package may be development, RC, or stable while
engineering receipts are gathered; certification still requires all ten gates
and a verified same-source delivery summary. Automated records continue to
report `release_authorized=false`: they certify evidence, not human authority.

Re-run full CPU tests, verifiers, performance, wheel/sdist and installed native
consumers, all three archives, deterministic rebuild and G8 for each clean
release commit. Linux is unsupported under ADR-0027; independent user adoption
remains not verified under ADR-0025. Do not invent broader support or claims.
Review every new reachable Git blob before pushing, not only release archives.
Record publication URLs, artifact hashes, anonymous readback and unchanged old
remote refs in a new version-specific release packet; never overwrite the 1.1
packet. Preserve all private evidence and failed attempts without publishing it.

## Consequences and rollback

Main and latest Release temporarily describe different product lines; Release
notes and branch README must make this explicit. Review reproduction uses an
exact manuscript/software ref, not a moving branch. Later default-branch
promotion requires a separate owner decision. If acceptance fails, keep the
candidate and evidence unpublished; if a published release needs correction,
issue a new version without moving or deleting any published tag.
