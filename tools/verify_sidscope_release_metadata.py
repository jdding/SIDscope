#!/usr/bin/env python3
"""Verify package, CLI, version-governance, and release-template consistency."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = "sidscope.release_metadata_verification.v1"


def _quoted_value(text: str, key: str) -> str:
    match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise ValueError(f"cannot find {key}")
    return match.group(1)


def verify_release_metadata(root: Path = ROOT) -> dict[str, Any]:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    project = pyproject.split("[project]", 1)[1].split("[", 1)[0]
    setup = (root / "setup.py").read_text(encoding="utf-8")
    project_name = _quoted_value(project, "name")
    project_version = _quoted_value(project, "version")
    setup_name = _quoted_value(setup, "name")
    setup_version = _quoted_value(setup, "version")
    if (project_name, project_version) != (setup_name, setup_version):
        raise ValueError(
            "pyproject/setup metadata mismatch: "
            f"{project_name}=={project_version} != {setup_name}=={setup_version}"
        )
    if 'sidscope = "sidinspector.cli:main"' not in pyproject:
        raise ValueError("pyproject missing the sidscope console facade")
    if '"sidscope=sidinspector.cli:main"' not in setup:
        raise ValueError("setup.py missing the sidscope console facade")
    if 'sidinspector = ["schemas/*.json"]' not in pyproject:
        raise ValueError("pyproject missing bundled JSON schemas")
    if 'package_data={"sidinspector": ["schemas/*.json"]}' not in setup:
        raise ValueError("setup.py missing bundled JSON schemas")

    required_docs = {
        "README.md": ["docs/VERSIONING.md", "docs/COMPATIBILITY.md"],
        "docs/VERSIONING.md": ["five independent compatibility axes", "GitHub Release"],
        "docs/COMPATIBILITY.md": [
            project_version,
            "sidscope.source_identity.v1",
            "sidscope.dataset_identity.v1",
            "sidscope.sid_space_identity.v1",
            "sidscope.prepared_dataset.v1",
        ],
        "docs/SIDSCOPE_RELEASE_TEMPLATE.md": ["Adapter SDK version:", "archive SHA-256:"],
        "docs/SIDSCOPE_RELEASE_CHECKLIST.md": ["docs/SIDSCOPE_RELEASE_TEMPLATE.md"],
    }
    for rel_path, tokens in required_docs.items():
        text = (root / rel_path).read_text(encoding="utf-8")
        missing = [token for token in tokens if token not in text]
        if missing:
            raise ValueError(f"{rel_path} missing release-governance tokens: {missing}")

    return {
        "schema": REPORT_SCHEMA,
        "status": "pass",
        "distribution": project_name,
        "package_version": project_version,
        "python_import": "sidinspector",
        "console_command": "sidscope",
        "canonical_schemas": [
            "sidscope.dataset_identity.v1@1.0.0",
            "sidscope.prepared_dataset.v1@1.0.0",
            "sidscope.sid_space_identity.v1@1.0.0",
            "sidscope.source_identity.v1@1.0.0",
        ],
        "contract_registry": "sidscope.contract_registry.v1@1.0.0",
        "governance_documents_checked": len(required_docs),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_release_metadata()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
