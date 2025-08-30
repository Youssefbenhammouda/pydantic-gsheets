# src/pydantic_gsheets/worksheet.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Optional,
    Self,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    get_origin,
    get_type_hints,
    Annotated,
)
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError
from googleapiclient.discovery import Resource


from googleapiclient.errors import HttpError

from .exceptions import RequiredValueError
from .types.smartChips_ import (
    GS_SMARTCHIP,
    fileSmartChip,
    richLinkProperties,
    smartChip,
    smartChips,
    peopleSmartChip,
    smartchipConf,
    split_at_tokens,
)

# =========================
# Annotation marker classes
# =========================


class GSIndex:
    """Zero-based index within the logical row (relative to worksheet.start_column)."""

    def __init__(self, index: int):
        if index < 0:
            raise ValueError("GSIndex must be >= 0")
        self.index = index


class GSRequired:
    """Field must be non-empty on read/write."""

    def __init__(self, message: str = "Required value is missing."):
        self.message = message


class GSParse:
    """Apply a callable(value) -> parsed before constructing the model."""

    def __init__(self, func: Callable[[Any], Any]):
        self.func = func


class GSFormat:
    """
    Desired Google Sheets numberFormat for the column.
    Example: GSFormat('DATE_TIME', 'dd-MM-yyyy HH:mm')
    Types: TEXT, NUMBER, PERCENT, CURRENCY, DATE, TIME, DATE_TIME, SCIENTIFIC
    """

    def __init__(self, number_format_type: str, pattern: Optional[str] = None):
        self.type = number_format_type
        self.pattern = pattern


class GSReadonly:
    """Do not write this field back to the sheet."""

    pass


# =========================
# Internal field descriptor
# =========================


@dataclass
class _FieldSpec:
    name: str
    py_type: Any
    index: int
    required: bool
    readonly: bool
    parser: Optional[Callable[[Any], Any]]
    fmt: Optional[GSFormat]

    smartchip: smartchipConf


def _extract_field_specs(model_cls: Type["SheetRow"]) -> Dict[str, _FieldSpec]:
    """
    Pull metadata from Annotated types on a SheetRow subclass.
    """
    specs: Dict[str, _FieldSpec] = {}
    hints = get_type_hints(model_cls, include_extras=True)
    last_index = 0
    for fname, annotated in hints.items():
        if fname.startswith("_"):
            continue
        # annotated is either plain type or Annotated[base, *extras]
        base_type = annotated
        extras: Tuple[Any, ...] = ()
        if get_origin(annotated) is Annotated:
            base_type = annotated.__args__[0]
            extras = tuple(annotated.__metadata__)  # type: ignore

        index = None
        required = False
        readonly = False
        parser = None
        fmt = None
        smartchip = smartchipConf(is_smartchips=issubclass(base_type, smartChips))
        for extra in extras:
            if isinstance(extra, GSIndex):
                index = extra.index
            elif isinstance(extra, GSRequired):
                required = True
            elif isinstance(extra, GSReadonly):
                readonly = True
            elif isinstance(extra, GSParse):
                parser = extra.func
            elif isinstance(extra, GSFormat):
                fmt = extra

            elif isinstance(extra, GS_SMARTCHIP):
                smartchip.format_text = extra.format_text
                smartchip.smartchips = extra.smartchips
                if not (
                    (
                        l := len(
                            set(
                                x
                                for x in extra.smartchips
                                if issubclass(x, richLinkProperties)
                            )
                        )
                    )
                    <= 1
                    and (l != 1 or fileSmartChip in extra.smartchips)
                ):
                    readonly = True
        if index is None:
            index = last_index
        else:
            last_index = index
        last_index += 1

        specs[fname] = _FieldSpec(
            name=fname,
            py_type=base_type,
            index=index,
            required=required,
            readonly=readonly,
            parser=parser,
            fmt=fmt,
            smartchip=smartchip,
        )

    # Ensure unique indices
    seen = set()
    for s in specs.values():
        if s.index in seen:
            raise ValueError(f"Duplicate GSIndex {s.index} detected.")
        seen.add(s.index)

    return specs


