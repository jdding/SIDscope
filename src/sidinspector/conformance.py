"""Adapter conformance checks for paper-facing SIDScope artifact routes."""

from __future__ import annotations

import csv
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from sidinspector.interface import CONTRACTS, validate_columns
from sidinspector.preflight import preflight_inputs, read_table


DEFAULT_INVENTORY = "docs/reproducibility/sidscope_source_license_config_inventory.csv"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA = "sidscope.adapter_manifest.v1"
REPORT_SCHEMA = "sidscope.adapter_conformance_report.v1"

ALLOWED_LICENSE_STATUSES = {
    "licensed",
    "restricted_source_license",
    "source_licensed_artifact_boundary_unresolved",
    "no_license_detected",
}
ALLOWED_DERIVATIONS = {
    "tracked_snapshot",
    "official_code_derived",
    "official_code_derived_with_compatibility_shim",
    "tokenizer_stage_rebuild",
    "released_archive",
    "released_index",
    "control",
    "stress_reference",
}
ALLOWED_EVIDENCE_ROLES = {
    "source_traced_named_route",
    "released_index_route",
    "official_code_derived_route",
    "tracked_snapshot",
    "stress_reference",
    "control",
}
ALLOWED_RUNTIME_CLASSES = {"cpu_seconds", "cpu_minutes", "gpu_required", "snapshot_only"}


