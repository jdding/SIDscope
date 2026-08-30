# SourceIdentity Fixture

`source_identity.json` is the positive canonical `SourceIdentity` v1 example.
`expected_failure_content_hash_mismatch.json` changes only the declared content
hash and must fail with `content_hash_mismatch`.

Validate the positive fixture through the stable facade:

```bash
sidscope contract validate \
  --type source-identity \
  --input examples/source_identity_fixture/source_identity.json
```
