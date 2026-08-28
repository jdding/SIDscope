from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from tests import local_test_bootstrap  # noqa: F401
from sidinspector.adapters.diffgrm import TRACE_SCHEMA_V2, canonical_sha256
from tools.verify_diffgrm_trained_trace_bundle import verify_paths


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/diffgrm_masked_diffusion_fixture"


def _read(name: str) -> dict:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def _write_v2_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    prepared = _read("prepared_dataset.json")
    selection = _read("episode_selection.json")
    bundle = _read("trained_trace_fixture.json")
    selection["episodes"][0]["gap_bucket"] = "30-90d"
    bundle["episodes"][0]["gap_bucket"] = "30-90d"
    bundle["schema"] = TRACE_SCHEMA_V2
    bundle["evidence_kind"] = "checkpoint_bound_trained_smoke"
    bundle["configuration"]["seed"] = 2024
    bundle["episode_selection_manifest_sha256"] = canonical_sha256(selection)
    bundle["evidence"] = {
        "source_revision": bundle["source_revision"],
        "source_manifest_sha256": "1" * 64,
        "configuration_sha256": canonical_sha256(bundle["configuration"]),
        "checkpoint_sha256": "2" * 64,
        "training_manifest_sha256": "3" * 64,
        "semantic_id_cache_sha256": "4" * 64,
        "run_log_sha256": "5" * 64,
    }
    prepared_path = tmp_path / "prepared_dataset.json"
    selection_path = tmp_path / "episode_selection.json"
    bundle_path = tmp_path / "trained_trace_bundle.json"
    prepared_path.write_text(json.dumps(prepared), encoding="utf-8")
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    return prepared_path, selection_path, bundle_path


def test_real_bundle_verifier_accepts_checkpoint_bound_v2(tmp_path: Path) -> None:
    prepared, selection, bundle = _write_v2_inputs(tmp_path)
    result = verify_paths(prepared, selection, bundle)
    assert result["status"] == "pass"
    assert result["source_audit_checked"] is False
    assert result["license_audit_checked"] is False
    assert result["episode_count"] == 1
    assert result["five_bucket_counts"] == {
        "short": 0,
        "30-90d": 1,
        "90-180d": 0,
        "180-365d": 0,
        ">365d": 0,
    }
    assert result["bindings"]["binding_level"] == "checkpoint_bound_v2"
    assert result["metrics"]["hit_at_10"] == 1.0
    assert result["rank_summary"]["exact_target_rank_count"] == 1
    assert result["resolution_summary"]["invalid_raw_tuple_count"] == 0
    assert result["compute_summary"]["nfe"] == 4


def test_real_bundle_verifier_rejects_prepared_binding_mismatch(tmp_path: Path) -> None:
    prepared, selection, bundle_path = _write_v2_inputs(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["prepared_dataset_contract_sha256"] = "0" * 64
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    result = verify_paths(prepared, selection, bundle_path)
    assert result["status"] == "fail"
    assert result["failure"]["label"] == "prepared_binding_mismatch"


def test_real_bundle_verifier_rejects_unknown_parent_beam(tmp_path: Path) -> None:
    prepared, selection, bundle_path = _write_v2_inputs(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["episodes"][0]["attempts"][0]["steps"][1]["expanded_candidates"][0][
        "parent_beam_id"
    ] = "missing-parent"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    result = verify_paths(prepared, selection, bundle_path)
    assert result["status"] == "fail"
    assert result["failure"]["label"] == "unknown_parent_beam"


def test_real_bundle_cli_writes_canonical_result(tmp_path: Path) -> None:
    prepared, selection, bundle = _write_v2_inputs(tmp_path)
    result_path = tmp_path / "verification.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/verify_diffgrm_trained_trace_bundle.py"),
            "--prepared",
            str(prepared),
            "--selection",
            str(selection),
            "--bundle",
            str(bundle),
            "--result-json",
            str(result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["schema"] == "sidscope.diffgrm_trained_trace_bundle_verification.v1"
    assert result["canonical_sha256"]["bundle"]


def test_v2_configuration_hash_is_fail_closed(tmp_path: Path) -> None:
    prepared, selection, bundle_path = _write_v2_inputs(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["configuration"]["beam_max"] = 3
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    result = verify_paths(prepared, selection, bundle_path)
    assert result["status"] == "fail"
    assert result["failure"]["label"] == "configuration_binding_mismatch"
