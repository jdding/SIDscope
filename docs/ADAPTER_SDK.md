# SIDScope Adapter SDK 1.0

Status: stable candidate in local `1.7.0.dev0`; no public release implied.

Adapter SDK `1.0.0` freezes the dependency-light method boundary already proven
by the pre-2.0 plugin, compatibility and installed-consumer gates. It is a
contract for describing capabilities and producing registered artifacts. It is
not a training API, model framework, dependency installer or conformance grant.

## Stable surface

- `sidscope.adapter_capabilities.v1` with `schema_revision: 1.0.0`;
- `ADAPTER_SDK_VERSION == "1.0.0"`;
- `AdapterCapabilities`, `AdapterHarness` and typed `AdapterSDKError`;
- plugin API `1.0` under the `sidscope.adapters` entry-point group;
- exact method-family to native-payload-schema binding;
- lazy discovery and explicit selected-plugin preflight;
- external runtime requirements remain declarations only.

Current descriptors declare `sdk_compatibility` from `1.0.0` up to but not
including `2.0.0`. The runtime also implements the frozen 0.2 API level, so an
unchanged pre-stable descriptor whose declared interval contains `0.2.0`
continues to validate. Publishers adopting the stable contract regenerate the
descriptor with the stable interval; its content hash changes because the
compatibility claim changes. SIDScope never ignores `maximum_exclusive`.

Historical `sidscope.adapter_capabilities.alpha.v1` / SDK `0.1.0` descriptors
remain readable for replay. They lack the native payload binding required of a
stable plugin descriptor and are not promoted into stable descriptors.

## Compatibility and rollback

The 1.0 promotion changes no producer execution, payload family, canonical
artifact or plugin API method. Positive descriptors, interval negatives,
external-package installation and zero-core-edit preflight run in the full
release gates. Rollback pins the last passing pre-stable package and descriptor;
immutable evidence and released historical records are never rewritten.

```bash
sidscope adapter preflight \
  --descriptor examples/native_trace_payload_fixtures/adapter_capabilities.v1.json
python3 tools/verify_sidscope_1_3_plugin_ecosystem.py
python3 tools/verify_sidscope_1_6_hardening.py --gate compatibility
```
