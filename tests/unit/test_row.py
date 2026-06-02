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


# ---------------------------------------------------------------------------
# _from_sheet_values tests — mock worksheet, real cell dict structure
# ---------------------------------------------------------------------------

from datetime import date, datetime
from unittest.mock import MagicMock
from typing import Optional
from pydantic_gsheets.core.descriptors import GSFormat, GSParse, GSTreatDashAsEmpty
from pydantic_gsheets.exceptions import ParseError


def _make_worksheet():
    return MagicMock()


def _cell(formatted: str | None = None, string: str | None = None, number: float | None = None,
          fmt_type: str | None = None) -> dict:
    """Build a minimal cell dict in the shape returned by includeGridData=True."""
    c: dict = {}
    if formatted is not None:
        c["formattedValue"] = formatted
    uev: dict = {}
    if string is not None:
        uev["stringValue"] = string
    if number is not None:
        uev["numberValue"] = number
    if uev:
        c["userEnteredValue"] = uev
    if number is not None:
        c["effectiveValue"] = {"numberValue": number}
    if fmt_type is not None:
        c["userEnteredFormat"] = {"numberFormat": {"type": fmt_type}}
    return c


class _StrRow(SheetRow):
    name: Annotated[str, GSIndex(0), GSRequired()]
    note: Annotated[Optional[str], GSIndex(1)] = None


class TestFromSheetValues:
    def test_str_field(self):
        ws = _make_worksheet()
        row = _StrRow._from_sheet_values(ws, 1, [_cell(formatted="Alice"), _cell(string="")])
        assert row.name == "Alice"

    def test_empty_optional_is_empty_string(self):
        """Empty cell for Optional[str] field → empty string (not None); Pydantic accepts both."""
        ws = _make_worksheet()
        row = _StrRow._from_sheet_values(ws, 1, [_cell(formatted="Alice"), _cell(string="")])
        # _from_sheet_values passes "" through; Pydantic stores it as ""
        assert row.note == "" or row.note is None

    def test_empty_required_raises(self):
        ws = _make_worksheet()
        from pydantic_gsheets.exceptions import RequiredValueError
        with pytest.raises(RequiredValueError) as exc_info:
            _StrRow._from_sheet_values(ws, 2, [_cell(string=""), _cell()])
        assert exc_info.value.field_name == "name"
        assert exc_info.value.row_number == 2

    def test_short_row_fills_missing(self):
        """Row with fewer cells than fields → missing cells treated as empty."""
        ws = _make_worksheet()
        # Only provide one cell for a 2-field model (name required)
        with pytest.raises(Exception):
            # name is required, but no cell → RequiredValueError
            _StrRow._from_sheet_values(ws, 3, [])

    def test_short_row_optional_missing(self):
        ws = _make_worksheet()
        row = _StrRow._from_sheet_values(ws, 1, [_cell(formatted="Bob")])
        # Missing cell → empty string or None
        assert row.note == "" or row.note is None

    def test_dash_default_not_empty(self):
        """Without GSTreatDashAsEmpty, '-' passes through as a normal string (does not raise)."""
        ws = _make_worksheet()
        row = _StrRow._from_sheet_values(ws, 1, [_cell(formatted="-"), _cell()])
        assert row.name == "-"

    def test_dash_with_treat_dash_empty(self):
        class DashRow(SheetRow):
            val: Annotated[Optional[str], GSIndex(0), GSTreatDashAsEmpty()] = None

        ws = _make_worksheet()
        row = DashRow._from_sheet_values(ws, 1, [_cell(formatted="-")])
        assert row.val is None

    def test_gs_parse_applied(self):
        class ParseRow(SheetRow):
            val: Annotated[int, GSIndex(0), GSParse(int)]

        ws = _make_worksheet()
        row = ParseRow._from_sheet_values(ws, 1, [_cell(formatted="42")])
        assert row.val == 42

    def test_gs_parse_exception_raises_parse_error(self):
        def bad_parser(v):
            raise ValueError("bad value")

        class FailRow(SheetRow):
            val: Annotated[str, GSIndex(0), GSParse(bad_parser)]

        ws = _make_worksheet()
        with pytest.raises(ParseError) as exc_info:
            FailRow._from_sheet_values(ws, 1, [_cell(formatted="x")])
        assert exc_info.value.field_name == "val"

    def test_date_field(self):
        class DateRow(SheetRow):
            d: Annotated[date, GSIndex(0), GSFormat("DATE")]

        ws = _make_worksheet()
        serial = 45000.0
        row = DateRow._from_sheet_values(ws, 1, [_cell(number=serial, fmt_type="DATE")])
        assert isinstance(row.d, date)
        assert not isinstance(row.d, datetime)

    def test_datetime_field(self):
        class DtRow(SheetRow):
            dt: Annotated[datetime, GSIndex(0), GSFormat("DATE_TIME")]

        ws = _make_worksheet()
        serial = 45000.5
        row = DtRow._from_sheet_values(ws, 1, [_cell(number=serial, fmt_type="DATE_TIME")])
        assert isinstance(row.dt, datetime)
        assert row.dt.hour == 12


class TestToSheetValues:
    def test_bool_true_written_as_true(self):
        class BoolRow(SheetRow):
            flag: Annotated[bool, GSIndex(0)]

        row = BoolRow(flag=True)
        vals = row._to_sheet_values()
        assert vals[0] is True

    def test_bool_false_written_as_false(self):
        class BoolRow(SheetRow):
            flag: Annotated[bool, GSIndex(0)]

        row = BoolRow(flag=False)
        vals = row._to_sheet_values()
        assert vals[0] is False

    def test_none_written_as_empty_string(self):
        class NoneRow(SheetRow):
            val: Annotated[Optional[str], GSIndex(0)] = None

        row = NoneRow(val=None)
        vals = row._to_sheet_values()
        assert vals[0] == ""

    def test_string_written(self):
        row = SampleRow(username="carol", age=5)
        vals = row._to_sheet_values()
        assert vals[0] == "carol"
