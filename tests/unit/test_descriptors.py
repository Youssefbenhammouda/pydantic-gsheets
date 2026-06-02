"""Tests for annotation descriptor classes."""
import pytest
from typing import Annotated

from pydantic_gsheets.exceptions import SchemaError
from pydantic_gsheets.core.descriptors import (
    GSIndex, GSRequired, GSParse, GSFormat, GSReadonly, GSTreatDashAsEmpty,
)
from pydantic_gsheets.core.field_spec import _extract_field_specs
from pydantic_gsheets.core.row import SheetRow


def test_gs_index_repr():
    assert repr(GSIndex(3)) == "GSIndex(3)"


def test_gs_index_negative_raises():
    with pytest.raises(ValueError):
        GSIndex(-1)


def test_gs_required_repr():
    assert "GSRequired" in repr(GSRequired())


def test_gs_format_repr():
    assert "DATE_TIME" in repr(GSFormat("DATE_TIME", "dd-MM-yyyy"))


def test_gs_readonly_repr():
    assert repr(GSReadonly()) == "GSReadonly()"


def test_gs_treat_dash_repr():
    assert repr(GSTreatDashAsEmpty()) == "GSTreatDashAsEmpty()"


def test_gs_required_bare_class_raises_schema_error():
    """Using GSRequired (no parens) in Annotated must raise SchemaError at spec extraction time."""
    class BadModel(SheetRow):
        x: Annotated[str, GSRequired]  # bare class, no ()

    with pytest.raises(SchemaError, match="GSRequired must be used as an instance"):
        _extract_field_specs(BadModel)


def test_gs_required_class_getitem_raises():
    with pytest.raises(SchemaError):
        _ = GSRequired[str]


def test_gs_parse_repr():
    assert "int" in repr(GSParse(int))


def test_gs_required_custom_message():
    r = GSRequired("must not be blank")
    assert r.message == "must not be blank"
    assert "must not be blank" in repr(r)


def test_gs_index_zero():
    assert GSIndex(0).index == 0


def test_gs_format_with_pattern():
    f = GSFormat("DATE", "YYYY-MM-DD")
    assert f.number_format_type == "DATE"
    assert f.pattern == "YYYY-MM-DD"
    assert "YYYY-MM-DD" in repr(f)
