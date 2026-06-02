"""Tests for field spec extraction."""
import pytest
from typing import Annotated, Optional

from pydantic_gsheets.exceptions import SchemaError
from pydantic_gsheets.core.descriptors import GSIndex, GSRequired, GSFormat, GSReadonly
from pydantic_gsheets.core.field_spec import _extract_field_specs, _max_index
from pydantic_gsheets.core.row import SheetRow


class SimpleModel(SheetRow):
    name: Annotated[str, GSIndex(0), GSRequired()]
    age: Annotated[int, GSIndex(1)]
    email: Annotated[str, GSIndex(2), GSRequired(), GSFormat("TEXT")]


def test_extract_basic():
    specs = _extract_field_specs(SimpleModel)
    assert set(specs) == {"name", "age", "email"}
    assert specs["name"].index == 0
    assert specs["name"].required is not None
    assert specs["age"].index == 1
    assert specs["age"].required is None
    assert specs["email"].fmt is not None
    assert specs["email"].fmt.number_format_type == "TEXT"


def test_duplicate_index_raises():
    class DupModel(SheetRow):
        a: Annotated[str, GSIndex(0)]
        b: Annotated[str, GSIndex(0)]

    with pytest.raises(SchemaError, match="Duplicate"):
        _extract_field_specs(DupModel)


def test_auto_index_assignment():
    class AutoModel(SheetRow):
        x: str
        y: str
        z: str

    specs = _extract_field_specs(AutoModel)
    assert specs["x"].index == 0
    assert specs["y"].index == 1
    assert specs["z"].index == 2


def test_max_index():
    specs = _extract_field_specs(SimpleModel)
    assert _max_index(specs) == 2


def test_max_index_empty():
    assert _max_index({}) == -1


def test_readonly_flag():
    class RoModel(SheetRow):
        a: Annotated[str, GSIndex(0), GSReadonly()]

    specs = _extract_field_specs(RoModel)
    assert specs["a"].readonly is True
