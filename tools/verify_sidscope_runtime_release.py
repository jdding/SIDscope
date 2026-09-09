#!/usr/bin/env python3
"""Verify the minimal installable SIDScope runtime release profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.schemas import CLI_RESULT_SCHEMA_IDS, load_public_schema_catalog, validate_cli_result
from sidinspector.version import PRODUCT_VERSION
from sidscope import __all__ as SIDSCOPE_PUBLIC_SYMBOLS
from sidscope import __version__ as SIDSCOPE_VERSION
try:
    from tools.sidscope_release_profiles import (
        PROFILE_RECEIPT_PATH,
        ReleaseProfileError,
        file_sha256,
        load_release_profiles,
        validate_profile_receipt,
    )
except ModuleNotFoundError:
    from sidscope_release_profiles import (
        PROFILE_RECEIPT_PATH,
        ReleaseProfileError,
        file_sha256,
        load_release_profiles,
        validate_profile_receipt,
    )


IGNORED_PARTS = {".pytest_cache", "__pycache__"}
FORBIDDEN_RUNTIME_PREFIXES = ("docs/reproducibility/", "examples/", "experiments/", "tests/")
PROFILE_REGISTRY_REL_PATH = "docs/reproducibility/sidscope_release_profiles.v1.json"
FORBIDDEN_CONTENT_TOKENS = ("/Users/", "/Volumes/", "/private/", "root@", "autodl-tmp")


def release_files(root: Path) -> list[str]:
    paths: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_dir() or any(part in IGNORED_PARTS or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        paths.append(rel.as_posix())
    return sorted(paths)


def _forbidden_content(root: Path, paths: list[str]) -> list[str]:
    findings: list[str] = []
    for rel_path in paths:
        path = root / rel_path
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for token in FORBIDDEN_CONTENT_TOKENS:
                if rel_path == "tools/verify_sidscope_runtime_release.py" and (
                    f'"{token}"' in line or f"'{token}'" in line
                ):
                    continue
                if token in line:
                    findings.append(f"{rel_path}:{line_number}:{token}")
    return findings


def verify_runtime_release(root: Path = ROOT) -> dict[str, Any]:
    receipt_path = root / PROFILE_RECEIPT_PATH
    if not receipt_path.is_file():
        raise ReleaseProfileError("missing_profile_receipt", str(receipt_path))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    all_paths = release_files(root)
    content_paths = [path for path in all_paths if path != PROFILE_RECEIPT_PATH]
    profile_id = validate_profile_receipt(
        receipt, content_paths=content_paths,
        content_hashes={path: file_sha256(root / path) for path in content_paths},
    )
    if profile_id not in {"runtime", "conformance", "evidence-full"}:
        raise ReleaseProfileError("unsupported_runtime_verification_profile", profile_id)

    if profile_id == "runtime":
        forbidden_paths = [
            path
            for path in content_paths
            if path != PROFILE_REGISTRY_REL_PATH and path.startswith(FORBIDDEN_RUNTIME_PREFIXES)
        ]
        if forbidden_paths:
            raise ReleaseProfileError("runtime_profile_leak", forbidden_paths[0])
    else:
        forbidden_paths = []

    registry_path = root / PROFILE_REGISTRY_REL_PATH
    if not registry_path.is_file():
        raise ReleaseProfileError("missing_profile_registry", PROFILE_REGISTRY_REL_PATH)
    load_release_profiles(registry_path)
    if receipt.get("profile_registry_sha256") != file_sha256(registry_path):
        raise ReleaseProfileError("profile_registry_binding_mismatch", profile_id)

    findings = _forbidden_content(root, content_paths) if profile_id == "runtime" else []
    if findings:
        raise ReleaseProfileError("forbidden_runtime_content", findings[0])

    if PRODUCT_VERSION != SIDSCOPE_VERSION or receipt.get("product_version") != PRODUCT_VERSION:
        raise ReleaseProfileError(
            "runtime_version_mismatch",
            f"receipt={receipt.get('product_version')} sidinspector={PRODUCT_VERSION} sidscope={SIDSCOPE_VERSION}",
        )
    schemas = load_public_schema_catalog()
    validate_cli_result(
        {
            "schema": "sidscope.public_schema_catalog_listing.v1",
            "status": "pass",
            "failure": None,
        }
    )
    extensions: dict[str, int] = {}
    for path in content_paths:
        suffix = Path(path).suffix.lower() or "[none]"
        extensions[suffix] = extensions.get(suffix, 0) + 1
    return {
        "schema": "sidscope.runtime_release_verification.v1",
        "status": "pass",
        "gpu_required": False,
        "profile_id": profile_id,
        "product_version": PRODUCT_VERSION,
        "content_file_count": len(content_paths),
        "extension_counts": dict(sorted(extensions.items())),
        "public_schema_id_count": len(schemas),
        "public_schema_resource_count": len({row.schema_resource for row in schemas}),
        "cli_result_schema_count": len(CLI_RESULT_SCHEMA_IDS),
        "python_facade_symbol_count": len(SIDSCOPE_PUBLIC_SYMBOLS),
        "forbidden_path_findings": forbidden_paths,
        "forbidden_content_findings": findings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a SIDScope runtime release extraction.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_runtime_release(args.root.resolve())
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
