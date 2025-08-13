# src/pydantic_gsheets/worksheet.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Generator, Generic, Iterable, List, Optional, Self, Sequence, Tuple, Type, TypeVar, get_origin, get_type_hints, Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError
from googleapiclient.discovery import Resource

from .drive_types import DriveFile, GSDrive




otherTypes = (DriveFile,)

formatters:dict[Type, Callable[[Any], str]] = {
    DriveFile: lambda v:v.url,
}

class RequiredValueError(ValueError):
    pass
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
    drive_opts: Optional[GSDrive]  # NEW

def _extract_field_specs(model_cls: Type["SheetRow"]) -> Dict[str, _FieldSpec]:
    """
    Pull metadata from Annotated types on a SheetRow subclass.
    """
    specs: Dict[str, _FieldSpec] = {}
    hints = get_type_hints(model_cls, include_extras=True)

    for fname, annotated in hints.items():
        if fname.startswith('_'):
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
        drive_opts: Optional[GSDrive] = None
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
            elif isinstance(extra, GSDrive):
                drive_opts = extra
                

        if index is None:
            raise ValueError(f"Field '{fname}' is missing GSIndex() annotation.")

        specs[fname] = _FieldSpec(
            name=fname,
            py_type=base_type,
            index=index,
            required=required,
            readonly=readonly,
            parser=parser,
            fmt=fmt,
            drive_opts=drive_opts,
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



def _get_cell_hyperlink(service, spreadsheet_id: str, sheet_name: str, row: int, col_index0: int) -> str | None:
    a1_col = _col_index_to_a1(col_index0)
    a1 = f"{sheet_name}!{a1_col}{row}:{a1_col}{row}"
    resp = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[a1],
        includeGridData=True,
        fields="sheets(data(rowData(values(hyperlink,textFormatRuns,userEnteredValue,formattedValue,chipRuns))))",
    ).execute()

    try:
        values = resp["sheets"][0]["data"][0]["rowData"][0]["values"][0]
    except (KeyError, IndexError):
        return None

    # 1) Direct cell-level hyperlink
    if "hyperlink" in values and values["hyperlink"]:
        return values["hyperlink"]
    if "chipRuns" in values and (link :=values["chipRuns"][0].get("chip", {}).get("richLinkProperties", {}).get("uri", {})):
        return link
    # 2) Hyperlink inside text runs (partial formatting)
    for run in values.get("textFormatRuns", []) or []:
        link = run.get("format", {}).get("link", {})
        if link and link.get("uri"):
            return link["uri"]

    return None

def _looks_like_url(s: str) -> bool:
    try:
        u = urlparse(s)
        return u.scheme in ("http", "https")
    except Exception:
        return False

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


