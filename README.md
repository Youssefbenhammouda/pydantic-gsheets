markdown
# pydantic-gsheets  

[![PyPI](https://img.shields.io/pypi/v/pydantic-gsheets)](https://pypi.org/project/pydantic-gsheets/)  
[![Python](https://img.shields.io/pypi/pyversions/pydantic-gsheets)](https://pypi.org/project/pydantic-gsheets/)  
[![License](https://img.shields.io/github/license/youssefbenhammouda/pydantic-gsheets)](./LICENSE)  
[![Docs](https://img.shields.io/badge/docs-online-blue)](https://youssefbenhammouda.github.io/pydantic-gsheets/)  

A Python library for sending and receiving data from Google Sheets using [Pydantic](https://docs.pydantic.dev/) models.

With **pydantic-gsheets**, each row in a Google Sheet maps to a strongly-typed Pydantic model. You can read rows as validated objects and write updates back seamlessly.  

### Features
- Declarative column mapping (`GSIndex`)
- Required fields (`GSRequired`)
- Custom parsing (`GSParse`)
- Number/date/time formatting (`GSFormat`)
- Read-only columns (`GSReadonly`)
- **Smart Chips**: People and Drive file rich links (experimental)
- Bulk read / bulk write helpers

📘 Full documentation: [pydantic-gsheets API reference](https://youssefbenhammouda.github.io/pydantic-gsheets/)

💡 Beginner friendly: you only need basic Python and a Google account.

---

## Installation

Python 3.10+ is recommended.

```bash
pip install pydantic-gsheets
````

If you’re using a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
pip install pydantic-gsheets
```

---

## Google Cloud Setup (One-Time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable these APIs:

   * **Google Sheets API**
   * **Google Drive API** (required for Drive file smart chips or file metadata)
3. Configure an OAuth consent screen (choose *External* for testing).
4. Create OAuth client credentials of type **Desktop** and download the JSON (e.g., `client_secret.json`).
5. Decide on a token cache location (e.g., `.tokens/google.json`). This will be created automatically on first authentication.

---

## Quick Start

```python
from typing import Annotated
from pydantic_gsheets import (
    AuthConfig, AuthMethod, get_sheets_service,
    GoogleWorkSheet, SheetRow,
    GSIndex, GSRequired
)

# 1. Authenticate (first run opens a browser for consent)
svc = get_sheets_service(AuthConfig(
    method=AuthMethod.USER_OAUTH,
    client_secrets_file="client_secret.json",
    token_cache_file=".tokens/google.json",
))

# 2. Define a row model
class UserRow(SheetRow):
    name: Annotated[str, GSRequired()]
    email: Annotated[str, GSRequired()]
    age: Annotated[int]

# 3. Bind to a worksheet (tab)
sheet = GoogleWorkSheet(
    model=UserRow,
    service=svc,
    spreadsheet_id="<SPREADSHEET_ID>",  # replace with your sheet ID
    sheet_name="Users",   # tab title
    start_row=2           # row 1 is headers
)

# 4. Read rows
for row in sheet.rows():
    print(row.name, row.email)

# 5. Append a new row
new_user = UserRow(name="Alice", email="alice@example.com", age=30)
sheet.saveRow(new_user)
```

---

## Core Concepts

| Marker                                | Purpose                                               |
| ------------------------------------- | ----------------------------------------------------- |
| `GSIndex(i)`                          | Zero-based column index relative to `start_column`.   |
| `GSRequired()`                        | Field must not be empty on read or write.             |
| `GSParse(func)`                       | Apply `func(raw_value)` before validation.            |
| `GSFormat(type, pattern?)`            | Assigns Google Sheets number/date format.             |
| `GSReadonly()`                        | Value is read but never written back.                 |
| `GS_SMARTCHIP(fmt, smartchips=[...])` | Define Smart Chip format placeholders (experimental). |

### Lifecycle

* **Read:** Cells → optional parse → Pydantic validation → `SheetRow` instance
* **Modify:** Update attributes in Python
* **Write:** Use `save()` (single) or `saveRows([...])` (bulk)

---

## Examples

### Formatting Dates

```python
from datetime import datetime
from typing import Annotated
from pydantic_gsheets import GSFormat, GSIndex, GSRequired, SheetRow

class LogRow(SheetRow):
    event: Annotated[str, GSIndex(0), GSRequired()]
    created_at: Annotated[
        datetime,
        GSIndex(1),
        GSRequired(),
        GSFormat("DATE_TIME", "dd-MM-yyyy HH:mm")
    ]
```

### Custom Parsing

```python
def to_int_or_zero(value: str) -> int:
    return int(value) if value.strip().isdigit() else 0

class ParsedRow(SheetRow):
    raw_number: Annotated[int, GSIndex(0), GSParse(to_int_or_zero)]
```

### Read-only Columns

```python
class Employee(SheetRow):
    id: Annotated[int, GSIndex(0), GSRequired(), GSReadonly()]
    name: Annotated[str, GSIndex(1), GSRequired()]
```

### Bulk Writes

```python
rows = [UserRow(name=f"User {i}", email=f"u{i}@ex.com", age=20+i) for i in range(5)]
sheet.saveRows(rows)
```

---

## Smart Chips (Experimental)

Smart Chips let you mix plain text with structured entities (people and Drive file links).

⚠️ Only Google Drive file links can currently be written as chips. Other service links (YouTube, Calendar, etc.) are read-only.

```python
from typing import Annotated
from pydantic_gsheets.types import (
    smartChips, GS_SMARTCHIP,
    peopleSmartChip, fileSmartChip
)

class OwnershipRow(SheetRow):
    ownership: Annotated[
        smartChips,
        GS_SMARTCHIP(
            "@ owner of @",
            smartchips=[peopleSmartChip, fileSmartChip]
        ),
        GSIndex(0), GSRequired()
    ]
```

---

## Creating Sheets Programmatically

```python
sheet = GoogleWorkSheet.create_sheet(
    model=UserRow,
    service=svc,
    spreadsheet_id="<SPREADSHEET_ID>",
    sheet_name="Users",
    add_column_headers=True,
    skip_if_exists=True
)
```

---

## Error Handling

* `RequiredValueError` → Raised when a `GSRequired` field is blank.
* Pydantic validation errors → Raised if a cell’s value cannot be coerced to the annotated type.

---

## Tips for Beginners

* Add `client_secret.json` and `.tokens/` to your `.gitignore`.
* Start with a simple sheet (2–3 columns) before scaling up.
* If writes seem to “do nothing,” check for `GSReadonly` or missing `GSIndex`.
* Use `refresh=True` when you need the latest remote state.

---

## FAQ

**Q: Do I need the Drive API enabled?**
A: Only if you use smart chips involving Drive files or file helpers.

**Q: Can I append rows without indices?**
A: Yes. Un-indexed fields follow declaration order. Explicit indices reserve/skip columns.

**Q: How do I format currency?**
A: Use `GSFormat("CURRENCY", "€#,##0.00")`.

---

## Contributing

Contributions are welcome! 🎉

1. Fork & clone
2. Create a virtual environment and install dev dependencies (`pip install -e ".[dev]"`)
3. Add or adjust tests in `tests/`
4. Open an [issue](../../issues) or a PR with a clear description

---

## Roadmap

See [ROADMAP.md](ROADMAP.md)

---

## Minimal End-to-End Script

```python
from typing import Annotated
from pydantic_gsheets import (
    AuthConfig, AuthMethod, get_sheets_service,
    GoogleWorkSheet, SheetRow, GSIndex, GSRequired
)

svc = get_sheets_service(AuthConfig(
    method=AuthMethod.USER_OAUTH,
    client_secrets_file="client_secret.json",
    token_cache_file=".tokens/google.json",
))

class Demo(SheetRow):
    title: Annotated[str, GSIndex(0), GSRequired()]
    views: Annotated[int, GSIndex(1)]

sheet = GoogleWorkSheet(Demo, svc, "<SPREADSHEET_ID>", "Demo", start_row=2)

# Append
items = [Demo(title=f"Post {i}", views=i*10) for i in range(3)]
sheet.saveRows(items)

# Read back
for row in sheet.rows(refresh=True):
    print(row.title, row.views)
```

---

## License  
MIT License © 2025 Youssef Benhammouda

