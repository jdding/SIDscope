#!/usr/bin/env python3
"""Fail closed when the checked-in SIDScope architecture inventory drifts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.build_sidscope_architecture_inventory import DEFAULT_OUTPUT, ROOT, build_inventory


REPORT_SCHEMA = "sidscope.architecture_inventory_verification.v1"
DIAGRAM_BASE = "docs/figures/sidscope-current-architecture"


def validate_diagram(document: dict[str, Any]) -> dict[str, Any]:
    """Check the illustration's content map, not its pixels or acceptance."""
    sys.path.insert(0, str(ROOT / "src"))
    from sidinspector.version import PRODUCT_VERSION
    if document.get("product_version") != PRODUCT_VERSION:
        raise ValueError("architecture_diagram_version_drift")
    if (document.get("format") != "sidscope-architecture-content-map"
            or document.get("view") != "local_implementation_not_public_certification"):
        raise ValueError("architecture_diagram_scope_drift")
    layers, surfaces = document.get("layers"), document.get("surfaces")
    if not isinstance(layers, list) or not isinstance(surfaces, list):
        raise ValueError("architecture_diagram_invalid_nodes")
    nodes = layers + surfaces
    if any(not isinstance(node, dict) or not isinstance(node.get("id"), str) for node in nodes):
        raise ValueError("architecture_diagram_invalid_nodes")
    by_id = {node["id"]: node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("architecture_diagram_duplicate_or_missing_id")
    if {node["id"] for node in layers} != {"integration", "contracts", "observation", "evaluation", "conformance", "evidence"}:
        raise ValueError("architecture_diagram_layer_drift")
    if {node["id"] for node in surfaces} != {"upstream", "workflows", "review", "indexes"}:
        raise ValueError("architecture_diagram_surface_drift")
    paths = set()
    for node in nodes:
        code_paths = node.get("code_paths")
        if not isinstance(code_paths, list) or not code_paths or not node.get("label"):
            raise ValueError("architecture_diagram_missing_code_path")
        for relative in code_paths:
            if not isinstance(relative, str) or not relative:
                raise ValueError("architecture_diagram_missing_code_path")
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not (ROOT / path).exists():
                raise ValueError("architecture_diagram_missing_code_path: " + relative)
            paths.add(relative)
    edges = document.get("edges")
    if not isinstance(edges, list):
        raise ValueError("architecture_diagram_broken_edge")
    observed_edges = []
    for edge in edges:
        if (not isinstance(edge, dict)
                or any(not isinstance(edge.get(key), str) for key in ("source", "target", "kind"))
                or edge["source"] not in by_id or edge["target"] not in by_id):
            raise ValueError("architecture_diagram_broken_edge")
        observed_edges.append((edge["source"], edge["target"], edge["kind"]))
    expected_edges = {
        (source, target, "artifact_flow") for source, target in (
            ("upstream", "integration"), ("integration", "observation"),
            ("observation", "evaluation"), ("evaluation", "conformance"),
            ("conformance", "evidence"), ("evidence", "review"), ("evidence", "indexes"))
    } | {("contracts", target, "contract_binding") for target in (
        "integration", "observation", "evaluation", "conformance", "evidence")}
    if set(observed_edges) != expected_edges or len(observed_edges) != len(expected_edges):
        raise ValueError("architecture_diagram_flow_drift")
    return {"owned_layers": len(layers), "code_paths_checked": len(paths),
        "logical_edges_checked": len(observed_edges), "pixel_semantics_checked": False}


def verify_diagram(inventory_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    expected_paths = {DIAGRAM_BASE + suffix for suffix in (".json", "-prompt.md", ".png")}
    observed = json.loads(inventory_path.read_text())["current_diagram_files"]
    if set(observed) != expected_paths:
        raise ValueError("architecture_diagram_checksum_paths")
    for name, digest in observed.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("architecture_diagram_content_drift: " + name)
    if not (ROOT / (DIAGRAM_BASE + ".png")).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("architecture_diagram_invalid_preview")
    return validate_diagram(json.loads((ROOT / (DIAGRAM_BASE + ".json")).read_text()))


def verify_inventory(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = build_inventory()
    if observed != expected:
        observed_ids = {row["schema_id"] for row in observed.get("schemas", [])}
        expected_ids = {row["schema_id"] for row in expected["schemas"]}
        raise ValueError(
            "architecture inventory drift: "
            f"missing={sorted(expected_ids - observed_ids)}, "
            f"stale={sorted(observed_ids - expected_ids)}; rebuild the inventory"
        )

    for record in observed["schemas"]:
        if not record["owner"] or not record["declaration_paths"]:
            raise ValueError(f"unowned or undeclared schema: {record['schema_id']}")
        for rel_path in record["declaration_paths"]:
            if not (ROOT / rel_path).is_file():
                raise FileNotFoundError(rel_path)
    for profile in observed["profiles"]:
        for key in ("authority", "verifier"):
            if not (ROOT / profile[key]).exists():
                raise FileNotFoundError(profile[key])
    for authority in observed.get("legacy_profile_authorities", []):
        for key in ("authority", "verifier"):
            if not (ROOT / authority[key]).exists():
                raise FileNotFoundError(authority[key])

    routes = observed["routes"]
    registry = observed["canonical_contract_registry"]
    if registry["contract_count"] != len(registry["contracts"]):
        raise ValueError("canonical contract registry count mismatch")
    if registry["contract_count"] != 11:
        raise ValueError("canonical contract registry does not close SIDScope 1.2")
    if any(edge["status"] != "implemented" for edge in observed["canonical_evidence_edges"]):
        raise ValueError("canonical 1.2 evidence DAG contains an unimplemented edge")
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass",
        "inventory_schema": observed["schema"],
        "schema_count": observed["schema_count"],
        "profile_count": len(observed["profiles"]),
        "generator_route_count": len(routes["generator"]),
        "static_mapping_route_count": len(routes["static_mapping"]),
        "canonical_evidence_edge_count": len(observed["canonical_evidence_edges"]),
        "canonical_contract_count": registry["contract_count"],
        "current_diagram": verify_diagram(path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_inventory(args.inventory)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
