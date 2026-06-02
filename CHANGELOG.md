# Changelog

## [1.0.0] – 2026-06-02

First stable release.

### New features

- **4 auth patterns** — service account file, service account info dict, Application Default Credentials (ADC), and browser OAuth2 (`credentials_from_*` factory functions replacing the old `AuthConfig`).
- **Named scope constants** — `SHEETS_RW`, `SHEETS_RO`, `DRIVE_FULL`, `DRIVE_FILE`; default is `(SHEETS_RW, DRIVE_FILE)` (principle of least privilege).
- **Full error hierarchy** — `PydanticGSheetsError`, `AuthError`, `PermissionDeniedError`, `SheetDataError`, `RequiredValueError` (with `.field_name` / `.row_number` attributes), `ParseError`, `UnboundRowError`, `WrongWorksheetError`, `RateLimitError`, `TransientAPIError`, `SchemaError`, `RequiredValueSkippedWarning`.
- **Retry with exponential backoff** — configurable via `RetryConfig` (max attempts, initial delay, multiplier, jitter); retries on 429/500/502/503/504.
- **Token-bucket rate limiter** — 290 req/min, burst=30, thread-safe; applied automatically to every API call.
- **New row operations** — `append_row()`, `append_rows()`, `delete_row(shift_up=True)`.
- **Pagination** — `rows(page_size=N)` for chunked reads on large sheets.
- **`GSTreatDashAsEmpty()`** — opt-in per-field descriptor; `"-"` is no longer silently treated as empty without it.
- **`GSReadonly()`** — columns excluded from writes.
- **Smart chip types** — `FileSmartChip`, `PeopleSmartChip`, `EventSmartChip`, `PlaceSmartChip`, `YouTubeSmartChip`; read-only chip types raise `NotImplementedError` on write instead of silently failing.
- **`py.typed` marker** (PEP 561) — inline type information for mypy / Pylance / Pyright.
- **Strict generic annotations** — `GoogleWorkSheet[T]` fully annotated so IDEs resolve `T` at the call site.
- **Library logger** — `logging.getLogger("pydantic_gsheets")` with `NullHandler`; replaces all `print()` calls.

### Bug fixes

- `gsheets_to_datetime()` previously returned a `date` (time component silently dropped). Now returns a naive `datetime`; use `gsheets_to_date()` for `date`-only fields.
- `datetime_to_gsheets()` now strips microseconds (Sheets serial numbers have ~1-second precision), preventing round-trip equality failures.
- `GSRequired` used as a bare class (no `()`) now raises `SchemaError` at model definition time instead of silently being ignored.
- `ValidationError` from Pydantic is no longer re-wrapped as `ValueError` — callers receive it directly.
- `save()` / `reload()` on an unbound row raises `UnboundRowError` with a clear message instead of `AttributeError`.
- `_validate_access` no longer writes a temporary marker cell to check write permission; uses a no-op `batchUpdate` instead.
- Batch write requests are chunked at 500 to avoid Sheets API request-size limits.

### Breaking changes

| # | Old | New |
|---|---|---|
| 1 | `AuthConfig` + `get_sheets_service(cfg)` | `credentials_from_*()` + `build_sheets_service(creds)` — old API kept with `DeprecationWarning` |
| 2 | `gsheets_to_datetime()` returns `date` | Returns `datetime`; use `gsheets_to_date()` for `date` |
| 3 | `ValidationError` re-wrapped as `ValueError` | `pydantic.ValidationError` raised directly |
| 4 | `RequiredValueError` message-only | Now has `.field_name` and `.row_number` attributes |
| 5 | `skip_rows_missing_required=True` silent drop | Emits `RequiredValueSkippedWarning` |
| 6 | `"-"` silently treated as empty | Passes through unchanged; opt in with `GSTreatDashAsEmpty()` |
| 7 | `GoogleWorkSheet(model, service, ...)` | `GoogleWorkSheet(model, SheetsClient(service), ...)` |
| 8 | `from pydantic_gsheets.types.smartChips_ import ...` | `from pydantic_gsheets.types.smart_chips import ...` |
| 9 | `smartchipConf` / `GS_SMARTCHIP` | `SmartChipConfig` / `GSSmartChip` — old names aliased with `DeprecationWarning` |
| 10 | `noWriteSupport` raised `ValueError` | Raises `NotImplementedError` with a descriptive message |