def _max_index(specs: Dict[str, _FieldSpec]) -> int:
    return max(s.index for s in specs.values()) if specs else -1


# ==============
# A1 utilities
# ==============


def _col_index_to_a1(idx: int) -> str:
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA' ..."""
    if idx < 0:
        raise ValueError("Column index must be >= 0")
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def gsheets_to_datetime(sheet_number: float) -> date:
    # Google Sheets epoch starts at 1899-12-30
    base_date = datetime(1899, 12, 30)
    return base_date + timedelta(days=sheet_number)


def datetime_to_gsheets(d: date | datetime) -> float:
    """Convert Python date/datetime to Google Sheets serial number."""
    base_date = datetime(1899, 12, 30)

    # If input is a date, convert to datetime at midnight
    if isinstance(d, date) and not isinstance(d, datetime):
        d = datetime.combine(d, datetime.min.time())

    return (d - base_date).total_seconds() / 86400


# =========
# SheetRow
# =========


class SheetRow(BaseModel):
    """
    Base class for typed, annotated rows in a Google Sheet.

    - Define fields with typing.Annotated[..., GSIndex(...), GSRequired(), GSParse(...), GSFormat(...), GSReadonly()]
    - Each instance is bound to a (worksheet, row_number) once loaded or appended.
    - Use worksheet.write_row(instance) to persist.
    """

    # Binding state (not part of the sheet schema)
    _worksheet: Optional[GoogleWorkSheet] = None
    _row_number: Optional[int] = None

    # ----------------
    # Binding helpers
    # ----------------

    @classmethod
    def _specs(cls) -> Dict[str, _FieldSpec]:
        return _extract_field_specs(cls)

    @classmethod
    def _width(cls) -> int:
        return _max_index(cls._specs()) + 1

    @classmethod
    def _from_sheet_values(
        cls, worksheet: GoogleWorkSheet, row_number: int, rowData: Sequence[Any]
    ) -> "Self":
        specs = cls._specs()
        data: Dict[str, Any] = {}

        for name, spec in specs.items():

            raw: dict[Any, Any] = (
                rowData[spec.index]
                if spec.index < len(rowData)
                else {"userEnteredValue": {"stringValue": ""}}
            )
            val = raw.get("formattedValue", None) or raw.get(
                "userEnteredValue", {}
            ).get("stringValue", None)

            # Apply parser if provided
            if spec.parser and val is not None:
                try:
                    val = spec.parser(val)
                except Exception as e:
                    raise ValueError(
                        f"Parse error for field '{name}' at column {spec.index}: {e}"
                    ) from e

            # Required check (on read)
            if spec.required and (
                val is None
                or (isinstance(val, str) and (val.strip() == "" or val.strip() == "-"))
            ):
                raise RequiredValueError(
                    f"Required field '{name}' is empty at row {row_number}."
                )
            if spec.smartchip.is_smartchips:
                copySmartChips = spec.smartchip.smartchips.copy()
                data[name] = smartChips(
                    format_text=spec.smartchip.format_text,
                    chipRuns=[],
                    display_text=val,
                )

                for part in split_at_tokens(spec.smartchip.format_text).values():
                    if part == "@":

                        try:
                            smartchiptype = copySmartChips.pop(0)
                        except IndexError:
                            print(
                                f"Warning: No smartchip type defined for {spec.smartchip.format_text} at row {row_number}:{val}"
                            )
                            break

                        for queriedChips in raw.get("chipRuns", []):
                            chipobj = queriedChips.get("chip", {})
                            if smartchiptype.__fieldName__ in chipobj:
                                raw["chipRuns"].remove(queriedChips)
                                if issubclass(smartchiptype, richLinkProperties):
                                    data[name].chipRuns.append(
                                        smartchiptype(
                                            uri=chipobj.get(
                                                "richLinkProperties", {}
                                            ).get("uri", ""),
                                        )
                                    )
                                elif issubclass(smartchiptype, peopleSmartChip):
                                    data[name].chipRuns.append(
                                        smartchiptype(
                                            email=chipobj.get(
                                                "personProperties", {}
                                            ).get("email", ""),
                                            display_format=smartchiptype.displayFormat(
                                                chipobj.get("personProperties", {}).get(
                                                    "displayFormat", ""
                                                )
                                            ),
                                        )
                                    )
                                break
                        else:
                            print(
                                f"Warning: No smartchip was found in sheet for {spec.smartchip.format_text} at row {row_number}:{val}"
                            )

            elif (
                "userEnteredFormat" in raw
                and "numberFormat" in raw["userEnteredFormat"]
                and "DATE" in raw["userEnteredFormat"]["numberFormat"]["type"]
            ):
                n = raw["effectiveValue"]["numberValue"]
                data[name] = gsheets_to_datetime(n)
            else:
                data[name] = val 

        try:
            inst = cls(**data)  # Pydantic validation of types
        except ValidationError as e:
            raise ValueError(
                f"Pydantic validation failed for row {row_number}: {e}"
            ) from e

        inst._bind(worksheet, row_number)
        return inst

    def _to_sheet_values(self) -> List[Any]:
        """
        Convert the instance to a list aligned with GSIndex columns.


        - Required fields are validated before returning.
        - Boolean values are converted to "TRUE"/"FALSE" for USER_ENTERED mode.
        - None values become empty strings.
        """
        specs = self._specs()
        width = self._width()
        out: List[Any] = [""] * width  # pre-fill blanks

        for name, spec in specs.items():

            val = getattr(self, name)

            # Required check
            if spec.required and (
                val is None or (isinstance(val, str) and val.strip() == "")
            ):
                raise ValueError(f"Required field '{name}' is empty (write aborted).")

            # Normalize booleans for Sheets
            if isinstance(val, bool):
                out[spec.index] = "TRUE" if val else "FALSE"
            else:

                out[spec.index] = val if val is not None else ""

        return out

    def _bind(self, worksheet: GoogleWorkSheet, row_number: int) -> None:
        self._worksheet = worksheet
        self._row_number = row_number

    # -------------
    # Public API
    # -------------

    @property
    def row_number(self) -> int:
        if self._row_number is None:
            raise RuntimeError("Row is not bound to a worksheet yet.")
        return self._row_number

    @property
    def worksheet(self) -> GoogleWorkSheet:
        if self._worksheet is None:
            raise RuntimeError("Row is not bound to a worksheet yet.")
        return self._worksheet

    def save(self) -> None:
        """Persist the current instance to its bound row."""
        if not self._worksheet:
            raise RuntimeError("Row is not bound to a worksheet; cannot save.")
        self._worksheet._write_rows([self])

    def reload(self) -> None:
        """Refresh the current instance from the sheet."""
        if not self._worksheet or not self._row_number:
            raise RuntimeError("Row is not bound; cannot reload.")
        fresh = self._worksheet._read_row(self._row_number)
        for k, v in fresh.model_dump().items():  # pydantic v2; for v1 use .dict()
            setattr(self, k, v)


