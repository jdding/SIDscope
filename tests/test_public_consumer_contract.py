import json
from pathlib import Path
import pytest
import sidscope
from tools.sidscope_public_consumer import verify

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/reproducibility/sidscope_public_consumer_contract.v1.json"


def test_old_style_consumer_executes_all_curated_symbols():
    assert len(verify(ROOT / "examples", CONTRACT)["curated_symbols_exercised"]) == 39


def test_unreviewed_product_version_is_not_implicitly_compatible(monkeypatch):
    monkeypatch.setattr(sidscope, "__version__", "3.0.0")
    with pytest.raises(AssertionError, match="unsupported consumer version"):
        verify(ROOT / "examples", CONTRACT)


def test_default_or_required_parameter_mutation_fails(monkeypatch):
    def changed(path, *, now_required):
        return None
    monkeypatch.setattr(sidscope, "load_trace_envelope", changed)
    with pytest.raises(AssertionError, match="signature"):
        verify(ROOT / "examples", CONTRACT)


def test_return_semantics_mutation_fails(monkeypatch):
    import inspect
    changed = lambda value: b"wrong"
    changed.__signature__ = inspect.signature(sidscope.canonical_json_bytes)
    monkeypatch.setattr(sidscope, "canonical_json_bytes", changed)
    with pytest.raises(AssertionError):
        verify(ROOT / "examples", CONTRACT)


def test_error_code_mutation_fails(monkeypatch):
    import inspect
    def changed(*args, **kwargs):
        raise sidscope.AdapterPluginError("silently_changed_code", "bad")
    changed.__signature__ = inspect.signature(sidscope.preflight_adapter_plugin)
    monkeypatch.setattr(sidscope, "preflight_adapter_plugin", changed)
    with pytest.raises(AssertionError):
        verify(ROOT / "examples", CONTRACT)
