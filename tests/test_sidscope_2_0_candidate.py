import json

from tools.verify_sidscope_2_0_candidate import main, verify


def test_engineering_candidate_is_frozen_but_not_certified():
    result = verify()
    assert result["status"] == "pass"
    assert result["package_version"] == "1.7.0.dev0"
    assert result["adapter_sdk_version"] == "1.0.0"
    assert result["python_facade_symbol_count"] == 39
    assert result["engineering_ready"] is True
    assert result["certification_ready"] is False
    assert result["certification_blockers"] == ["F09"]
    assert result["excluded_candidates"] == ["N09", "N10"]
    assert result["release_authorized"] is False


def test_cli_blocks_certification_without_changing_acceptance(capsys):
    assert main(["--require-engineering-ready"]) == 0
    capsys.readouterr()
    assert main(["--require-certification-ready"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["pending_acceptance"] == ["independent_user_actual_use"]
