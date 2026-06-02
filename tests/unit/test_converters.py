"""Tests for date/datetime conversion helpers."""
import pytest
from datetime import date, datetime, timezone

from pydantic_gsheets.core.converters import (
    col_index_to_a1, gsheets_to_datetime, gsheets_to_date, datetime_to_gsheets,
)


def test_gsheets_to_datetime_preserves_time():
    """Serial 45000.5 should give 12:00:00, not midnight."""
    dt = gsheets_to_datetime(45000.5)
    assert isinstance(dt, datetime)
    assert dt.hour == 12
    assert dt.minute == 0


def test_gsheets_to_datetime_midnight():
    dt = gsheets_to_datetime(45000.0)
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.second == 0


def test_gsheets_to_date_returns_date():
    d = gsheets_to_date(45000.5)
    assert isinstance(d, date)
    assert not isinstance(d, datetime)


def test_roundtrip():
    original = 45000.75
    dt = gsheets_to_datetime(original)
    back = datetime_to_gsheets(dt)
    assert abs(back - original) < 1e-9


def test_datetime_to_gsheets_naive():
    d = datetime(2023, 1, 1, 0, 0, 0)
    n = datetime_to_gsheets(d)
    assert n > 0


@pytest.mark.parametrize("idx,expected", [
    (0, "A"),
    (1, "B"),
    (25, "Z"),
    (26, "AA"),
    (51, "AZ"),
    (52, "BA"),
    (701, "ZZ"),
])
def test_col_index_to_a1(idx, expected):
    assert col_index_to_a1(idx) == expected


def test_col_index_negative_raises():
    with pytest.raises(ValueError):
        col_index_to_a1(-1)
