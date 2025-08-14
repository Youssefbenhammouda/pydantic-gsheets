# Drive File Helpers

Utilities for working with Google Drive links stored in sheet cells.



## `DriveFile`
Pydantic model representing a file stored in Google Drive.

| Field | Type | Description |
| --- | --- | --- |
| `url` | `str | None` | Original value from the cell. Supports `=IMAGE()` formulas. |
| `file_id` | `str | None` | Extracted Drive file identifier. |
| `local_path` | `str | None` | Path where the file was downloaded. |
| `meta` | `dict` | Optional metadata returned by the Drive API. |
