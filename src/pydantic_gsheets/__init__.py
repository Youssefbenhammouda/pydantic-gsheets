"""pydantic-gsheets: type-safe Google Sheets integration for Pydantic models."""
from __future__ import annotations

from .core.row import SheetRow
from .core.worksheet import GoogleWorkSheet
from .core.descriptors import (
    GSIndex, GSRequired, GSParse, GSFormat, GSReadonly, GSTreatDashAsEmpty,
)
from .core.converters import gsheets_to_datetime, gsheets_to_date, datetime_to_gsheets
from .auth.credentials import (
    credentials_from_service_account_file,
    credentials_from_service_account_info,
    credentials_from_adc,
    credentials_from_user_oauth,
    build_sheets_service,
    build_drive_service,
)
from .auth._scopes import SHEETS_RW, SHEETS_RO, DRIVE_FULL, DRIVE_FILE
from .types.smart_chips import (
    SmartChips, smartChips,
    SmartChipConfig, smartchipConf,
    GSSmartChip, GS_SMARTCHIP,
    fileSmartChip, FileSmartChip,
    peopleSmartChip, PeopleSmartChip,
    eventSmartChip, EventSmartChip,
    placeSmartChip, PlaceSmartChip,
    youtubeSmartChip, YouTubeSmartChip,
    richLinkProperties, RichLinkProperties,
)
from .api.retry import RetryConfig
from .api.client import SheetsClient
from .exceptions import (
    PydanticGSheetsError, AuthError, PermissionDeniedError,
    SheetDataError, RequiredValueError, ParseError,
    UnboundRowError, WrongWorksheetError,
    RateLimitError, TransientAPIError, SchemaError,
    RequiredValueSkippedWarning,
)

__all__ = [
    # Core
    "SheetRow", "GoogleWorkSheet",
    # Descriptors
    "GSIndex", "GSRequired", "GSParse", "GSFormat", "GSReadonly", "GSTreatDashAsEmpty",
    # Auth
    "credentials_from_service_account_file", "credentials_from_service_account_info",
    "credentials_from_adc", "credentials_from_user_oauth",
    "build_sheets_service", "build_drive_service",
    # Scopes
    "SHEETS_RW", "SHEETS_RO", "DRIVE_FULL", "DRIVE_FILE",
    # Smart chips
    "SmartChips", "SmartChipConfig", "GSSmartChip",
    "FileSmartChip", "PeopleSmartChip", "EventSmartChip", "PlaceSmartChip", "YouTubeSmartChip",
    "RichLinkProperties",
    # Converters
    "gsheets_to_datetime", "gsheets_to_date", "datetime_to_gsheets",
    # Errors
    "PydanticGSheetsError", "AuthError", "PermissionDeniedError",
    "SheetDataError", "RequiredValueError", "ParseError",
    "UnboundRowError", "WrongWorksheetError",
    "RateLimitError", "TransientAPIError", "SchemaError",
    "RequiredValueSkippedWarning",
    # Config / client
    "RetryConfig", "SheetsClient",
]
