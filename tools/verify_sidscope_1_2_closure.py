#!/usr/bin/env python3
"""Verify the complete canonical 1.2 pipeline, SDK alpha, and CLI parity."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sidinspector.cli import main as cli_main
from sidinspector.contracts import (
    load_checkpoint_binding,
    load_conformance_report,
    load_contract_registry,
    load_diagnostic_report,
    load_episode_selection,
    load_evidence_index,
    load_prepared_dataset,
    load_run_identity,
    load_source_identity,
    load_trace_envelope,
    validate_report_bindings,
    validate_runtime_bindings,
)
from sidinspector.sdk import AdapterSDKError, load_adapter_capabilities


FIXTURE = ROOT / "examples/canonical_pipeline_fixture"


def _quiet_cli(argv: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return cli_main(argv)


def verify_closure() -> dict[str, object]:
    registry = load_contract_registry(repository_root=ROOT)
    source = load_source_identity(FIXTURE / "source_identity.json")
    prepared = load_prepared_dataset(FIXTURE / "prepared_dataset.json")
    selection = load_episode_selection(FIXTURE / "episode_selection.json")
    run = load_run_identity(FIXTURE / "run_identity.json")
    checkpoint = load_checkpoint_binding(FIXTURE / "checkpoint_binding.json")
    trace = load_trace_envelope(FIXTURE / "trace_envelope.json")
    diagnostic = load_diagnostic_report(FIXTURE / "diagnostic_report.json")
    conformance = load_conformance_report(FIXTURE / "conformance_report.json")
    evidence = load_evidence_index(FIXTURE / "evidence_index.json")
    validate_runtime_bindings(
        selection,
        run,
        checkpoint,
        trace,
        source_sha256=source.content_sha256,
        prepared_sha256=prepared.content_sha256,
    )
    validate_report_bindings(diagnostic, conformance, trace, selection)

    expected_hashes = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))["content_sha256"]
        for path in FIXTURE.glob("*.json")
        if not path.name.startswith("expected_failure_")
        and path.name not in {"adapter_capabilities.json", "evidence_index.json"}
    }
    evidence_rows = evidence.to_dict()["artifacts"]
    observed_hashes = {row["content_sha256"] for row in evidence_rows}
    if observed_hashes != set(expected_hashes.values()):
        raise ValueError("evidence index artifact hashes do not cover the canonical pipeline")

    capabilities = load_adapter_capabilities(FIXTURE / "adapter_capabilities.json")
    try:
        load_adapter_capabilities(FIXTURE / "expected_failure_telemetry_overlap.json")
    except AdapterSDKError as exc:
        if exc.code != "telemetry_overlap":
            raise
    else:
        raise ValueError("SDK negative fixture unexpectedly passed")

    artifact_paths = [
        FIXTURE / name
        for name in (
            "source_identity.json",
            "dataset_identity.json",
            "sid_space_identity.json",
            "prepared_dataset.json",
            "episode_selection.json",
            "run_identity.json",
            "checkpoint_binding.json",
            "trace_envelope.json",
            "diagnostic_report.json",
            "conformance_report.json",
        )
    ]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if _quiet_cli(
            ["adapter", "preflight", "--descriptor", str(FIXTURE / "adapter_capabilities.json")]
        ) != 0:
            raise ValueError("adapter preflight CLI failed")
        if _quiet_cli(
            ["trace", "validate", "--input", str(FIXTURE / "trace_envelope.json")]
        ) != 0:
            raise ValueError("trace validate CLI failed")
        evaluated = tmp_path / "diagnostic.json"
        if _quiet_cli(
            [
                "evaluate", "--trace", str(FIXTURE / "trace_envelope.json"),
                "--selection", str(FIXTURE / "episode_selection.json"),
                "--output", str(evaluated),
            ]
        ) != 0:
            raise ValueError("evaluate CLI failed")
        if json.loads(evaluated.read_text(encoding="utf-8")) != diagnostic.to_dict():
            raise ValueError("evaluate CLI differs from canonical diagnostic fixture")
        if _quiet_cli(
            ["verify", "--report", str(FIXTURE / "conformance_report.json")]
        ) != 0:
            raise ValueError("verify CLI failed")
        packaged = tmp_path / "evidence.json"
        command = ["evidence", "package"]
        for path in artifact_paths:
            command.extend(["--artifact", str(path)])
        command.extend(
            ["--index-id", "rpg:fixture-evidence-index", "--output", str(packaged)]
        )
        if _quiet_cli(command) != 0:
            raise ValueError("evidence package CLI failed")
        if json.loads(packaged.read_text(encoding="utf-8")) != evidence.to_dict():
            raise ValueError("evidence package CLI differs from canonical index fixture")

    return {
        "schema": "sidscope.release_1_2_closure_verification.v1",
        "status": "pass",
        "contract_count": len(registry.contracts),
        "declared_dependency_count": sum(
            len(descriptor.dependencies) for descriptor in registry.contracts
        ),
        "canonical_pipeline_artifact_count": len(evidence_rows) + 1,
        "sdk_version": "0.1.0",
        "adapter_id": capabilities.adapter_id,
        "cli_commands": [
            "adapter preflight",
            "contract list/show/validate",
            "trace validate",
            "evaluate",
            "verify",
            "evidence package",
        ],
        "legacy_payload_schema": trace.to_dict()["payload_schema"],
    }


def main() -> None:
    result = verify_closure()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
