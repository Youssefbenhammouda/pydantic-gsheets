# Smart Chips Integration in pydantic-gsheets

Smart chips are a powerful feature in `pydantic-gsheets` that allow you to represent rich, interactive data within Google Sheets. These chips can include links to Google services, such as Drive files, YouTube videos, Calendar events, and more. Below is an extensive guide to understanding and using smart chips in your projects.

## Overview

Smart chips are implemented using the `smartChip` base class and its various subclasses, such as `richLinkProperties`, `personProperties`, and others. These classes define the structure and behavior of different types of chips, enabling seamless integration with Google Sheets.

## Supported Smart Chips

The following types of smart chips are supported:

- **Rich Link Chips**: Represent links to external resources, such as Google Drive files.
- **Person Chips**: Represent individuals with associated email addresses and display formats.
- **Event Chips**: Represent calendar events (read-only).
- **Place Chips**: Represent locations (read-only).
- **YouTube Chips**: Represent YouTube videos (read-only).

## Writing Smart Chips

While the API can read links to various Google services (like YouTube or Calendar), only links to Google Drive files can be written as chips.

### Authorization Requirements

Writing Drive file chips requires your application to be authorized with at least one of the following OAuth scopes:

- `drive.file`
- `drive.readonly`
- `drive`

Ensure that your application is properly authorized to avoid any issues when writing Drive file chips.

## Example Usage

Here is an example of how to define and use smart chips in a Google Sheet:

```python
from pydantic_gsheets.types import peopleSmartChip, fileSmartChip, smartChips, GS_SMARTCHIP
from pydantic_gsheets import GoogleWorkSheet, SheetRow
from typing import Annotated

class CustomRow(SheetRow):
    field1: Annotated[
        smartChips,
        GS_SMARTCHIP(
            "@ owner of @",
            smartchips=[peopleSmartChip, fileSmartChip]
        )
    ]

# Initialize the worksheet
sheet = GoogleWorkSheet(
    model=CustomRow,
    service=svc,  # Your authenticated Sheets service
    spreadsheet_id="your_spreadsheet_id",
    sheet_name="Sheet1"
)

# Fetch and manipulate rows
data = list(sheet.rows(skip_rows_missing_required=True))
data[0].name = smartChips(display_text="John Doe", format_text="@")
data[0].save()
```

## Limitations

- Only Google Drive file chips can be written. Other types of chips, such as YouTube or Calendar event chips, are read-only.
- Ensure proper authorization to avoid runtime errors.


## Smart Chip Object Definitions

### `smartChip`
Base class for all smart chip types. It is an abstract class that defines the common structure for smart chips.

### `richLinkProperties`
Represents a rich link chip with a URI.

#### Properties
- `uri` – The URI of the rich link.

#### Methods
- `_to_dict()` – Converts the chip to a dictionary representation.

### `personProperties`
Represents a person chip with an email and display format.

#### Properties
- `email` – The email address of the person.
- `display_format` – The display format for the person. Options include:
  - `DEFAULT`
  - `LAST_NAME_COMMA_FIRST_NAME`
  - `EMAIL`

#### Methods
- `_to_dict()` – Converts the chip to a dictionary representation.

### `peopleSmartChip`
A subclass of `personProperties` for representing people chips.

### `fileSmartChip`
A subclass of `richLinkProperties` for representing file chips.

### `eventSmartChip`
A subclass of `richLinkProperties` for representing event chips. Writing is not supported.

#### Methods
- `_to_dict()` – Raises `noWriteSupport` as writing is not supported.

### `placeSmartChip`
A subclass of `richLinkProperties` for representing place chips. Writing is not supported.

#### Methods
- `_to_dict()` – Raises `noWriteSupport` as writing is not supported.

### `youtubeSmartChip`
A subclass of `richLinkProperties` for representing YouTube chips. Writing is not supported.

#### Methods
- `_to_dict()` – Raises `noWriteSupport` as writing is not supported.

### `smartChips`
Represents a collection of smart chips with display text and format.

#### Properties
- `display_text` – The display text for the rich link.
- `format_text` – The format text for the smart chip.
- `chipRuns` – A list of `smartChip` objects.

### `GS_SMARTCHIP`
Defines the format text and associated smart chips for a display text.

#### Properties
- `format_text` – The format text for the smart chip.
- `smartchips` – A list of smart chip types associated with the display text.

### `smartchipConf`
Configuration class for smart chips.

#### Properties
- `is_smartchips` – Boolean indicating if smart chips are enabled.
- `smartchips` – A list of smart chip types.
- `format_text` – The format text for the smart chip.

