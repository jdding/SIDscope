"""Self-contained synthetic contract walkthrough for installed runtime users."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sidscope import canonical_json_bytes, validate_public_document, with_content_sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    document = with_content_sha256({
        "schema": "sidscope.source_identity.v1",
        "schema_revision": "1.0.0",
        "source_id": "synthetic_runtime_demo",
        "artifact_name": "synthetic runtime demo",
        "producer": {"name": "sidscope.runtime-demo", "version": "1.0.0"},
        "repository": {"url": "https://example.org/synthetic-demo", "revision_kind": "git_commit", "revision": "a" * 40},
        "license": {"status": "no_license_detected", "identifier": "NOASSERTION", "redistribution_policy": "excluded", "notices": []},
        "paper": {"title": "Synthetic example only", "url": "https://example.org/synthetic-demo"},
        "derivation": "tracked_snapshot",
        "patches": [],
    })
    validate_public_document(document)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "source_identity.json"
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(document) + b"\n")
    print(json.dumps({"status": "pass", "synthetic": True, "output": str(path),
                      "boundary": "Contract walkthrough only; not upstream evidence or verified admission."}))


if __name__ == "__main__":
    main()
