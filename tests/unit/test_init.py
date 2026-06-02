"""Smoke-test: every name in __all__ must be importable from the package root."""
import importlib


def test_all_exports_importable():
    pkg = importlib.import_module("pydantic_gsheets")
    missing = [name for name in pkg.__all__ if not hasattr(pkg, name)]
    assert not missing, f"Names in __all__ but not importable: {missing}"


def test_all_attribute_set():
    import pydantic_gsheets
    assert hasattr(pydantic_gsheets, "__all__")
    assert len(pydantic_gsheets.__all__) > 0
