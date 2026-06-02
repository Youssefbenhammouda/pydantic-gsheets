from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Naive epoch — Google Sheets serial numbers have no timezone concept.
# We use naive datetimes throughout so that round-trips preserve equality
# for users who work with naive datetimes (the common case).
_GSHEETS_EPOCH_NAIVE = datetime(1899, 12, 30)
_GSHEETS_EPOCH_AWARE = datetime(1899, 12, 30, tzinfo=timezone.utc)


def gsheets_to_datetime(sheet_number: float) -> datetime:
    """Convert a Google Sheets serial number to a naive datetime.

    Returns a naive (no tzinfo) datetime. Microseconds are not preserved
    as Sheets serial numbers have ~1-second resolution.
    """
    return _GSHEETS_EPOCH_NAIVE + timedelta(days=sheet_number)


def gsheets_to_date(sheet_number: float) -> date:
    """Convert a Google Sheets serial number to a date (time component dropped)."""
    return gsheets_to_datetime(sheet_number).date()


def datetime_to_gsheets(d: date | datetime) -> float:
    """Convert a Python date or datetime to a Google Sheets serial number."""
    if isinstance(d, datetime):
        if d.tzinfo is not None:
            # Aware datetime: subtract aware epoch
            delta = d - _GSHEETS_EPOCH_AWARE
        else:
            # Naive datetime: subtract naive epoch
            delta = d - _GSHEETS_EPOCH_NAIVE
    else:
        naive_dt = datetime(d.year, d.month, d.day)
        delta = naive_dt - _GSHEETS_EPOCH_NAIVE
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
