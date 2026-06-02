# Worksheet Interaction

API for representing Google Sheet tabs as typed Pydantic models and
reading/writing row data.

## Annotation Markers

Markers are placed inside `Annotated[...]` on `SheetRow` field definitions.

### `GSIndex(index: int)`
Zero-based column position relative to `start_column`. If omitted, columns
are assigned positions in definition order.

```python
name: Annotated[str, GSIndex(0)]
age:  Annotated[int, GSIndex(2)]   # column B is skipped
```

### `GSRequired(message="")`
Field must be non-empty on read and write. Raises `RequiredValueError` when
violated. Must be **instantiated** — `GSRequired()` not `GSRequired`.

### `GSParse(func)`
Apply `func(raw_string)` to the cell value before Pydantic validation.
Useful for custom string-to-type conversions.

### `GSFormat(number_format_type, pattern=None)`
Desired Google Sheets number format for the column (e.g. `"DATE_TIME"`,
`"CURRENCY"`). Applied via `GoogleWorkSheet.apply_formats_for_model()`.

### `GSReadonly()`
Field is never written back to the sheet. Drive link chips and read-only
chip types are marked readonly automatically.

### `GSTreatDashAsEmpty()`
Opt-in: treat the literal string `"-"` as an empty/None value for this
field. Without this marker, `"-"` passes through unchanged.

### `GS_SMARTCHIP(format_text="@", smartchips=[...])`
Declares a field as containing smart chips. See [Smart Chips](smartchips.md).

## Errors

### `RequiredValueError(field_name, row_number)`
Raised when a `GSRequired` field is empty. Carries `.field_name` and
`.row_number` attributes.

### `ParseError(field_name, col_index, cause)`
Raised when a `GSParse` callable throws. Carries `.field_name`,
`.col_index`, and `.__cause__`.

### `UnboundRowError`
Raised when `save()` or `reload()` is called on a row not yet bound to a
worksheet.

### `SchemaError`
Raised at model definition time for invalid annotations (duplicate
`GSIndex`, bare `GSRequired` class without `()`, etc.).

### `RateLimitError` / `TransientAPIError`
Raised after all retry attempts are exhausted (429 and 5xx respectively).

### `RequiredValueSkippedWarning`
`UserWarning` emitted when a row is skipped because a required field is
empty (instead of silently discarding it).

## `SheetRow`

Base class for typed rows. Subclass and annotate fields with `Annotated`.

```python
from pydantic_gsheets import SheetRow, GSIndex, GSRequired, GSFormat
from typing import Annotated
from datetime import datetime

class MyRow(SheetRow):
    username: Annotated[str,      GSIndex(0), GSRequired()]
    age:      Annotated[int,      GSIndex(1)]
    joined:   Annotated[datetime, GSIndex(2), GSFormat("DATE_TIME", "dd-MM-yyyy HH:mm")]
```

### Properties
- `row_number` — absolute 1-based row number in the sheet (raises `UnboundRowError` if not bound).
- `worksheet` — the `GoogleWorkSheet` the row is bound to.

### Methods
- `save()` — write the current instance back to its bound row.
- `reload()` — refresh the instance from the sheet.

## `GoogleWorkSheet[T]`

Generic wrapper around a single worksheet tab.

### Constructor

```python
GoogleWorkSheet(
    model,
    service,          # SheetsClient or raw Resource (deprecated)
    spreadsheet_id,
    sheet_name,
    *,
    start_row=2,
    start_column=0,
    validate_access=True,
)
```

| Parameter | Type | Description |
|---|---|---|
| `model` | `Type[T]` | The `SheetRow` subclass for this sheet. |
| `service` | `SheetsClient` or `Resource` | Authenticated API client. |
| `spreadsheet_id` | `str` | Google Sheets spreadsheet ID. |
| `sheet_name` | `str` | Name of the worksheet tab. |
| `start_row` | `int` | First data row (1-based). Default `2` (assumes a header row). |
| `start_column` | `int` | Column offset (0 = column A). |
| `validate_access` | `bool` | Verify read/write permissions on init. Default `True`. |

### Factory

#### `GoogleWorkSheet.create_sheet(model, service, spreadsheet_id, sheet_name, *, add_column_headers=True, skip_if_exists=True, start_row=2, start_column=0)`
Create a new sheet tab and return a bound `GoogleWorkSheet`. If the tab
already exists and `skip_if_exists=True`, opens the existing tab instead.

### Read Methods

#### `rows(*, refresh=False, skip_rows_missing_required=True, page_size=None)`
Generator yielding all data rows as typed instances. Results are cached;
pass `refresh=True` to re-read from the sheet. Use `page_size` to read
large sheets in chunks (reduces memory usage).

#### `get(row_number, *, use_cache=True, refresh=False, skip_rows_missing_required=True) → T | None`
Fetch a single row by absolute 1-based row number. Returns `None` if a
required field is empty and `skip_rows_missing_required=True`.

### Write Methods

#### `saveRow(inst)` / `saveRows(rows)`
Save one or multiple already-bound row instances.

#### `append_row(instance) → T`
Append an **unbound** `SheetRow` instance as a new row at the end of data.
Binds the instance to its new row number and returns it.

```python
new_row = MyRow(username="alice", age=30, joined=datetime.now())
ws.append_row(new_row)
print(new_row.row_number)  # e.g. 5
```

#### `append_rows(instances) → list[T]`
Append multiple unbound rows in a single `batchUpdate` call.

#### `delete_row(row_number_or_instance, *, shift_up=True)`
Delete a row by number or bound instance. When `shift_up=True` (default)
subsequent rows shift up (Google Sheets native behaviour); the cache is
updated accordingly.

### Other Methods

- `clear_cache()` — discard the in-memory row cache.
- `apply_formats_for_model()` — apply `GSFormat` annotations as column-level number formats.
- `get_last_row_number()` — best-effort detection of the last populated row.

## Date and Datetime Helpers

```python
from pydantic_gsheets import gsheets_to_datetime, gsheets_to_date, datetime_to_gsheets
```

- `gsheets_to_datetime(serial)` → `datetime` (UTC-aware, preserves time)
- `gsheets_to_date(serial)` → `date` (time component dropped)
- `datetime_to_gsheets(d)` → `float` serial number

Fields typed as `datetime` use `gsheets_to_datetime`; fields typed as
`date` use `gsheets_to_date`. The type annotation is the source of truth.

## Retry & Rate Limiting

All API calls go through `SheetsClient` which applies:

- **Token-bucket rate limiter** — 290 req/min (Google's quota is 300/min).
- **Exponential backoff** — retries on 429 / 5xx with jitter.

Tune via `RetryConfig`:

```python
from pydantic_gsheets import SheetsClient, RetryConfig

client = SheetsClient(service, retry_config=RetryConfig(max_attempts=3))
```