# =================
# GoogleWorkSheet
# =================


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
        cls, worksheet: GoogleWorkSheet, row_number: int, values: Sequence[Any]
    ) -> "Self":
        specs = cls._specs()
        data: Dict[str, Any] = {}

        for name, spec in specs.items():
            raw = values[spec.index] if spec.index < len(values) else ""
            val = raw

            # Normalize Google empty -> None
            if val == "":
                val = None

            # Apply parser if provided
            if spec.parser and val is not None:
                try:
                    val = spec.parser(val)
                except Exception as e:
                    raise ValueError(f"Parse error for field '{name}' at column {spec.index}: {e}") from e
            else:
                if spec.py_type is DriveFile:
                    if val is not None and not _looks_like_url(str(val)):
                        if worksheet is not None:
                            link = _get_cell_hyperlink(
                                worksheet.service,
                                worksheet.spreadsheet_id,
                                worksheet.sheet_name,
                                row_number,
                                worksheet.start_column + spec.index,
                            )
                            if link:
                                val = link
                    val = DriveFile.parse_from_cell(val)
                
            # Required check (on read)
            if spec.required and (val is None or (isinstance(val, str) and (val.strip() == "" or val.strip() == "-"))):
                raise RequiredValueError(f"Required field '{name}' is empty at row {row_number}.")

            data[name] = val

        try:
            inst = cls(**data)  # Pydantic validation of types
        except ValidationError as e:
            raise ValueError(f"Pydantic validation failed for row {row_number}: {e}") from e

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
            if spec.required and (val is None or (isinstance(val, str) and val.strip() == "")):
                raise ValueError(f"Required field '{name}' is empty (write aborted).")

            # Normalize booleans for Sheets
            if isinstance(val, bool):
                out[spec.index] = "TRUE" if val else "FALSE"
            else:
                if type(val) in otherTypes:
                    out[spec.index] = formatters[type(val)](val)
                else:
                    out[spec.index] = str(val) if val is not None else ""

        return out
    def _bind(self, worksheet: GoogleWorkSheet, row_number: int) -> None:
        self._worksheet = worksheet
        self._row_number = row_number


    def _predownload_drive_files(self, specs: Dict[str, _FieldSpec], drive_service: Resource) -> None:
            """
            If a field is DriveFile and annotated with GSDrive(predownload=True),
            download it using the provided Drive service.
            """
            for fname, spec in specs.items():
                if spec.drive_opts and spec.drive_opts.predownload:
                    val = getattr(self, fname, None)
                    if isinstance(val, DriveFile):
                        val.ensure_downloaded(
                            drive_service,
                            dest_dir=spec.drive_opts.dest_dir,
                            filename_template=spec.drive_opts.filename_template,
                            export_mime=spec.drive_opts.export_mime,
                            overwrite=spec.drive_opts.overwrite,
                            row_number=self._row_number,
                            field_name=fname,
                        )



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
        if not self._worksheet or not self._row_number:
            raise RuntimeError("Row is not bound; cannot save. Use worksheet.append_row() or read_row().")
        self._worksheet.write_rows([self])

    def reload(self) -> None:
        """Refresh the current instance from the sheet."""
        if not self._worksheet or not self._row_number:
            raise RuntimeError("Row is not bound; cannot reload.")
        fresh = self._worksheet._read_row( self._row_number)
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
        start_row: int = 2,           # 1-based row number where data starts (2 if you have headers in row 1)
        has_headers: bool = True,
        start_column: int = 0,        # 0-based column offset (0 = column A)
        require_write: bool = False,
        drive_service: Optional[Any]=None,
    ):
        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.start_row = start_row
        self.has_headers = has_headers
        self.start_column = start_column
        self.drive_service = drive_service
        self._model = model
        # Resolve sheetId and confirm it exists
        meta = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id, fields="sheets(properties(sheetId,title))"
        ).execute()
        sheets = meta.get("sheets", [])
        sheet_id = None
        for sh in sheets:
            props = sh.get("properties", {})
            if props.get("title") == sheet_name:
                sheet_id = props.get("sheetId")
                break
        if sheet_id is None:
            raise ValueError(f"Worksheet '{sheet_name}' not found in spreadsheet {spreadsheet_id}")
        self.sheet_id = sheet_id

        # Pre-validate read (and optionally write) permissions
        self._validate_access(require_write=require_write)


        self._row_instances: Dict[int, T] = {}
        self._row_order: List[int] = []  # preserves insertion/read order



    def rows(self, *, refresh: bool = False, skip_rows_missing_required : bool = True) ->Generator[T, None, None]:
        """
        Return all row instances for this worksheet (cached).
        Set refresh=True to re-read the sheet.
        """
        if refresh or not self._row_instances:
            self.clear_cache()
            for inst in self._read_rows(skip_rows_missing_required=skip_rows_missing_required):
                self._cache_put(inst)
                yield inst 

    def get(self, row_number: int, *, use_cache: bool = True, refresh: bool = False, skip_rows_missing_required: bool = True) -> Optional[T]:
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
        inst.save()
    
    def saveRows(self, rows: Iterable[T]) -> None:
        #Bulk save rows
        pass

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

    def _validate_access(self, *, require_write: bool = False) -> None:
        # Read check: try to fetch top-left data cell in our region
        top_left_range = f"{self.sheet_name}!{_col_index_to_a1(self.start_column)}{self.start_row}:{_col_index_to_a1(self.start_column)}{self.start_row}"
        self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=top_left_range
        ).execute()

        if require_write:
            # Write check: write back the same value to the same cell (no-op but requires write perms)
            get_resp = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=top_left_range
            ).execute()
            current = get_resp.get("values", [[""]])[0]
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=top_left_range,
                valueInputOption="RAW",
                body={"values": [current]},
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
            requests.append({
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
                                **({"pattern": s.fmt.pattern} if s.fmt.pattern else {})
                            }
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat"
                }
            })
        if requests:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests}
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
        rng = self._row_a1_range( row_number)
        resp = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=rng
        ).execute()
        row_vals = resp.get("values", [[]])
        # Google may return fewer cells; pad to full width
        specs = _extract_field_specs(self._model)
        width = _max_index(specs) + 1
        flat = row_vals[0] if row_vals else []
        flat = list(flat) + [""] * (width - len(flat))
        instance = self._model._from_sheet_values(self, row_number, flat)
        if self.drive_service:
            instance._predownload_drive_files(specs, self.drive_service)
        return instance


    def _read_rows(self, skip_rows_missing_required : bool = True) -> Generator[T, None, None]:
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
            raise RuntimeError("No model bound to this worksheet. Set self._model to a SheetRow subclass.")

        model_cls: Type[T] = self._model  # type: ignore[assignment]
        specs = _extract_field_specs(model_cls)
        width = _max_index(specs) + 1

        # Build open-ended A1 range from start_row to end-of-sheet across the model's width
        start_col = self.start_column
        end_col = start_col + width - 1
        a1_start = _col_index_to_a1(start_col)
        a1_end = _col_index_to_a1(end_col)
        rng = f"{self.sheet_name}!{a1_start}{self.start_row}:{a1_end}"

        # Fetch rows
        resp = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=rng,
            majorDimension="ROWS",
        ).execute()
        rows = resp.get("values", [])

        # Yield typed instances
        for offset, row in enumerate(rows):
            row_number = self.start_row + offset  # absolute row number in the sheet

            # Normalize Google’s row to fixed width
            flat = list(row) if row else []
            if len(flat) < width:
                flat += [""] * (width - len(flat))

            # Skip fully blank logical rows (across our model's columns)
            if all((c == "" for c in flat)):
                continue
            try:
                instance = model_cls._from_sheet_values(self, row_number, flat)
            except RequiredValueError as e:
                if skip_rows_missing_required :
                    continue
                else:
                    raise e

            # Drive predownload hook (if configured)
            if self.drive_service:
                instance._predownload_drive_files(specs, self.drive_service)

            yield instance

    def write_rows(self, instances: Iterable["T"]) -> None:
        """
        Bulk write multiple bound instances in a single API call.
        Preserves GSReadonly columns by fetching their existing values first.
        """
        instances = list(instances)
        if not instances:
            return
        new_columns:list[int] = []
        # Validate and sort by row_number
        for inst in instances:
            if inst._worksheet is not self:
                raise ValueError(f"Row {inst} is bound to a different worksheet.")
            if inst._row_number is None:
                inst._row_number = self.get_last_row_number() + 1
                new_columns.append(inst._row_number)
        instances.sort(key=lambda r: r._row_number) # pyright: ignore[reportArgumentType]


        specs = self._model._specs()
        all_cols = [spec.index for spec in specs.values()]
        editable_cols = [spec.index for spec in specs.values() if not spec.readonly]
        requests = []
        for inst in instances:
            rn:int = inst._row_number # pyright: ignore[reportAssignmentType]
            row_vals = inst._to_sheet_values()  
            for col_idx, cell_val in enumerate(row_vals):
                if  col_idx not in all_cols:
                    continue
                if rn not in new_columns and col_idx not in editable_cols:
                    continue
                a1 = self._cell_a1_range(rn, col_idx + self.start_column)
                requests.append({
                    "range": a1,
                    "majorDimension": "ROWS",
                    "values": [[cell_val]],
                })
        if not requests:
            return
        # ONE request to write everything
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={
                "valueInputOption": "USER_ENTERED",
                "data": requests
            },
        ).execute()

        # Optional: refresh cache
        if hasattr(self, "_cache_put"):
            for inst in instances:
                self._cache_put(inst)



    def get_last_row_number(self,) -> int:
        """
        Best-effort last row detection for the model's columns.
        """
        # Query a long range down the first column used by this model
        first_col_a1 = _col_index_to_a1(self.start_column)
        rng = f"{self.sheet_name}!{first_col_a1}{self.start_row}:{first_col_a1}"
        resp = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=rng, majorDimension="ROWS"
        ).execute()
        values = resp.get("values", [])
        # The number of non-empty rows + offset gives the last populated row
        last_idx = len(values) - 1  # zero-based within the queried block
        return self.start_row + last_idx
