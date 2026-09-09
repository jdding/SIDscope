from pathlib import Path
import pytest
from tools.sidscope_local_release_record import verify_record, ReleaseRecordError, source_snapshot
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
