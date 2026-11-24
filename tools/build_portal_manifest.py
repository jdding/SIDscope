#!/usr/bin/env python3
"""Build PACKAGE_MANIFEST.json and SHA256SUMS for SIDScope's resource portal."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PORTAL_FILES = [
    "README.md",
    "CITATION.cff",
    "LICENSE",
    "ARTIFACT_QUICKSTART.md",
    "EXPECTED_OUTPUTS.md",
    "RELEASE_STATUS.json",
    "index.html",
    "demo/browser.css",
    "demo/browser-example.js",
    "demo/browser_example.py",
    "demo/local.html",
    "demo/python-worker.js",
    "tools/build_sidscope_paper_tables.py",
    "tools/serve_demo.py",
    "tools/validate_resource_portal.py",
    "examples/reviewer_quickstart_data/sid_codes.csv",
    "examples/reviewer_quickstart_data/interactions.csv",
    "examples/reviewer_quickstart_data/item_metadata.csv",
    "examples/conformance_failure_fixture/manifest.json",
    "examples/conformance_failure_fixture/sid_assignments.csv",
    "examples/conformance_failure_fixture/item_metadata.csv",
    "examples/conformance_failure_fixture/interactions.csv",
    "examples/conformance_failure_fixture/conformance_report.json",
    "docs/BRING_YOUR_OWN_DATA.md",
    "docs/RESOURCE_CAPABILITIES.md",
    "docs/LOCAL_DEMO.md",
    "docs/RELATION_TO_SIDINSPECTOR_AND_SIDDUET.md",
    "docs/reproducibility/sidscope_source_license_config_inventory.csv",
    "docs/reproducibility/d7_labeled_trace_release.json",
    "docs/reproducibility/g22_diagnose_repair_handoff_summary.json",
    "docs/reproducibility/g22_handoff_uncertainty.json",
    "docs/reproducibility/g20_trained_trace_summary.json",
    "docs/reproducibility/g21_released_tiger_trace_summary.json",
    "docs/reproducibility/paper_table_sources/table1_resource_delta_source.csv",
    "docs/reproducibility/paper_table_sources/table2_artifact_coverage_source.csv",
    "docs/reproducibility/paper_table_sources/table4_evidence_ladder_source.csv",
    "docs/reproducibility/paper_table_sources/table5_trace_accounting_source.csv",
    "docs/reproducibility/paper_table_sources/table6_resource_contract_source.csv",
    "docs/reproducibility/paper_table_sources/table10_g20_trained_trace_source.csv",
    "docs/reproducibility/paper_tables/table1_resource_delta.csv",
    "docs/reproducibility/paper_tables/table2_artifact_coverage.csv",
    "docs/reproducibility/paper_tables/table4_adapter_conformance.csv",
    "docs/reproducibility/paper_tables/table5_diagnostic_profile.csv",
    "docs/reproducibility/paper_tables/table6_evidence_ladder.csv",
    "docs/reproducibility/paper_tables/table8_resot_walkthrough.csv",
    "docs/reproducibility/paper_tables/table9_resource_contract.csv",
    "docs/reproducibility/paper_tables/table10_g20_trained_trace.csv",
    "docs/reproducibility/conformance/resid_gaoq_video_report.json",
    "docs/reproducibility/conformance/grid_p5_beauty_report.json",
    "docs/reproducibility/conformance/card_p5_beauty_report.json",
    "docs/reproducibility/conformance/diger_beauty_report.json",
    "docs/reproducibility/conformance/diger_yelp_report.json",
    "docs/reproducibility/conformance/resot_instruments_report.json",
    "docs/reproducibility/conformance/letter_instruments_report.json",
    "docs/reproducibility/conformance/lcrec_instruments_report.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    status = json.loads((ROOT / "RELEASE_STATUS.json").read_text(encoding="utf-8"))
    entries = []
    checksum_lines = []
    for rel in sorted(set(PORTAL_FILES)):
        full = ROOT / rel
        if not full.is_file():
            raise FileNotFoundError(f"Expected portal file missing: {rel}")
        digest = sha256_file(full)
        entries.append({"path": rel, "sha256": digest, "bytes": full.stat().st_size})
        checksum_lines.append(f"{digest}  {rel}")

    manifest = {
        "schema": "sidscope.portal_manifest.v1",
        "name": status["name"],
        "version": status["version"],
        "portal_revision": status["portal_revision"],
        "file_count": len(entries),
        "files": entries,
    }
    (ROOT / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    print(f"Wrote SIDScope PACKAGE_MANIFEST.json and SHA256SUMS ({len(entries)} files)")


if __name__ == "__main__":
    main()
