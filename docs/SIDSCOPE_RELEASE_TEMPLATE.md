# SIDScope GitHub Release Template

Use this template for an authorized formal release. Replace every placeholder;
do not publish a partially filled record.

```text
Version:
Tag:
Commit:
Release date:

Product changes:
Compatibility:
Breaking changes:
Migration:
1.x-to-2.0 migration guide:

Package version:
Adapter SDK version:
Schema versions/revisions:
Conformance profile versions:
Evidence bundle format versions:
Named adapter status:
Known limitations:

Validation:
- focused tests:
- full tests:
- resource verifier:
- deterministic archive rebuild:
- archive smoke:
- G8 fresh-environment smoke:
- public URL smoke:
- 1.6 compatibility/migration/adoption hardening:

Artifacts:
- source/archive URL:
- release archive URL:
- archive SHA-256:
- release manifest:
```

The post-publication public URL smoke result and final immutable identifiers are
recorded in a new version-specific release packet. Preserve the historical
`docs/SIDSCOPE_PUBLIC_RELEASE_PACKET.md` for 1.1.0 unchanged.
