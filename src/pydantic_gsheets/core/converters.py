from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

_GSHEETS_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)


def gsheets_to_datetime(sheet_number: float) -> datetime:
    """Convert a Google Sheets serial number to a UTC-aware datetime."""
    return _GSHEETS_EPOCH + timedelta(days=sheet_number)


def gsheets_to_date(sheet_number: float) -> date:
    """Convert a Google Sheets serial number to a date (time component dropped)."""
    return gsheets_to_datetime(sheet_number).date()


def datetime_to_gsheets(d: date | datetime) -> float:
    """Convert a Python date or datetime to a Google Sheets serial number."""
    if isinstance(d, datetime):
        dt = d if d.tzinfo is not None else d.replace(tzinfo=timezone.utc)
    else:
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    delta = dt - _GSHEETS_EPOCH
    return delta.days + delta.seconds / 86400.0


def col_index_to_a1(idx: int) -> str:
    """Convert a 0-based column index to A1 column notation (0→'A', 26→'AA')."""
    if idx < 0:
        raise ValueError("Column index must be >= 0")
    result = ""
    idx += 1
    while idx:
        idx, remainder = divmod(idx - 1, 26)
        result = chr(65 + remainder) + result
    return result
