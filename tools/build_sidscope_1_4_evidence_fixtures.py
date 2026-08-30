#!/usr/bin/env python3
"""Build deterministic positive and typed-negative SIDScope 1.4 fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_sha256, with_content_sha256
from sidinspector.evidence.bundle import build_evidence_bundle


OUTPUT = ROOT / "examples" / "evidence_system_fixture"
ROLES = ("source", "data", "sid", "run", "checkpoint", "trace", "diagnostics", "conformance")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_rows(
    public_content_sha256: str, public_object_sha256: str, public_size: int
) -> list[dict[str, object]]:
    rows = []
    for index, role in enumerate(ROLES, start=1):
        embedded = role == "conformance"
        rows.append(
            {
                "artifact_id": f"{index:02d}-{role}",
                "role": role,
                "schema_id": f"sidscope.fixture.{role}.v1",
                "schema_revision": "1.0.0",
                "content_sha256": public_content_sha256 if embedded else canonical_sha256({"role": role}),
                "object_sha256": public_object_sha256 if embedded else canonical_sha256({"object_role": role}),
                "size_bytes": public_size if embedded else index * 100,
                "media_type": "application/json",
                "availability": "embedded_public" if embedded else "hash_reference_only",
            }
        )
    return rows


def provenance_edges() -> list[dict[str, str]]:
    return [
        {
            "from_artifact": f"{index:02d}-{ROLES[index - 1]}",
            "to_artifact": f"{index + 1:02d}-{ROLES[index]}",
            "relation": "produces",
        }
        for index in range(1, len(ROLES))
    ]


def bundle(
    *,
    bundle_id: str,
    public_content_sha256: str,
    public_object_sha256: str,
    public_size: int,
    adapter_id: str,
    hit_at_10: float,
    target_universe_sha256: str,
    supersedes: list[str] | None = None,
) -> dict[str, object]:
    return build_evidence_bundle(
        bundle_id=bundle_id,
        producer={"name": "sidscope.fixture", "version": "1.4.0.dev0"},
        profile_binding={
            "profile_id": "family.parallel_graph_token_set.v1",
            "profile_revision": "1.0.0",
            "conformance_report_sha256": public_content_sha256,
        },
        subject={"adapter_id": adapter_id, "method_family": "parallel_graph_token_set"},
        compatibility={
            "dataset_identity_sha256": "1" * 64,
            "target_universe_sha256": target_universe_sha256,
            "evaluation_cutoff": 10,
            "publication_depth": 100,
            "rank_semantics": "exact_with_censoring",
        },
        artifacts=artifact_rows(public_content_sha256, public_object_sha256, public_size),
        provenance_edges=provenance_edges(),
        result_card={
            "overall_metrics": {"hit_at_10": hit_at_10, "ndcg_at_10": hit_at_10 / 2},
            "slice_metrics": {
                "overall": {"hit_at_10": hit_at_10, "ndcg_at_10": hit_at_10 / 2},
                "gap_gt_365d": {"hit_at_10": hit_at_10 / 2, "ndcg_at_10": hit_at_10 / 4},
            },
            "failure_counts": {
                "generation_search_miss": 7,
                "resolution_loss": 1,
                "success": 2,
            },
            "compute": {"nfe": 10, "candidate_count": 100, "latency_ms": 12.5},
            "rank_observations": {
                "exact_count": 2,
                "censored_count": 8,
                "exact_ranks": [3, 37],
            },
        },
        supersedes=supersedes or [],
    ).to_dict()


def main() -> None:
    public = {"schema": "sidscope.fixture.conformance.v1", "status": "pass", "gate_count": 6}
    public_path = OUTPUT / "public_conformance_summary.json"
    write_json(public_path, public)
    public_bytes = public_path.read_bytes()
    public_object_sha256 = hashlib.sha256(public_bytes).hexdigest()
    public_content_sha256 = canonical_sha256(public)

    baseline = bundle(
        bundle_id="fixture:rpg:baseline",
        public_content_sha256=public_content_sha256,
        public_object_sha256=public_object_sha256,
        public_size=len(public_bytes),
        adapter_id="rpg-fixture-a",
        hit_at_10=0.2,
        target_universe_sha256="2" * 64,
    )
    correction = bundle(
        bundle_id="fixture:rpg:correction",
        public_content_sha256=public_content_sha256,
        public_object_sha256=public_object_sha256,
        public_size=len(public_bytes),
        adapter_id="rpg-fixture-b",
        hit_at_10=0.3,
        target_universe_sha256="2" * 64,
        supersedes=[str(baseline["content_sha256"])],
    )
    incompatible = bundle(
        bundle_id="fixture:rpg:other-universe",
        public_content_sha256=public_content_sha256,
        public_object_sha256=public_object_sha256,
        public_size=len(public_bytes),
        adapter_id="rpg-fixture-c",
        hit_at_10=0.4,
        target_universe_sha256="3" * 64,
    )
    write_json(OUTPUT / "baseline_bundle.json", baseline)
    write_json(OUTPUT / "correction_bundle.json", correction)
    write_json(OUTPUT / "incompatible_bundle.json", incompatible)

    spec = copy.deepcopy(baseline)
    for field in ("schema", "schema_revision", "content_sha256"):
        spec.pop(field)
    write_json(OUTPUT / "baseline_bundle_spec.json", spec)

    privacy = copy.deepcopy(baseline)
    privacy["privacy"]["source_item_ids_exported"] = True
    write_json(OUTPUT / "expected_failure_privacy.json", with_content_sha256(privacy))

    rank = copy.deepcopy(baseline)
    rank["compatibility"]["publication_depth"] = 10
    rank["compatibility"]["rank_semantics"] = "cutoff_only"
    rank["result_card"]["rank_observations"] = {
        "exact_count": 1,
        "censored_count": 9,
        "exact_ranks": [11],
    }
    write_json(OUTPUT / "expected_failure_unsupported_rank.json", with_content_sha256(rank))

    cycle = copy.deepcopy(baseline)
    cycle["provenance_edges"].append(
        {
            "from_artifact": "08-conformance",
            "to_artifact": "01-source",
            "relation": "invalid_cycle",
        }
    )
    cycle["provenance_edges"] = sorted(
        cycle["provenance_edges"],
        key=lambda row: (row["from_artifact"], row["to_artifact"], row["relation"]),
    )
    write_json(OUTPUT / "expected_failure_provenance_cycle.json", with_content_sha256(cycle))

    manifest = {
        "schema": "sidscope.evidence_system_fixture_manifest.v1",
        "positive": ["baseline_bundle.json", "correction_bundle.json", "incompatible_bundle.json"],
        "negative": {
            "expected_failure_privacy.json": "privacy_boundary_violation",
            "expected_failure_unsupported_rank.json": "unsupported_exact_rank_claim",
            "expected_failure_provenance_cycle.json": "provenance_cycle",
        },
        "public_artifact": "public_conformance_summary.json",
    }
    write_json(OUTPUT / "manifest.json", manifest)
    print(json.dumps({"status": "pass", "output": str(OUTPUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
