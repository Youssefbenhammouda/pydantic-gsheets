# pydantic-gsheets

A Python library for sending and receiving data from Google Sheets using [Pydantic](https://docs.pydantic.dev/) models.

## Features

- **Type-safe data mapping** — Convert Google Sheets rows into strongly typed Pydantic models.
- **Validation** — Ensure incoming data meets schema requirements before processing.
- **Serialization** — Write validated models back to Sheets easily.
- **Batch operations** — Read and write large ranges in a single request.
- **Built on official Google Sheets API** — Reliable and well-maintained foundation.



# Usage

## Example: Inventory sheet with typed rows and optional Drive image download

This example shows how to:

* authorize with **User OAuth**
* map a sheet to a **typed Pydantic row model**
* **stream rows** and (optionally) pre-download Drive images
* **update** a row and **append** a new one

```python
from typing import Annotated, Optional
from pydantic_gsheets import (
    GoogleWorkSheet, SheetRow,
    GSIndex, GSRequired, GSParse, 
    GSFormat, DriveFile, GSDrive, 
    get_drive_service, AuthConfig, 
    AuthMethod, get_sheets_service
)

# --- Auth (User OAuth). Make sure your OAuth client and consent screen are set up.
sheets = get_sheets_service(AuthConfig(
    method=AuthMethod.USER_OAUTH,
    client_secrets_file="client_secret.json",
    token_cache_file=".tokens/sheets_token.json",
))
# For Drive-backed columns (optional), you also need a Drive client (same auth).
drive = get_drive_service(AuthConfig(
    method=AuthMethod.USER_OAUTH,
    client_secrets_file="client_secret.json",
    token_cache_file=".tokens/sheets_token.json",
))

# --- Small parsers for typed columns
def parse_bool(v):
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y"): return True
    if s in ("false", "0", "no", "n"): return False
    raise ValueError(f"Not a bool: {v}")

def parse_float(v):
    return float(str(v).replace(",", "."))

# --- Define your sheet row model (adjust GSIndex to match your columns)
class InventoryRow(SheetRow):
    sku:      Annotated[str,   GSIndex(0), GSRequired()]
    name:     Annotated[str,   GSIndex(1), GSRequired()]
    price:    Annotated[float, GSIndex(2), GSParse(parse_float), GSFormat("NUMBER", "0.00")]
    in_stock: Annotated[bool,  GSIndex(3), GSParse(parse_bool)]
    photo:    Annotated[
        Optional[DriveFile],
        GSIndex(4),
        # If the cell contains a Drive URL (or an =IMAGE("...drive...")), predownload it:
        GSDrive(
            predownload=True,
            dest_dir="downloads/photos",
            filename_template="{row}_{field}_{id}.{ext}",  # e.g., 12_photo_1AbCdEf.png
            export_mime=None,     # set e.g. "image/png" for Google Drawings export
            overwrite=False,
        )
    ]

# --- Open a worksheet bound to your model
sheet = GoogleWorkSheet(
    model=InventoryRow,               # the row type for this sheet
    service=sheets,                   # Sheets API client
    spreadsheet_id="<YOUR-SPREADSHEET-ID>",
    sheet_name="Inventory",
    start_row=2,                      # data starts at row 2 (headers on row 1)
    has_headers=True,
    drive_service=drive,              # optional; enables GSDrive(predownload=...)
)

# --- Read and iterate typed rows
for row in sheet.read_rows():
    print(row.sku, row.name, row.price, row.in_stock,
          getattr(row.photo, "local_path", None))  # path if predownloaded

# --- Update an existing row and save it back
first = next(sheet.read_rows())
first.in_stock = False
first.save()  # writes the row back to the same line

# --- Append a brand-new row
new_item = InventoryRow(
    sku="SKU-12345",
    name="Widget Mini",
    price=19.99,
    in_stock=True,
    photo=None,  # or a Drive URL in the cell — it will be parsed on next read
)
sheet.append_row(new_item)  # binds new_item to its newly created row number

# --- (Optional) apply number/date formats defined via GSFormat annotations
sheet.apply_formats_for_model(InventoryRow)
```

### Notes

* **Column indices:** `GSIndex(0)` is the **first logical column** of your data region (i.e., relative to `start_column`). Adjust to match your sheet.
* **Scopes:** if you use `DriveFile` (with `GSDrive`), your OAuth scopes must include Drive read access (e.g., `drive.readonly`) in addition to Sheets.
* **Predownload:** `GSDrive(predownload=True)` will download files at **read time** if `drive_service` is provided. If you omit `drive_service`, the field still parses as a `DriveFile`, but no auto-download happens.
* **Readonly cells:** fields marked with `GSReadonly()` will never be overwritten by `save()`/`append_row()`.
* **Formatting:** `GSFormat` sets Google Sheets column number formats through `apply_formats_for_model(...)` – run it once after creating/binding a sheet.


