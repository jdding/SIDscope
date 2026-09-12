from pathlib import Path
import pytest
from tools.sidscope_local_release_record import verify_record, ReleaseRecordError, source_snapshot
from tools import sidscope_local_release_record as record
from tools.sidscope_release_profiles import ReleaseProfileError


def test_untrusted_record_fails_before_archive_is_read(tmp_path):
    record = tmp_path / "record.json"
    record.write_text('{}')
    with pytest.raises(ReleaseProfileError) as caught:
        verify_record(record, expected_record_sha256="0"*64, archive_path=tmp_path / "must-not-execute.zip", profile="runtime")
    assert caught.value.code == "archive_digest_mismatch"


def test_source_snapshot_binds_head_dirty_and_exact_bytes():
    snapshot = source_snapshot()
    assert len(snapshot["head"]) == 40
    assert isinstance(snapshot["dirty"], bool)
    assert "src/sidscope/workflows.py" in snapshot["public_files"]
    assert len(snapshot["public_files"]["src/sidscope/workflows.py"]) == 64


def test_exact_source_builder_runs_and_binds_delivery_performance():
    source = Path(record.__file__).read_text()
    assert '"tools/check_sidscope_current_performance.py", "--require-delivery"' in source
    assert '"format": "sidscope.local_release_record.v2"' in source
    assert '"measurement": performance_payload' in source
    assert '"source_snapshot_sha256": before["content_sha256"]' in source


def test_record_without_bound_passing_performance_is_rejected(tmp_path, monkeypatch):
    candidate = {"format":"sidscope.local_release_record.v2","status":"pass",
        "source":{"content_sha256":"a"*64},"archives":[{"profile":"runtime","archive_sha256":"b"*64}],
        "tests":[{"returncode":0,"source_snapshot_sha256":"a"*64}],"performance":{}}
    monkeypatch.setattr(record,"verify_archive_digest",lambda *args:None)
    monkeypatch.setattr(record,"read_archive_profile",lambda *args,**kwargs:None)
    monkeypatch.setattr(record,"load_json",lambda *args,**kwargs:candidate)
    with pytest.raises(ReleaseRecordError) as error:
        verify_record(tmp_path/"record.json",expected_record_sha256="c"*64,archive_path=tmp_path/"runtime.zip",profile="runtime")
    assert error.value.code == "unbound_performance_evidence"
