"""Tests for SheetRow behaviour (no real API calls)."""
import pytest
from typing import Annotated
from pydantic_gsheets.core.row import SheetRow
from pydantic_gsheets.core.descriptors import GSIndex, GSRequired, GSTreatDashAsEmpty
from pydantic_gsheets.exceptions import UnboundRowError, RequiredValueError


class SampleRow(SheetRow):
    username: Annotated[str, GSIndex(0), GSRequired()]
    age: Annotated[int, GSIndex(1)]


def test_save_unbound_raises_unbound_row_error():
    row = SampleRow(username="alice", age=30)
    with pytest.raises(UnboundRowError):
        row.save()


def test_reload_unbound_raises_unbound_row_error():
    row = SampleRow(username="alice", age=30)
    with pytest.raises(UnboundRowError):
        row.reload()


def test_specs_cached():
    s1 = SampleRow._specs()
    s2 = SampleRow._specs()
    assert s1 is s2


def test_row_number_property_raises_when_unbound():
    row = SampleRow(username="bob", age=25)
    with pytest.raises(UnboundRowError):
        _ = row.row_number


def test_dash_not_empty_by_default():
    """Without GSTreatDashAsEmpty, '-' should pass through as a string value."""
    class NoOptIn(SheetRow):
        val: Annotated[str, GSIndex(0)]

    specs = NoOptIn._specs()
    assert specs["val"].treat_dash_as_empty is False


def test_dash_as_empty_with_opt_in():
    """With GSTreatDashAsEmpty(), '-' should be treated as empty."""
    class WithOptIn(SheetRow):
        val: Annotated[str, GSIndex(0), GSTreatDashAsEmpty()]

    specs = WithOptIn._specs()
    assert specs["val"].treat_dash_as_empty is True


def test_to_sheet_values_required_empty_raises():
    row = SampleRow(username="", age=30)
    with pytest.raises(RequiredValueError):
        row._to_sheet_values()