T = TypeVar("T", bound=SheetRow)


class GoogleWorkSheet(Generic[T]):
    """
    Thin wrapper around a single worksheet (tab) within a Google Spreadsheet.

    - Pre-validates access (read, and optionally write) at init.
    - Supports custom start row/column and header presence.
    - Provides helpers to read/write rows tied to a SheetRow model.
    """

    def __init__(
        self,
        model: Type[T],
        service: Any,
        spreadsheet_id: str,
        sheet_name: str,
        *,
        start_row: int = 2,  # 1-based row number where data starts (2 if you have headers in row 1)
        start_column: int = 0,  # 0-based column offset (0 = column A)
        drive_service: Optional[Any] = None,
    ):

        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.start_row = start_row

        self.start_column = start_column
        self.drive_service = drive_service
        self._model = model
        # Resolve sheetId and confirm it exists
        meta = (
            self.service.spreadsheets()
            .get(
                spreadsheetId=self.spreadsheet_id,
                fields="sheets(properties(sheetId,title))",
            )
            .execute()
        )
        sheets = meta.get("sheets", [])
        sheet_id = None
        for sh in sheets:
            props = sh.get("properties", {})
            if props.get("title") == sheet_name:
                sheet_id = props.get("sheetId")
                break
        if sheet_id is None:
            raise ValueError(
                f"Worksheet '{sheet_name}' not found in spreadsheet {spreadsheet_id}"
            )
        self.sheet_id = sheet_id

        # Pre-validate read (and optionally write) permissions
        self._validate_access()

        self._row_instances: Dict[int, T] = {}
        self._row_order: List[int] = []  # preserves insertion/read order

    @staticmethod
    def create_sheet(
        model: Type[T],
        service: Any,
        spreadsheet_id: str,
        sheet_name: str,
        add_column_headers: bool = True,
        skip_if_exists: bool = True,
        start_row: int = 2,
        start_column: int = 0,  # 0-based column offset (0 = column A)
        drive_service: Optional[Any] = None,
    ) -> GoogleWorkSheet[T]:
        """Create a new sheet in the specified spreadsheet."""
        body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body=body
            ).execute()
        except HttpError as e:
            if skip_if_exists and "already exists" in e.reason:
                return GoogleWorkSheet(
                    model=model,
                    service=service,
                    spreadsheet_id=spreadsheet_id,
                    sheet_name=sheet_name,
                    start_column=start_column,
                    start_row=start_row,
                    drive_service=drive_service,
                )
            raise e
        # write columns names
        if add_column_headers:
            headers = model.__annotations__.keys()
            header_range = f"{sheet_name}!{_col_index_to_a1(0)}{1}:{_col_index_to_a1(len(headers) - 1)}{1}"
            sheets = (
                service.spreadsheets()
                .get(
                    spreadsheetId=spreadsheet_id,
                    fields="sheets(properties(sheetId,title))",
                )
                .execute()["sheets"]
            )
            sheet_id = next(
                (
                    sheet["properties"]["sheetId"]
                    for sheet in sheets
                    if sheet["properties"]["title"] == sheet_name
                ),
                None,
            )
            if sheet_id is None:
                raise ValueError(f"Sheet with name '{sheet_name}' not found.")

            # Combine header writing and styling into a single batchUpdate request
            requests = [
                {
                    "updateCells": {
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {"stringValue": header},
                                        "userEnteredFormat": {
                                            "textFormat": {"bold": True},
                                            "horizontalAlignment": "CENTER",
                                            "backgroundColor": {
                                                "red": 0.9,
                                                "green": 0.9,
                                                "blue": 0.9,
                                            },
                                        },
                                    }
                                    for header in headers
                                ]
                            }
                        ],
                        "fields": "userEnteredValue,userEnteredFormat(textFormat,horizontalAlignment,backgroundColor)",
                        "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                    }
                }
            ]
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"requests": requests}
            ).execute()

        return GoogleWorkSheet(
            model=model,
            service=service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            start_column=start_column,
            start_row=start_row,
            drive_service=drive_service,
        )

    def rows(
        self, *, refresh: bool = False, skip_rows_missing_required: bool = True
    ) -> Generator[T, None, None]:
        """
        Return all row instances for this worksheet (cached).
        Set refresh=True to re-read the sheet.
        """
        if refresh or not self._row_instances:
            self.clear_cache()
            for inst in self._read_rows(
                skip_rows_missing_required=skip_rows_missing_required
            ):
                self._cache_put(inst)
                yield inst
        else:
            yield from self._row_instances.values()

    def get(
        self,
        row_number: int,
        *,
        use_cache: bool = True,
        refresh: bool = False,
        skip_rows_missing_required: bool = True,
    ) -> Optional[T]:
        """
        Get a single row by absolute row number. Returns None if required fields
        were missing and ignore_required=True would have skipped it.
        """
        if use_cache and not refresh and row_number in self._row_instances:
            return self._row_instances[row_number]
        try:
            inst = self._read_row(row_number)
        except RequiredValueError as e:
            if skip_rows_missing_required:
                return None
            raise e
        self._cache_put(inst)
        return inst

    def saveRow(self, inst: T | int) -> None:
        if isinstance(inst, int):
            if inst not in self._row_order:
                raise ValueError(f"No row instance found for row number {inst}.")
            inst = self._row_instances[inst]
        self.saveRows([inst])

    def saveRows(self, rows: Iterable[T]) -> None:
        # Bulk save rows
        self._write_rows(rows)

    def _cache_put(self, inst: T) -> None:
        rn = inst._row_number
        if rn is None:
            raise ValueError("Row number is not set.")
        self._row_instances[rn] = inst
        if rn not in self._row_order:
            self._row_order.append(rn)

    def clear_cache(self) -> None:
        self._row_instances.clear()
        self._row_order.clear()

    # -------------
    # Access checks
    # -------------

    def _validate_access(self, *, require_write: bool = True) -> None:
        # Read check: try to fetch top-left data cell in our region
        top_left_range = f"{self.sheet_name}!{_col_index_to_a1(self.start_column)}{self.start_row}:{_col_index_to_a1(self.start_column)}{self.start_row}"
        self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=top_left_range
        ).execute()

        if not require_write:
            return

        # --- Write check that avoids touching user data ---
        # Strategy:
        # 1) Find the first empty row in our target column starting at start_row.
        # 2) Write a temporary marker to that empty cell (proves write perms).
        # 3) Clear that cell immediately in a finally block.
        col_a1 = _col_index_to_a1(self.start_column)
        scan_range = f"{self.sheet_name}!{col_a1}{self.start_row}:{col_a1}"

        # Get existing values in the column from start_row downwards.
        # Google Sheets returns only up to the last non-empty cell, so
        # the first empty row index is start_row + len(values).
        get_resp = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=scan_range,
                majorDimension="ROWS",
            )
            .execute()
        )
        col_values = get_resp.get("values", [])
        first_empty_row = self.start_row + len(col_values)

        # Construct the scratch cell range (guaranteed empty based on the above).
        scratch_range = (
            f"{self.sheet_name}!{col_a1}{first_empty_row}:{col_a1}{first_empty_row}"
        )

        # Write a harmless marker, then clear it.
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=scratch_range,
                valueInputOption="RAW",
                body={"values": [["__WRITE_CHECK__"]]},
            ).execute()
        finally:
            # Always attempt to clean up—even if the update failed, this is harmless.
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=scratch_range,
                body={},  # required but empty
            ).execute()

    # ---------------------
    # Formatting management
    # ---------------------

    def apply_formats_for_model(self) -> None:
        """
        Apply GSFormat for each annotated field to the entire column.
        """
        specs = _extract_field_specs(self._model)
        requests = []
        for s in specs.values():
            if not s.fmt:
                continue
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": self.sheet_id,
                            "startColumnIndex": self.start_column + s.index,
                            "endColumnIndex": self.start_column + s.index + 1,
                            # Apply to all rows (omit row indices)
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": s.fmt.type,
                                    **(
                                        {"pattern": s.fmt.pattern}
                                        if s.fmt.pattern
                                        else {}
                                    ),
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )
        if requests:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body={"requests": requests}
            ).execute()

    # -------------
    # Range helpers
    # -------------

    def _row_a1_range(self, row_number: int) -> str:
        """
        A1 range for a single logical data row bound to model_cls.
        row_number is absolute (1-based) row index in the sheet.
        """
        specs = _extract_field_specs(self._model)
        width = _max_index(specs) + 1
        start_col = self.start_column
        end_col = start_col + width - 1
        a1_start = _col_index_to_a1(start_col)
        a1_end = _col_index_to_a1(end_col)
        return f"{self.sheet_name}!{a1_start}{row_number}:{a1_end}{row_number}"

    def _cell_a1_range(self, row: int, col_index0: int) -> str:
        """
        A1 range for a single logical data cell bound to model_cls.
        """
        a1_col = _col_index_to_a1(col_index0)
        return f"{self.sheet_name}!{a1_col}{row}:{a1_col}{row}"

    # ----------
    # Read/write
    # ----------

    def _read_row(self, row_number: int) -> "T":
        """
        Read a single row into a bound model instance.
        """
        if row_number < 1:
            raise ValueError("row_number must be >= 1")
        rng = self._row_a1_range(row_number)
        resp = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=rng)
            .execute()
        )
        row_vals = resp.get("values", [[]])
        # Google may return fewer cells; pad to full width
        specs = _extract_field_specs(self._model)
        width = _max_index(specs) + 1
        flat = row_vals[0] if row_vals else []
        flat = list(flat) + [""] * (width - len(flat))
        instance = self._model._from_sheet_values(self, row_number, flat)

        return instance

    def _read_rows(
        self, skip_rows_missing_required: bool = True
    ) -> Generator[T, None, None]:
        """
        Stream all non-empty data rows as typed SheetRow instances.
        - Uses the model bound to this worksheet (self._model).
        - Pads short rows to the model width.
        - Skips fully blank rows.
        - Preserves absolute row numbers (sheet 1-based).

        skip_rows_missing_required : If true, skip rows with missing required fields
        """
        # --- safety & setup
        if not hasattr(self, "_model") or self._model is None:
            raise RuntimeError(
                "No model bound to this worksheet. Set self._model to a SheetRow subclass."
            )

        model_cls: Type[T] = self._model  # type: ignore[assignment]
        specs = _extract_field_specs(model_cls)
        width = _max_index(specs) + 1

        # Build open-ended A1 range from start_row to end-of-sheet across the model's width
        start_col = self.start_column
        end_col = start_col + width - 1
        a1_start = _col_index_to_a1(start_col)
        a1_end = _col_index_to_a1(end_col)
        rng = f"{self.sheet_name}!{a1_start}{self.start_row}:{a1_end}{max(self.start_row,self.get_last_row_number())}"

        # Fetch rows
        resp = (
            self.service.spreadsheets()
            .get(spreadsheetId=self.spreadsheet_id, ranges=[rng], includeGridData=True)
            .execute()
        )
        rows = resp.get("sheets", [{}])[0].get("data", [{}])[0].get("rowData", [{}])

        # Yield typed instances
        for offset, row in enumerate(rows):
            row_number = self.start_row + offset  # absolute row number in the sheet

            try:
                instance = model_cls._from_sheet_values(
                    self, row_number, row.get("values", [])
                )
            except RequiredValueError as e:
                if skip_rows_missing_required:
                    continue
                else:
                    raise e

            yield instance

    def _write_rows(self, instances: Iterable["T"]) -> None:
        """
        Bulk write multiple bound instances using a single Sheets batchUpdate call.
        - Preserves readonly columns by only updating editable/new cells.
        - Applies GSFormat once per column across the affected row range.
        """
        lastrow = self.get_last_row_number()
        instances = list(instances)
        if not instances:
            return

        # Validate and assign row numbers
        new_rows: list[int] = []
        for inst in instances:
            if inst._worksheet is None:
                if type(inst) is not self._model:
                    raise ValueError(f"Row {inst} is not of the correct model type.")
                inst._worksheet = self
            elif inst._worksheet is not self:
                raise ValueError(f"Row {inst} is bound to a different worksheet.")
            if inst._row_number is None:
                lastrow += 1
                inst._row_number = lastrow
                new_rows.append(inst._row_number)

        # Ensure deterministic write order
        instances.sort(
            key=lambda r: r._row_number  # pyright: ignore[reportArgumentType]
        )
        specs = self._model._specs()
        all_cols = {spec.index: spec for spec in specs.values()}
        editable_cols = {spec.index for spec in specs.values() if not spec.readonly}

        # Row span that we'll touch (for formatting)
        min_row = min(
            inst._row_number
            for inst in instances  # pyright: ignore[reportArgumentType]
        )
        max_row = lastrow

        requests = []

        # 1) Value writes using updateCells (one HTTP call; many sub-requests is fine)
        for inst in instances:
            rn: int = inst._row_number  # pyright: ignore[reportAssignmentType]
            row_vals = inst._to_sheet_values()

            for col_idx, cell_val in enumerate(row_vals):
                if col_idx not in all_cols:
                    continue

                # Preserve readonly columns on existing rows
                if rn not in new_rows and col_idx not in editable_cols:
                    continue
                data: dict[str, List | dict | str | float | int] = {
                    "rows": [{"values": [{"userEnteredValue": {"stringValue" if isinstance(cell_val, str) else "numberValue": cell_val}}]}],
                    "fields": "userEnteredValue",
                }

                
                if isinstance(cell_val, smartChips):
                    data["fields"] += ",chipRuns"  # type: ignore
                    data["rows"] = [{"values": [{"userEnteredValue": {}}]}]

                    obj = data["rows"][0]["values"][0]
                    obj["userEnteredValue"]["stringValue"] = (
                        cell_val.format_text.replace("\\@", "@")
                    )
                    sections = [
                        x[0]
                        for x in split_at_tokens(cell_val.format_text.replace("\\@", " ")).items()
                        if x[1] == "@"
                    ]
                    l = len(sections)
                    obj["chipRuns"] = [
                        {**x._to_dict(), "startIndex": sections[i]}
                        for i, x in enumerate(cell_val.chipRuns)
                        if i < l
                    ]

                elif (fmt := all_cols[col_idx].fmt) is not None:
                    if isinstance(cell_val, date):
                        n = datetime_to_gsheets(cell_val)
                    else:
                        n = float(cell_val)
                    data["fields"] = "userEnteredValue,userEnteredFormat.numberFormat"
                    data["rows"] = [
                        {"values": [{"userEnteredValue": {"numberValue": n},"userEnteredFormat":{"numberFormat": {
                            "type": fmt.type,
                            **({"pattern": fmt.pattern} if fmt.pattern is not None else {})
                        }}}]}
                    ]  # type: ignore
                    

                
                requests.append(
                    {
                        "updateCells": {
                            "range": {
                                "sheetId": self.sheet_id,
                                "startRowIndex": rn - 1,
                                "endRowIndex": rn,
                                "startColumnIndex": self.start_column + col_idx,
                                "endColumnIndex": self.start_column + col_idx + 1,
                            },
                            **data,
                        }
                    }
                )

        if not requests:
            return
        
        # Single API call for both values and formatting
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests},
        ).execute()

        # Optional: refresh cache
        for _ in self.rows(refresh=True):pass

    def get_last_row_number(
        self,
    ) -> int:
        """
        Best-effort last row detection for the model's columns.
        """
        # Query a long range down the first column used by this model
        first_col_a1 = _col_index_to_a1(self.start_column)
        rng = f"{self.sheet_name}!{first_col_a1}{self.start_row}:{first_col_a1}"
        resp = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=rng, majorDimension="ROWS")
            .execute()
        )
        values = resp.get("values", [])
        # The number of non-empty rows + offset gives the last populated row
        last_idx = len(values) - 1  # zero-based within the queried block
        return self.start_row + last_idx
