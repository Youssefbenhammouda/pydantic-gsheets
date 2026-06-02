from __future__ import annotations

import warnings
from typing import (
    Any, Dict, Generator, Generic, Iterable, Iterator, List, Optional,
    Sequence, Type, TypeVar, overload,
)

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from ..exceptions import (
    RequiredValueError, RequiredValueSkippedWarning, UnboundRowError, WrongWorksheetError,
)
from .._logging import logger
from .converters import col_index_to_a1, datetime_to_gsheets
from .field_spec import _extract_field_specs, _max_index
from .row import SheetRow
from ..api.client import SheetsClient, _chunked, _BATCH_REQUEST_LIMIT

from datetime import date

T = TypeVar("T", bound=SheetRow)


class GoogleWorkSheet(Generic[T]):
    """
    Thin wrapper around a single worksheet (tab) within a Google Spreadsheet.

    Accepts either a SheetsClient or a raw googleapiclient Resource (deprecated).
    """

    def __init__(
        self,
        model: Type[T],
        service: SheetsClient | Resource,
        spreadsheet_id: str,
        sheet_name: str,
        *,
        start_row: int = 2,
        start_column: int = 0,
        drive_service: Optional[Resource] = None,
        validate_access: bool = True,
    ) -> None:
        if isinstance(service, SheetsClient):
            self._client = service
        else:
            warnings.warn(
                "Passing a raw googleapiclient Resource is deprecated. "
                "Wrap it with SheetsClient(service) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            self._client = SheetsClient(service, drive_service=drive_service)

        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.start_row = start_row
        self.start_column = start_column
        self._model = model

        # Resolve sheet ID
        meta = self._client.spreadsheets_get(
            spreadsheet_id,
            fields="sheets(properties(sheetId,title))",
        )
        self.sheet_id: int = self._resolve_sheet_id(meta, sheet_name, spreadsheet_id)

        if validate_access:
            self._validate_access()

        self._row_instances: Dict[int, T] = {}
        self._row_order: List[int] = []

    @staticmethod
    def _resolve_sheet_id(meta: dict, sheet_name: str, spreadsheet_id: str) -> int:
        for sh in meta.get("sheets", []):
            props = sh.get("properties", {})
            if props.get("title") == sheet_name:
                return props["sheetId"]
        raise ValueError(
            f"Worksheet '{sheet_name}' not found in spreadsheet '{spreadsheet_id}'. "
            "Check the sheet name and spreadsheet ID for typos."
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create_sheet(
        model: Type[T],
        service: SheetsClient | Resource,
        spreadsheet_id: str,
        sheet_name: str,
        add_column_headers: bool = True,
        skip_if_exists: bool = True,
        start_row: int = 2,
        start_column: int = 0,
        drive_service: Optional[Resource] = None,
    ) -> GoogleWorkSheet[T]:
        """Create a new sheet tab. Returns a bound GoogleWorkSheet."""
        if isinstance(service, SheetsClient):
            client = service
        else:
            warnings.warn(
                "Passing a raw Resource to create_sheet is deprecated. "
                "Use SheetsClient(service) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            client = SheetsClient(service, drive_service=drive_service)

        try:
            client.spreadsheets_batch_update(
                spreadsheet_id,
                [{"addSheet": {"properties": {"title": sheet_name}}}],
            )
        except HttpError as exc:
            if skip_if_exists and "already exists" in str(exc.reason):
                return GoogleWorkSheet(
                    model=model,
                    service=client,
                    spreadsheet_id=spreadsheet_id,
                    sheet_name=sheet_name,
                    start_row=start_row,
                    start_column=start_column,
                )
            raise

        if add_column_headers:
            specs = _extract_field_specs(model)
            headers = [s.name for s in sorted(specs.values(), key=lambda s: s.index)]
            meta = client.spreadsheets_get(
                spreadsheet_id,
                fields="sheets(properties(sheetId,title))",
            )
            sheet_id = GoogleWorkSheet._resolve_sheet_id(meta, sheet_name, spreadsheet_id)
            requests = [
                {
                    "updateCells": {
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {"stringValue": h},
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
                                    for h in headers
                                ]
                            }
                        ],
                        "fields": "userEnteredValue,userEnteredFormat(textFormat,horizontalAlignment,backgroundColor)",
                        "start": {
                            "sheetId": sheet_id,
                            "rowIndex": 0,
                            "columnIndex": start_column,
                        },
                    }
                }
            ]
            client.spreadsheets_batch_update(spreadsheet_id, requests)

        return GoogleWorkSheet(
            model=model,
            service=client,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            start_row=start_row,
            start_column=start_column,
        )

    # ------------------------------------------------------------------
    # Access validation
    # ------------------------------------------------------------------

    def _validate_access(self, *, require_write: bool = True) -> None:
        # Read check
        top_left = (
            f"{self.sheet_name}!"
            f"{col_index_to_a1(self.start_column)}{self.start_row}:"
            f"{col_index_to_a1(self.start_column)}{self.start_row}"
        )
        self._client.values_get(self.spreadsheet_id, top_left)

        if not require_write:
            return

        # Write check: no-op updateCells with empty rows — exercises write permission
        # without modifying any data.
        try:
            self._client.spreadsheets_batch_update(
                self.spreadsheet_id,
                [
                    {
                        "updateCells": {
                            "rows": [],
                            "fields": "userEnteredValue",
                            "start": {
                                "sheetId": self.sheet_id,
                                "rowIndex": 0,
                                "columnIndex": 0,
                            },
                        }
                    }
                ],
            )
        except HttpError as exc:
            if int(exc.resp.status) == 403:
                from ..exceptions import PermissionDeniedError
                raise PermissionDeniedError(
                    f"No write permission for spreadsheet '{self.spreadsheet_id}'."
                ) from exc
            raise

    # ------------------------------------------------------------------
    # Public read
    # ------------------------------------------------------------------

    def rows(
        self,
        *,
        refresh: bool = False,
        skip_rows_missing_required: bool = True,
        page_size: Optional[int] = None,
    ) -> Generator[T, None, None]:
        """Yield all data rows. Cached after first call; pass refresh=True to re-read."""
        if refresh or not self._row_instances:
            self.clear_cache()
            for inst in self._read_rows(
                skip_rows_missing_required=skip_rows_missing_required,
                page_size=page_size,
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
        """Fetch a single row by absolute (1-based) row number."""
        if use_cache and not refresh and row_number in self._row_instances:
            return self._row_instances[row_number]
        try:
            inst = self._read_row(row_number)
        except RequiredValueError as exc:
            if skip_rows_missing_required:
                warnings.warn(
                    f"Row {row_number} skipped: {exc}",
                    RequiredValueSkippedWarning,
                    stacklevel=2,
                )
                return None
            raise
        self._cache_put(inst)
        return inst

    # ------------------------------------------------------------------
    # Public write
    # ------------------------------------------------------------------

    def saveRow(self, inst: T | int) -> None:
        if isinstance(inst, int):
            if inst not in self._row_instances:
                raise ValueError(f"No cached row instance for row number {inst}.")
            inst = self._row_instances[inst]
        self._write_rows([inst])

    def saveRows(self, rows: Iterable[T]) -> None:
        self._write_rows(rows)

    def append_row(self, instance: T) -> T:
        """Append a new unbound row at the end of data. Binds and returns the instance."""
        if instance._row_number_ref is not None:
            raise UnboundRowError(
                "Instance is already bound to row "
                f"{instance._row_number_ref}. Use save() to update it."
            )
        instance._worksheet_ref = self
        self._write_rows([instance])
        return instance

    def append_rows(self, instances: Iterable[T]) -> List[T]:
        """Append multiple unbound rows in a single batchUpdate."""
        lst = list(instances)
        for inst in lst:
            if inst._row_number_ref is not None:
                raise UnboundRowError(
                    f"Instance already bound to row {inst._row_number_ref}."
                )
            inst._worksheet_ref = self
        self._write_rows(lst)
        return lst

    def delete_row(
        self,
        row_number_or_instance: int | T,
        *,
        shift_up: bool = True,
    ) -> None:
        """Delete a row by number or instance. Shift_up=True shifts subsequent rows up."""
        if isinstance(row_number_or_instance, int):
            rn = row_number_or_instance
        else:
            if row_number_or_instance._row_number_ref is None:
                raise UnboundRowError("Cannot delete an unbound row.")
            rn = row_number_or_instance._row_number_ref

        if shift_up:
            self._client.spreadsheets_batch_update(
                self.spreadsheet_id,
                [
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": self.sheet_id,
                                "dimension": "ROWS",
                                "startIndex": rn - 1,
                                "endIndex": rn,
                            }
                        }
                    }
                ],
            )
            # Renumber cached rows above the deleted index
            updated: Dict[int, T] = {}
            updated_order: List[int] = []
            for cached_rn, inst in self._row_instances.items():
                if cached_rn == rn:
                    continue
                new_rn = cached_rn - 1 if cached_rn > rn else cached_rn
                inst._row_number_ref = new_rn
                updated[new_rn] = inst
            self._row_instances = updated
            self._row_order = sorted(updated.keys())
        else:
            self._client.values_clear(
                self.spreadsheet_id,
                self._row_a1_range(rn),
            )
            self._row_instances.pop(rn, None)
            if rn in self._row_order:
                self._row_order.remove(rn)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_put(self, inst: T) -> None:
        rn = inst._row_number_ref
        if rn is None:
            raise ValueError("Cannot cache an unbound row.")
        self._row_instances[rn] = inst
        if rn not in self._row_order:
            self._row_order.append(rn)

    def clear_cache(self) -> None:
        self._row_instances.clear()
        self._row_order.clear()

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def apply_formats_for_model(self) -> None:
        """Apply GSFormat annotations as column-level number formats."""
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
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": s.fmt.number_format_type,
                                    **({"pattern": s.fmt.pattern} if s.fmt.pattern else {}),
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )
        if requests:
            self._client.spreadsheets_batch_update(self.spreadsheet_id, requests)

    # ------------------------------------------------------------------
    # Range helpers
    # ------------------------------------------------------------------

    def _row_a1_range(self, row_number: int) -> str:
        specs = _extract_field_specs(self._model)
        width = _max_index(specs) + 1
        start_col = self.start_column
        end_col = start_col + width - 1
        return (
            f"{self.sheet_name}!"
            f"{col_index_to_a1(start_col)}{row_number}:"
            f"{col_index_to_a1(end_col)}{row_number}"
        )

    def _cell_a1_range(self, row: int, col_index0: int) -> str:
        a1 = col_index_to_a1(col_index0)
        return f"{self.sheet_name}!{a1}{row}:{a1}{row}"

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def _read_row(self, row_number: int) -> T:
        if row_number < 1:
            raise ValueError("row_number must be >= 1")
        rng = self._row_a1_range(row_number)
        resp = self._client.spreadsheets_get_with_grid(self.spreadsheet_id, [rng])
        row_data = (
            resp.get("sheets", [{}])[0]
            .get("data", [{}])[0]
            .get("rowData", [{}])
        )
        values = row_data[0].get("values", []) if row_data else []
        return self._model._from_sheet_values(self, row_number, values)

    def _read_rows(
        self,
        skip_rows_missing_required: bool = True,
        page_size: Optional[int] = None,
    ) -> Generator[T, None, None]:
        specs = _extract_field_specs(self._model)
        width = _max_index(specs) + 1
        start_col = self.start_column
        end_col = start_col + width - 1
        last_row = self.get_last_row_number()

        if page_size:
            # Read in pages
            current = self.start_row
            while current <= last_row:
                end = min(current + page_size - 1, last_row)
                rng = (
                    f"{self.sheet_name}!"
                    f"{col_index_to_a1(start_col)}{current}:"
                    f"{col_index_to_a1(end_col)}{end}"
                )
                resp = self._client.spreadsheets_get_with_grid(self.spreadsheet_id, [rng])
                rows_data = (
                    resp.get("sheets", [{}])[0]
                    .get("data", [{}])[0]
                    .get("rowData", [])
                )
                for offset, row in enumerate(rows_data):
                    row_number = current + offset
                    yield from self._parse_row(
                        row, row_number, skip_rows_missing_required
                    )
                current += page_size
        else:
            rng = (
                f"{self.sheet_name}!"
                f"{col_index_to_a1(start_col)}{self.start_row}:"
                f"{col_index_to_a1(end_col)}{max(self.start_row, last_row)}"
            )
            resp = self._client.spreadsheets_get_with_grid(self.spreadsheet_id, [rng])
            rows_data = (
                resp.get("sheets", [{}])[0]
                .get("data", [{}])[0]
                .get("rowData", [])
            )
            for offset, row in enumerate(rows_data):
                row_number = self.start_row + offset
                yield from self._parse_row(row, row_number, skip_rows_missing_required)

    def _parse_row(
        self,
        row: dict,
        row_number: int,
        skip_rows_missing_required: bool,
    ) -> Generator[T, None, None]:
        try:
            inst = self._model._from_sheet_values(
                self, row_number, row.get("values", [])
            )
            yield inst
        except RequiredValueError as exc:
            if skip_rows_missing_required:
                warnings.warn(
                    f"Row {row_number} skipped: {exc}",
                    RequiredValueSkippedWarning,
                    stacklevel=4,
                )
            else:
                raise

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def _write_rows(self, instances: Iterable[T]) -> None:
        from ..types.smart_chips import SmartChips, split_at_tokens

        last_row = self.get_last_row_number()
        inst_list = list(instances)
        if not inst_list:
            return

        # Assign row numbers to new (unbound) rows
        new_rows: set[int] = set()
        for inst in inst_list:
            if inst._worksheet_ref is not None and inst._worksheet_ref is not self:
                raise WrongWorksheetError(
                    f"Row is bound to a different worksheet."
                )
            if inst._row_number_ref is None:
                last_row += 1
                inst._row_number_ref = last_row
                inst._worksheet_ref = self
                new_rows.add(last_row)

        inst_list.sort(key=lambda r: r._row_number_ref)

        specs = self._model._specs()
        all_cols = {spec.index: spec for spec in specs.values()}
        editable_cols = {spec.index for spec in specs.values() if not spec.readonly}

        requests = []

        for inst in inst_list:
            rn: int = inst._row_number_ref
            row_vals = inst._to_sheet_values()

            for col_idx, cell_val in enumerate(row_vals):
                if col_idx not in all_cols:
                    continue
                # Skip readonly columns on existing rows
                if rn not in new_rows and col_idx not in editable_cols:
                    continue

                spec = all_cols[col_idx]

                if isinstance(cell_val, bool):
                    user_entered_value: dict = {"boolValue": cell_val}
                elif isinstance(cell_val, str):
                    user_entered_value = {"stringValue": cell_val}
                elif cell_val == "" or cell_val is None:
                    user_entered_value = {"stringValue": ""}
                else:
                    user_entered_value = {"numberValue": cell_val}

                data: dict = {
                    "rows": [{"values": [{"userEnteredValue": user_entered_value}]}],
                    "fields": "userEnteredValue",
                }

                if isinstance(cell_val, SmartChips):
                    data["fields"] = "userEnteredValue,chipRuns"
                    format_text = spec.smartchip.format_text if spec.smartchip else "@"
                    sections = [
                        k for k, v in split_at_tokens(format_text.replace("\\@", " ")).items()
                        if v == "@"
                    ]
                    chip_dicts = [
                        {**chip._to_dict(), "startIndex": sections[i]}
                        for i, chip in enumerate(cell_val.chipRuns)
                        if i < len(sections)
                    ]
                    data["rows"] = [
                        {
                            "values": [
                                {
                                    "userEnteredValue": {
                                        "stringValue": format_text.replace("\\@", "@")
                                    },
                                    "chipRuns": chip_dicts,
                                }
                            ]
                        }
                    ]

                elif spec.fmt is not None:
                    if isinstance(cell_val, (date,)):
                        n = datetime_to_gsheets(cell_val)
                    else:
                        try:
                            n = float(cell_val)
                        except (TypeError, ValueError):
                            n = 0.0
                    data["fields"] = "userEnteredValue,userEnteredFormat.numberFormat"
                    data["rows"] = [
                        {
                            "values": [
                                {
                                    "userEnteredValue": {"numberValue": n},
                                    "userEnteredFormat": {
                                        "numberFormat": {
                                            "type": spec.fmt.number_format_type,
                                            **(
                                                {"pattern": spec.fmt.pattern}
                                                if spec.fmt.pattern
                                                else {}
                                            ),
                                        }
                                    },
                                }
                            ]
                        }
                    ]

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

        self._client.spreadsheets_batch_update(self.spreadsheet_id, requests)

        # Refresh cache
        for inst in inst_list:
            self._cache_put(inst)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_last_row_number(self) -> int:
        first_col_a1 = col_index_to_a1(self.start_column)
        rng = f"{self.sheet_name}!{first_col_a1}{self.start_row}:{first_col_a1}"
        resp = self._client.values_get(
            self.spreadsheet_id, rng, majorDimension="ROWS"
        )
        values = resp.get("values", [])
        return self.start_row + len(values) - 1