def redact_private_input_paths(report: dict[str, Any]) -> dict[str, Any]:
    """Return a public report that keeps counts but omits non-redistributed input paths."""

    public_report = copy.deepcopy(report)
    for check in public_report.get("checks", []):
        if check.get("level") != "C1":
            continue
        tables = check.get("details", {}).get("tables", {})
        for table in tables.values():
            table.pop("path", None)
            table["availability"] = "summary_only_raw_not_redistributed"
    return public_report


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _resolve(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"path must be relative to the conformance root: {raw_path}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes the conformance root: {raw_path}") from exc
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _report_path(path: Path, root: Path) -> str:
    """Return a portable path for machine-readable public reports."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _level(level: str, title: str, function: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        details = function()
        return {"level": level, "title": title, "status": "pass", "details": details, "failures": []}
    except Exception as exc:  # collect all layer failures in one report
        return {
            "level": level,
            "title": title,
            "status": "fail",
            "details": {},
            "failures": [f"{type(exc).__name__}: {exc}"],
        }


def _required_dict(parent: dict[str, Any], key: str, required: set[str]) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"manifest.{key} must be an object")
    missing = sorted(field for field in required if value.get(field) in (None, ""))
    if missing:
        raise ValueError(f"manifest.{key} missing required fields: {missing}")
    return value


def _inventory_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["route_id"]: row for row in csv.DictReader(handle)}


def _check_c0(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(f"schema_version must be {MANIFEST_SCHEMA!r}")
    for field in ("artifact_id", "paper_label", "method_family", "configuration"):
        if not str(manifest.get(field, "")).strip():
            raise ValueError(f"manifest.{field} is required")

    source = _required_dict(
        manifest,
        "source",
        {
            "url",
            "revision",
            "license_status",
            "license_identifier",
            "derivation",
            "artifact_name",
            "redistribution_policy",
        },
    )
    dataset = _required_dict(manifest, "dataset", {"name", "expected_items", "sid_depth"})
    inputs = _required_dict(manifest, "inputs", set(CONTRACTS).difference({"generator_outputs"}))
    _required_dict(manifest, "reproduction", {"command", "runtime_class", "source_evidence"})
    _required_dict(
        manifest,
        "promotion",
        {"route_id", "evidence_role", "paper_counted", "conformance_status", "conformance_evidence"},
    )

    if not str(source["url"]).startswith("https://"):
        raise ValueError("manifest.source.url must use https")
    if source["license_status"] not in ALLOWED_LICENSE_STATUSES:
        raise ValueError(f"unsupported license_status={source['license_status']!r}")
    if source["derivation"] not in ALLOWED_DERIVATIONS:
        raise ValueError(f"unsupported derivation={source['derivation']!r}")
    if int(dataset["expected_items"]) <= 0:
        raise ValueError("manifest.dataset.expected_items must be positive")
    if int(dataset["sid_depth"]) <= 0:
        raise ValueError("manifest.dataset.sid_depth must be positive")
    allow_partial = manifest.get("allow_partial_coverage", False)
    if not isinstance(allow_partial, bool):
        raise ValueError("manifest.allow_partial_coverage must be boolean")
    return {
        "artifact_id": manifest["artifact_id"],
        "paper_label": manifest["paper_label"],
        "source_revision": source["revision"],
        "license_status": source["license_status"],
    }


def _sid_level_columns(columns: list[str]) -> list[str]:
    levels: list[tuple[int, str]] = []
    for column in columns:
        if not column.startswith("sid_level_"):
            continue
        suffix = column.removeprefix("sid_level_")
        if not suffix.isdigit():
            raise ValueError(f"invalid SID level column: {column}")
        levels.append((int(suffix), column))
    levels.sort()
    if [index for index, _ in levels] != list(range(len(levels))):
        raise ValueError("SID level columns must be contiguous from sid_level_0")
    if not levels:
        raise ValueError("sid_assignments must include at least one sid_level_* column")
    return [column for _, column in levels]


def _check_c1(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    inputs = manifest["inputs"]
    paths = {name: _resolve(root, str(raw_path)) for name, raw_path in inputs.items()}
    if len(set(paths.values())) != len(paths):
        raise ValueError("manifest.inputs must resolve to three distinct normalized tables")
    tables = {name: read_table(path) for name, path in paths.items()}
    for name, frame in tables.items():
        validate_columns(name, frame.columns)
        if frame.empty:
            raise ValueError(f"{name} is empty")

    sid = tables["sid_assignments"]
    levels = _sid_level_columns(list(sid.columns))
    reconstructed = sid[levels].astype(str).agg("-".join, axis=1)
    mismatch = sid["sid"].astype(str) != reconstructed
    if mismatch.any():
        example = int(mismatch[mismatch].index[0])
        raise ValueError(f"sid does not match sid_level_* columns at row index {example}")
    if sid["item_id"].duplicated().any():
        raise ValueError("sid_assignments contains duplicate item_id values")

    expected_items = int(manifest["dataset"]["expected_items"])
    if len(sid) != expected_items:
        raise ValueError(f"expected {expected_items} SID rows, observed {len(sid)}")
    observed_datasets = sorted(str(value) for value in sid["dataset"].dropna().unique())
    expected_dataset = str(manifest["dataset"].get("normalized_name", manifest["dataset"]["name"]))
    if observed_datasets != [expected_dataset]:
        raise ValueError(f"dataset mismatch: expected {expected_dataset!r}, observed {observed_datasets}")
    for name in ("item_metadata", "interactions"):
        frame = tables[name]
        if "dataset" not in frame.columns:
            continue
        observed = sorted(str(value) for value in frame["dataset"].dropna().unique())
        if observed != [expected_dataset]:
            raise ValueError(f"{name} dataset mismatch: expected {expected_dataset!r}, observed {observed}")
    expected_depth = int(manifest["dataset"]["sid_depth"])
    if len(levels) != expected_depth:
        raise ValueError(f"expected SID depth {expected_depth}, observed {len(levels)}")

    return {
        "tables": {name: {"path": inputs[name], "rows": len(frame)} for name, frame in tables.items()},
        "sid_depth": len(levels),
        "sid_reconstruction_match": True,
    }


def _check_c2(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    inputs = manifest["inputs"]
    result = preflight_inputs(
        _resolve(root, inputs["sid_assignments"]),
        _resolve(root, inputs["item_metadata"]),
        _resolve(root, inputs["interactions"]),
        allow_partial_coverage=manifest.get("allow_partial_coverage", False),
    )
    empty_interactions = [row for row in result["coverage"] if int(row["interaction_items"]) == 0]
    if empty_interactions:
        raise ValueError("artifact dataset has no joined interaction items")
    return {"status": result["status"], "coverage": result["coverage"]}


def _check_c3(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    inputs = manifest["inputs"]
    smoke = manifest.get("metric_smoke", {})
    if not isinstance(smoke, dict):
        raise ValueError("manifest.metric_smoke must be an object")
    result = preflight_inputs(
        _resolve(root, inputs["sid_assignments"]),
        _resolve(root, inputs["item_metadata"]),
        _resolve(root, inputs["interactions"]),
        allow_partial_coverage=manifest.get("allow_partial_coverage", False),
        run_metric_smoke=True,
        max_metric_items=int(smoke.get("max_metric_items", 50_000)),
        top_k=int(smoke.get("top_k", 5)),
        max_pair_events=int(smoke.get("max_pair_events", 10_000)),
        max_user_items=int(smoke.get("max_user_items", 50)),
    )
    empty_interactions = [row for row in result["coverage"] if int(row["interaction_items"]) == 0]
    if empty_interactions:
        raise ValueError("artifact dataset has no joined interaction items")
    for row in result["metric_smoke_summary"]:
        if int(row.get("d1_level_count", 0)) <= 0:
            raise ValueError("D1 utilization did not produce per-level results")
    return {"bounds": result["bounds"], "metric_smoke_summary": result["metric_smoke_summary"]}


def _check_c4(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    reproduction = manifest["reproduction"]
    command = reproduction["command"]
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
        raise ValueError("manifest.reproduction.command must be a non-empty string list")
    if reproduction["runtime_class"] not in ALLOWED_RUNTIME_CLASSES:
        raise ValueError(f"unsupported runtime_class={reproduction['runtime_class']!r}")

    evidence = reproduction["source_evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("manifest.reproduction.source_evidence must be a non-empty list")
    evidence_paths = [_resolve(root, path) for path in evidence]
    missing = [str(path) for path in evidence_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing source evidence: {missing}")

    expected_hashes = manifest.get("input_sha256")
    expected_names = set(manifest["inputs"])
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != expected_names:
        raise ValueError(f"manifest.input_sha256 must contain exactly {sorted(expected_names)}")
    observed_hashes: dict[str, str] = {}
    for name, raw_path in manifest["inputs"].items():
        path = _resolve(root, raw_path)
        observed_hashes[name] = _sha256(path)
        if observed_hashes[name] != expected_hashes[name]:
            raise ValueError(f"sha256 mismatch for {name}")

    return {
        "command": command,
        "runtime_class": reproduction["runtime_class"],
        "source_evidence": evidence,
        "input_sha256": observed_hashes,
    }


def _check_c5(manifest: dict[str, Any], inventory_path: Path) -> dict[str, Any]:
    promotion = manifest["promotion"]
    if promotion["evidence_role"] not in ALLOWED_EVIDENCE_ROLES:
        raise ValueError(f"unsupported evidence_role={promotion['evidence_role']!r}")
    if not isinstance(promotion["paper_counted"], bool):
        raise ValueError("manifest.promotion.paper_counted must be boolean")
    if promotion["paper_counted"] and promotion["evidence_role"] in {"stress_reference", "control"}:
        raise ValueError("stress/reference and control routes cannot count as named paper coverage")
    if promotion["paper_counted"] and manifest.get("allow_partial_coverage", False):
        raise ValueError("paper-counted routes cannot enable partial coverage")

    inventory = _inventory_rows(inventory_path)
    route_id = str(promotion["route_id"])
    if not promotion["paper_counted"]:
        return {"paper_counted": False, "evidence_role": promotion["evidence_role"], "route_id": route_id}
    if route_id not in inventory:
        raise ValueError(f"paper-counted route_id is absent from the source inventory: {route_id}")

    row = inventory[route_id]
    source = manifest["source"]
    expected = {
        "paper_label": row["paper_label"],
        "method_family": row["method_family"],
        "dataset": row["dataset"],
        "source_url": row["source_url"],
        "source_revision": row["source_revision"],
        "artifact_name": row["artifact_name"],
        "license_status": row["license_status"],
        "license_identifier": row["license_identifier"],
        "redistribution_policy": row["redistribution_policy"],
        "derivation": row["derivation"],
        "configuration": row["configuration"],
        "expected_items": int(row["item_count"]),
        "sid_depth": int(row["sid_depth"]),
        "conformance_status": row["conformance_status"],
        "conformance_evidence": row["conformance_evidence"],
        "evidence_role": row["evidence_role"],
    }
    observed = {
        "paper_label": manifest["paper_label"],
        "method_family": manifest["method_family"],
        "dataset": manifest["dataset"]["name"],
        "source_url": source["url"],
        "source_revision": source["revision"],
        "artifact_name": source["artifact_name"],
        "license_status": source["license_status"],
        "license_identifier": source["license_identifier"],
        "redistribution_policy": source["redistribution_policy"],
        "derivation": source["derivation"],
        "configuration": manifest["configuration"],
        "expected_items": int(manifest["dataset"]["expected_items"]),
        "sid_depth": int(manifest["dataset"]["sid_depth"]),
        "conformance_status": promotion["conformance_status"],
        "conformance_evidence": promotion["conformance_evidence"],
        "evidence_role": promotion["evidence_role"],
    }
    if observed != expected:
        raise ValueError(f"promotion metadata does not match inventory: expected={expected}, observed={observed}")
    return {
        "paper_counted": True,
        "evidence_role": promotion["evidence_role"],
        "route_id": route_id,
        "inventory_match": True,
    }


def run_conformance(
    manifest_path: Path,
    *,
    root: Path,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    """Run C0-C5 conformance gates and return a machine-readable report."""

    manifest = _load_json(manifest_path)
    root = root.resolve()
    inventory_path = inventory_path or PROJECT_ROOT / DEFAULT_INVENTORY
    checks = [
        _level("C0", "Source and license declaration", lambda: _check_c0(manifest)),
        _level("C1", "Normalized table schema", lambda: _check_c1(manifest, root)),
        _level("C2", "Coverage and join preflight", lambda: _check_c2(manifest, root)),
        _level("C3", "Bounded D1-D5 smoke", lambda: _check_c3(manifest, root)),
        _level("C4", "Reproduction record and input hashes", lambda: _check_c4(manifest, root)),
        _level("C5", "Paper-promotion contract", lambda: _check_c5(manifest, inventory_path)),
    ]
    failed = [check["level"] for check in checks if check["status"] != "pass"]
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass" if not failed else "fail",
        "manifest": _report_path(manifest_path, root),
        "artifact_id": manifest.get("artifact_id"),
        "paper_label": manifest.get("paper_label"),
        "checks": checks,
        "failed_levels": failed,
    }
