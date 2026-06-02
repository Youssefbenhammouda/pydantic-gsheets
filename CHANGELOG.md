# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-06-02

### Added
- New API layer with `SheetsClient`, `RetryConfig`, and rate-limiting/retry helpers.
- New auth helpers for service account, ADC, and user OAuth flows.
- New modular core package (`core`, `api`, `auth`, `types`) and package typing marker (`py.typed`).
- Expanded unit test coverage with dedicated tests for core models, auth, retry/rate limiting, and smart chips.

### Changed
- Reorganized package exports in `pydantic_gsheets.__init__` for the new modular API surface.
- Updated documentation pages for auth, worksheet usage, and smart chips.
- Updated package metadata version to `1.0.0`.