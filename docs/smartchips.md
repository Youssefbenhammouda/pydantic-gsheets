# Smart Chips

Smart chips are rich, interactive cells in Google Sheets that can link to Drive
files, people, calendar events, YouTube videos, and places. `pydantic-gsheets`
parses chips on read and emits them on write where supported.

## Supported Types

| Class | Readable | Writable | Description |
|---|---|---|---|
| `fileSmartChip` / `FileSmartChip` | ✅ | ✅ | Google Drive file link |
| `peopleSmartChip` / `PeopleSmartChip` | ✅ | ✅ | Person / email chip |
| `eventSmartChip` / `EventSmartChip` | ✅ | ❌ | Calendar event (read-only) |
| `placeSmartChip` / `PlaceSmartChip` | ✅ | ❌ | Location (read-only) |
| `youtubeSmartChip` / `YouTubeSmartChip` | ✅ | ❌ | YouTube video (read-only) |
| `richLinkProperties` / `RichLinkProperties` | ✅ | ✅ | Generic rich link |

Attempting to write a read-only chip type raises `NotImplementedError`.

## Writing Smart Chips

Write access to Drive file chips requires the `drive.file`, `drive.readonly`,
or `drive` OAuth scope. These are included in `DEFAULT_SCOPES`.

## Declaring Smart Chip Fields

Use `GS_SMARTCHIP` (or its alias `GSSmartChip`) as an annotation marker on a
field typed as `SmartChips`:

```python
from pydantic_gsheets import SheetRow, GSIndex, GSRequired, GS_SMARTCHIP
from pydantic_gsheets.types.smart_chips import SmartChips, peopleSmartChip, fileSmartChip
from typing import Annotated

class MyRow(SheetRow):
    owner_and_file: Annotated[
        SmartChips,
        GS_SMARTCHIP("@ owns @", smartchips=[peopleSmartChip, fileSmartChip]),
        GSIndex(0),
        GSRequired(),
    ]
```

The `format_text` string uses `@` as a placeholder for each chip in order.
Use `\@` for a literal `@` character.

## Reading Smart Chips

When a row is read, the field will be a `SmartChips` instance:

```python
for row in ws.rows():
    chips = row.owner_and_file
    print(chips.display_text)       # raw cell text
    print(chips.chipRuns[0].email)  # peopleSmartChip
    print(chips.chipRuns[1].uri)    # fileSmartChip
```

## Writing Smart Chips

Assign a `SmartChips` instance and call `save()`:

```python
from pydantic_gsheets.types.smart_chips import SmartChips, peopleSmartChip, fileSmartChip

row.owner_and_file = SmartChips(
    format_text="@ owns @",
    chipRuns=[
        peopleSmartChip(email="alice@example.com"),
        fileSmartChip(uri="https://drive.google.com/file/d/FILE_ID"),
    ],
)
row.save()
```

## Class Reference

### `smartChip` (base)
Abstract base for all chip types. Defines `__fieldName__` class variable and
`_to_dict()` method.

### `richLinkProperties` / `RichLinkProperties`
- `uri: str` — the link URI.

### `personProperties`
- `email: str`
- `display_format: displayFormat` — `DEFAULT`, `LAST_NAME_COMMA_FIRST_NAME`, or `EMAIL`.

### `peopleSmartChip` / `PeopleSmartChip`
Subclass of `personProperties`.

### `fileSmartChip` / `FileSmartChip`
Subclass of `richLinkProperties`. The only writable rich-link chip type.

### `eventSmartChip`, `placeSmartChip`, `youtubeSmartChip`
Read-only subclasses of `richLinkProperties`. `_to_dict()` raises `NotImplementedError`.

### `SmartChips` (also `smartChips`)
Container returned when reading a smart chip field.
- `display_text: str | None` — raw cell text.
- `format_text: str | None` — the `@`-pattern format string.
- `chipRuns: list[smartChip]` — parsed chip objects in order.

### `GS_SMARTCHIP` / `GSSmartChip`
Annotation marker dataclass.
- `format_text: str` — `@`-pattern string. Default `"@"`.
- `smartchips: list[type[smartChip]]` — chip types in the same order as `@` tokens.

### `SmartChipConfig` (also `smartchipConf`)
Internal Pydantic model storing parsed chip config per field. Not part of
the public annotation API.
