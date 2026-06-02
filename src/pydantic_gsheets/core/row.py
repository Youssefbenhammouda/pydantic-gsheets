from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Type, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError

from ..exceptions import RequiredValueError, UnboundRowError, ParseError
from .._logging import logger
from .converters import gsheets_to_datetime, gsheets_to_date, datetime_to_gsheets
from .field_spec import _extract_field_specs, _max_index, _FieldSpec

if TYPE_CHECKING:
    from .worksheet import GoogleWorkSheet


class SheetRow(BaseModel):
    """
    Base class for typed, annotated rows in a Google Sheet.

    Define fields with Annotated[..., GSIndex(...), GSRequired(), GSParse(...),
    GSFormat(...), GSReadonly(), GSTreatDashAsEmpty()].
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    _worksheet_ref: Optional[Any] = PrivateAttr(default=None)
    _row_number_ref: Optional[int] = PrivateAttr(default=None)

    @classmethod
    def _specs(cls) -> Dict[str, _FieldSpec]:
        cache_key = "_pgs_specs_cache"
        if cache_key not in cls.__dict__:
            type.__setattr__(cls, cache_key, _extract_field_specs(cls))
        return cls.__dict__[cache_key]

    @classmethod
    def _width(cls) -> int:
        return _max_index(cls._specs()) + 1

    @classmethod
    def _from_sheet_values(
        cls,
        worksheet: GoogleWorkSheet,
        row_number: int,
        rowData: Sequence[Any],
    ) -> SheetRow:
        from ..types.smart_chips import (
            SmartChips, richLinkProperties, peopleSmartChip, split_at_tokens,
        )

        specs = cls._specs()
        data: Dict[str, Any] = {}

        for name, spec in specs.items():
            raw: dict = (
                rowData[spec.index]
                if spec.index < len(rowData)
                else {"userEnteredValue": {"stringValue": ""}}
            )

            val = raw.get("formattedValue") or raw.get("userEnteredValue", {}).get("stringValue")

            # Apply custom parser
            if spec.parser and val is not None:
                try:
                    val = spec.parser(val)
                except Exception as exc:
                    raise ParseError(name, spec.index, exc) from exc

            # Dash-as-empty opt-in
            if (
                spec.treat_dash_as_empty
                and isinstance(val, str)
                and val.strip() == "-"
            ):
                val = None

            # Required check on read
            if spec.required and (
                val is None or (isinstance(val, str) and val.strip() == "")
            ):
                raise RequiredValueError(name, row_number)

            # Smart chip field
            if spec.smartchip and spec.smartchip.is_smartchips:
                chips_copy = list(spec.smartchip.smartchips)
                chip_obj = SmartChips(
                    format_text=spec.smartchip.format_text,
                    chipRuns=[],
                    display_text=val,
                )
                raw_chips = list(raw.get("chipRuns", []))

                for part in split_at_tokens(spec.smartchip.format_text).values():
                    if part != "@":
                        continue
                    if not chips_copy:
                        logger.warning(
                            "No smartchip type defined for %s at row %d:%s",
                            spec.smartchip.format_text, row_number, val,
                        )
                        break
                    chip_type = chips_copy.pop(0)
                    matched = False
                    for queried in raw_chips:
                        chip_data = queried.get("chip", {})
                        if chip_type.__fieldName__ in chip_data:
                            raw_chips.remove(queried)
                            if issubclass(chip_type, peopleSmartChip):
                                chip_obj.chipRuns.append(
                                    chip_type(
                                        email=chip_data.get("personProperties", {}).get("email", ""),
                                        display_format=chip_type.displayFormat(
                                            chip_data.get("personProperties", {}).get("displayFormat", "DEFAULT")
                                        ),
                                    )
                                )
                            elif issubclass(chip_type, richLinkProperties):
                                chip_obj.chipRuns.append(
                                    chip_type(
                                        uri=chip_data.get("richLinkProperties", {}).get("uri", ""),
                                    )
                                )
                            matched = True
                            break
                    if not matched:
                        logger.warning(
                            "No smartchip found in sheet for %s at row %d:%s",
                            spec.smartchip.format_text, row_number, val,
                        )

                data[name] = chip_obj

            # Date/datetime field from Sheets serial number
            elif (
                "userEnteredFormat" in raw
                and "numberFormat" in raw.get("userEnteredFormat", {})
                and "DATE" in raw["userEnteredFormat"]["numberFormat"].get("type", "")
            ):
                n = raw.get("effectiveValue", {}).get("numberValue", 0)
                if spec.py_type is date and not (isinstance(spec.py_type, type) and issubclass(spec.py_type, datetime)):
                    data[name] = gsheets_to_date(n)
                else:
                    data[name] = gsheets_to_datetime(n)

            elif val is not None:
                data[name] = val

        inst = cls(**data)
        inst._bind(worksheet, row_number)
        return inst

    def _to_sheet_values(self) -> List[Any]:
        """Convert the instance to a list aligned by GSIndex column positions."""
        from ..types.smart_chips import SmartChips
        specs = self._specs()
        width = self._width()
        out: List[Any] = [""] * width

        for name, spec in specs.items():
            val = getattr(self, name)

            if spec.required and (
                val is None or (isinstance(val, str) and val.strip() == "")
            ):
                raise RequiredValueError(name, self._row_number_ref or 0)

            if isinstance(val, bool):
                out[spec.index] = val
            elif val is None:
                out[spec.index] = ""
            else:
                out[spec.index] = val

        return out

    def _bind(self, worksheet: GoogleWorkSheet, row_number: int) -> None:
        self._worksheet_ref = worksheet
        self._row_number_ref = row_number

    @property
    def row_number(self) -> int:
        if self._row_number_ref is None:
            raise UnboundRowError("Row is not bound to a worksheet yet.")
        return self._row_number_ref

    @property
    def worksheet(self) -> GoogleWorkSheet:
        if self._worksheet_ref is None:
            raise UnboundRowError("Row is not bound to a worksheet yet.")
        return self._worksheet_ref

    def save(self) -> None:
        """Persist the current instance to its bound row in the sheet."""
        if self._worksheet_ref is None:
            raise UnboundRowError(
                "Row is not bound to a worksheet; cannot save. "
                "Use worksheet.append_row(instance) to add a new row."
            )
        self._worksheet_ref._write_rows([self])

    def reload(self) -> None:
        """Refresh the current instance from the sheet."""
        if self._worksheet_ref is None or self._row_number_ref is None:
            raise UnboundRowError("Row is not bound; cannot reload.")
        fresh = self._worksheet_ref._read_row(self._row_number_ref)
        for k, v in fresh.model_dump().items():
            setattr(self, k, v)
