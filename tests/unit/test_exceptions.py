"""Tests for exception hierarchy and attribute contracts."""
import pytest
from pydantic_gsheets.exceptions import (
    PydanticGSheetsError, AuthError, PermissionDeniedError,
    SheetDataError, RequiredValueError, ParseError,
    UnboundRowError, WrongWorksheetError, RateLimitError,
    TransientAPIError, SchemaError, RequiredValueSkippedWarning,
)


def test_hierarchy():
    assert issubclass(AuthError, PydanticGSheetsError)
    assert issubclass(PermissionDeniedError, AuthError)
    assert issubclass(SheetDataError, PydanticGSheetsError)
    assert issubclass(RequiredValueError, SheetDataError)
    assert issubclass(ParseError, SheetDataError)
    assert issubclass(UnboundRowError, PydanticGSheetsError)
    assert issubclass(RateLimitError, PydanticGSheetsError)
    assert issubclass(TransientAPIError, PydanticGSheetsError)
    assert issubclass(SchemaError, PydanticGSheetsError)


def test_required_value_error_attributes():
    exc = RequiredValueError("username", 5)
    assert exc.field_name == "username"
    assert exc.row_number == 5
    assert "username" in str(exc)
    assert "5" in str(exc)


def test_required_value_error_custom_message():
    exc = RequiredValueError("email", 3, "custom msg")
    assert str(exc) == "custom msg"


def test_parse_error_attributes():
    cause = ValueError("bad value")
    exc = ParseError("age", 2, cause)
    assert exc.field_name == "age"
    assert exc.col_index == 2
    assert exc.__cause__ is cause
    assert "age" in str(exc)


def test_required_value_skipped_warning_is_warning():
    assert issubclass(RequiredValueSkippedWarning, UserWarning)
