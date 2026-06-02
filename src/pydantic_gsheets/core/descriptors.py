from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..exceptions import SchemaError


@dataclass(frozen=True)
class GSIndex:
    """Zero-based column offset relative to start_column."""
    index: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("GSIndex must be >= 0")

    def __repr__(self) -> str:
        return f"GSIndex({self.index})"


class GSRequired:
    """Mark a field as required — must not be empty on read or write."""

    def __init__(self, message: str = "Required value is missing.") -> None:
        self.message = message

    def __repr__(self) -> str:
        return f"GSRequired({self.message!r})"

    def __class_getitem__(cls, item: Any) -> Any:
        raise SchemaError(
            "GSRequired must be instantiated: use GSRequired() not GSRequired[...]."
        )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise SchemaError("GSRequired should not be subclassed.")


@dataclass(frozen=True)
class GSParse:
    """Apply a custom parsing function to the raw cell string before Pydantic validation."""
    func: Callable[[Any], Any]

    def __repr__(self) -> str:
        return f"GSParse({self.func!r})"


@dataclass(frozen=True)
class GSFormat:
    """Apply a Google Sheets number format to this column."""
    number_format_type: str
    pattern: Optional[str] = None

    def __repr__(self) -> str:
        return f"GSFormat({self.number_format_type!r}, {self.pattern!r})"


@dataclass(frozen=True)
class GSReadonly:
    """Column is read-only; never written back to the sheet."""

    def __repr__(self) -> str:
        return "GSReadonly()"


@dataclass(frozen=True)
class GSTreatDashAsEmpty:
    """Opt-in: treat the literal string '-' as an empty/None value for this field."""

    def __repr__(self) -> str:
        return "GSTreatDashAsEmpty()"
