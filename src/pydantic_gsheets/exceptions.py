"""Library-wide exception and warning hierarchy."""
from __future__ import annotations


class PydanticGSheetsError(Exception):
    """Base for all pydantic-gsheets errors."""


class AuthError(PydanticGSheetsError):
    """Credential or permission problem."""


class PermissionDeniedError(AuthError):
    """HTTP 403 returned by Sheets/Drive API."""


class SheetDataError(PydanticGSheetsError):
    """Problem with data read from or written to a sheet."""


class RequiredValueError(SheetDataError):
    """A GSRequired field was empty during read or write."""

    def __init__(self, field_name: str, row_number: int, message: str = "") -> None:
        self.field_name = field_name
        self.row_number = row_number
        super().__init__(
            message or f"Required field '{field_name}' is empty at row {row_number}."
        )


class ParseError(SheetDataError):
    """A GSParse callable raised an exception."""

    def __init__(self, field_name: str, col_index: int, cause: Exception) -> None:
        self.field_name = field_name
        self.col_index = col_index
        super().__init__(
            f"Parse error for field '{field_name}' at column {col_index}: {cause}"
        )
        self.__cause__ = cause


class UnboundRowError(PydanticGSheetsError):
    """save()/reload() called on a row not bound to a worksheet."""


class WrongWorksheetError(PydanticGSheetsError):
    """Row was passed to a worksheet it was not loaded from."""


class RateLimitError(PydanticGSheetsError):
    """429 RESOURCE_EXHAUSTED raised after all retry attempts are exhausted."""


class TransientAPIError(PydanticGSheetsError):
    """5xx or other retryable HTTP error that persisted past the retry budget."""


class SchemaError(PydanticGSheetsError):
    """Model definition is invalid (duplicate index, misused annotation, etc.)."""


class RequiredValueSkippedWarning(UserWarning):
    """Emitted when a row is skipped because a required field is empty."""
