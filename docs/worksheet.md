# Worksheet Interaction

API for representing Google Sheet tabs as typed models and reading/writing
row data.

## Errors and Annotation Markers

### `RequiredValueError`
Raised when a field marked as required is empty when reading or writing.

### `GSIndex`
`GSIndex(index: int)` marks the zero-based column position of a field
relative to the worksheet's `start_column`.

### `GSRequired`
Marks a field as mandatory. Missing values raise `RequiredValueError` on
read and abort writes.

### `GSParse`
`GSParse(func)` applies `func(value)` to a cell before model construction.
Useful for custom parsing such as converting strings to numbers or booleans.

### `GSFormat`
Defines the desired number format for a column. Example:
`GSFormat('DATE_TIME', 'dd-MM-yyyy HH:mm')`.
Apply formats using `GoogleWorkSheet.apply_formats_for_model()`.

### `GSReadonly`
Indicates that the field should not be written back to the sheet.

## `SheetRow`
Base class for typed rows. Subclass it and annotate fields with
`typing.Annotated` using the markers above. Instances are bound to a
`GoogleWorkSheet` and row number when read or appended.

> Support for advanced Google Sheets functionalities (such as chips) will be added in the future. For now, use [DriveFile](../drive_types).
### Properties
- `row_number` – absolute row number within the sheet (1-based).
- `worksheet` – the `GoogleWorkSheet` instance the row is bound to.

### Methods
- `save()` – persist changes for the bound row.
- `reload()` – refresh the instance from the sheet.

## `GoogleWorkSheet`
Wrapper around a single worksheet (tab) that streams rows as `SheetRow`
instances and writes changes back.

### Constructor
`GoogleWorkSheet(model, service, spreadsheet_id, sheet_name, *, start_row=2, has_headers=True, start_column=0, require_write=False, drive_service=None)`

| Parameter | Type | Description |
| --- | --- | --- |
| `model` | `Type[SheetRow]` | The Pydantic row model associated with this sheet. |
| `service` | Sheets `Resource` | Authenticated Sheets API client. |
| `spreadsheet_id` | `str` | ID of the spreadsheet. |
| `sheet_name` | `str` | Name of the worksheet tab. |
| `start_row` | `int` | First row containing data (1-based). |
| `has_headers` | `bool` | Whether the sheet has a header row. |
| `start_column` | `int` | Column offset (0 = column A). |
| `require_write` | `bool` | If `True`, verify write permissions on initialization. |
| `drive_service` | Drive `Resource` or `None` | Enables Drive file predownload. |

### Methods

- `rows(*, refresh=False, skip_rows_missing_required=True)` → generator of
  row instances. Set `refresh=True` to re-read the sheet.
- `get(row_number, *, use_cache=True, refresh=False, skip_rows_missing_required=True)` → return a specific row or
  `None` when required values are missing.
- `saveRow(inst)` → save a row instance or by row number.
- `saveRows(rows)` → intended bulk save helper (currently a placeholder).
- `clear_cache()` → clear in-memory row cache.
- `apply_formats_for_model()` → apply `GSFormat` markers to all columns.
- `write_rows(instances)` → bulk write multiple `SheetRow` objects. Unbound
  rows are appended to the end of the sheet.
- `get_last_row_number()` → best-effort detection of the final populated row.