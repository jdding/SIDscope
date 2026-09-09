"""The standalone scale harness must fail closed without instrumenting runtime."""
import json
import subprocess
from types import SimpleNamespace

import pytest
from tools import benchmark_sidscope_local_workflows as benchmark


@pytest.mark.parametrize("kind", ["json", "csv", "parquet", "evaluate"])
def test_small_scale_cell_records_correctness_and_resources(kind):
    result = benchmark.worker(10, kind)
    assert result["status"] == "pass" and result["rows"] == 10
    assert result["input_bytes"] > 0 and result["output_bytes"] > 0
    assert result["process_peak_rss_bytes"] > 0
    assert result["phase_seconds"] and result["nfe"] is None


@pytest.mark.parametrize("failure", ["timeout", "rss", "exit", "source"])
def test_matrix_does_not_promote_failed_cells(tmp_path, monkeypatch, failure):
    snapshots = iter([{"source": "before"}, {"source": "after" if failure == "source" else "before"}])
    monkeypatch.setattr(benchmark, "source_hashes", lambda: next(snapshots))
    def run(*args, **kwargs):
        assert kwargs["timeout"] == 3
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args[0], 3)
        cell = {"status": "pass", "kind": "json", "rows": 10,
                "process_peak_rss_bytes": 2 * 1048576 if failure == "rss" else 1}
        return SimpleNamespace(returncode=2 if failure == "exit" else 0,
                               stdout=json.dumps(cell), stderr="")
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    result = benchmark.run_matrix(tmp_path / "profile_output", [10], ["json"], 3, 1)
    assert result["status"] == "fail"
    assert json.loads((tmp_path / "profile_output/result.json").read_text()) == result
