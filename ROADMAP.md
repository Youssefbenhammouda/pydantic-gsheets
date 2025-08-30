# Project Roadmap

This document outlines the planned steps for developing `pydantic-gsheets` from a minimal package to a fully featured library.

## Phase 1: Core Infrastructure
- [X] Implement authentication and connection helpers for the Google Sheets API.
- [X] Create utilities to map rows to Pydantic models and back.
- [X] Support reading data ranges and writing batch updates.
- [X] Support for smart chips.
  - [X] Implement reading smart chips
  - [X] Implement writing smart chips.
- [ ] Add logging.
- [ ] Support rate limiting for Google sheet API.

## Phase 2: Usability Enhancements
- [ ] Provide command-line interface for common operations.
- [ ] Add caching and rate limit handling.
- [ ] Improve error handling and logging.

## Phase 3: Documentation and Testing
- [ ] Write comprehensive usage examples and API documentation.
- [ ] Achieve high test coverage with unit and integration tests.
- [ ] Publish stable releases to PyPI with automated workflows.

