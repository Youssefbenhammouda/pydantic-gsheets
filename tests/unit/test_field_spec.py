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


def test_mixed_explicit_and_auto_index():
    """Explicit GSIndex + auto-index should interleave correctly."""
    from pydantic_gsheets.core.descriptors import GSTreatDashAsEmpty, GSParse
    class MixedModel(SheetRow):
        x: Annotated[str, GSIndex(0)]
        y: str                          # auto → 1
        z: Annotated[str, GSIndex(5)]
        w: str                          # auto → 6

    specs = _extract_field_specs(MixedModel)
    assert specs["x"].index == 0
    assert specs["y"].index == 1
    assert specs["z"].index == 5
    assert specs["w"].index == 6


def test_treat_dash_as_empty_extracted():
    from pydantic_gsheets.core.descriptors import GSTreatDashAsEmpty
    class DashModel(SheetRow):
        name: Annotated[str, GSIndex(0), GSTreatDashAsEmpty()]

    specs = _extract_field_specs(DashModel)
    assert specs["name"].treat_dash_as_empty is True


def test_gs_parse_stored_in_spec():
    from pydantic_gsheets.core.descriptors import GSParse
    class ParseModel(SheetRow):
        value: Annotated[int, GSIndex(0), GSParse(int)]

    specs = _extract_field_specs(ParseModel)
    assert specs["value"].parser is int


def test_underscore_fields_skipped():
    """Private fields (underscore prefix) must not appear in specs."""
    class PrivModel(SheetRow):
        name: str

    specs = _extract_field_specs(PrivModel)
    # PrivateAttr fields from SheetRow (_worksheet_ref, _row_number_ref) start with _
    assert all(not k.startswith("_") for k in specs)
