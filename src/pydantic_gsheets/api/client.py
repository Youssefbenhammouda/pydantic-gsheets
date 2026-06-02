from __future__ import annotations

from typing import Any

from googleapiclient.discovery import Resource

from .rate_limiter import TokenBucketLimiter, _default_limiter
from .retry import RetryConfig, retry_on_http_error
from .._logging import logger

_BATCH_REQUEST_LIMIT = 500


def _chunked(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


class SheetsClient:
    """
    Thin wrapper around a googleapiclient Sheets v4 Resource.
    All HTTP calls pass through the rate limiter and retry decorator.
    """

    def __init__(
        self,
        service: Resource,
        *,
        drive_service: Resource | None = None,
        retry_config: RetryConfig = RetryConfig(),
        limiter: TokenBucketLimiter | None = None,
    ) -> None:
        self._service = service
        self._drive_service = drive_service
        self._retry = retry_on_http_error(retry_config)
        self._limiter = limiter or _default_limiter

    def _exec(self, request: Any) -> dict:
        self._limiter.acquire()
        return self._retry(request.execute)()

    def spreadsheets_get(self, spreadsheet_id: str, **kwargs) -> dict:
        req = self._service.spreadsheets().get(spreadsheetId=spreadsheet_id, **kwargs)
        return self._exec(req)

    def spreadsheets_batch_update(self, spreadsheet_id: str, requests: list[dict]) -> dict:
        result = {}
        for chunk in _chunked(requests, _BATCH_REQUEST_LIMIT):
            req = self._service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": chunk},
            )
            result = self._exec(req)
        return result

    def values_get(self, spreadsheet_id: str, range_: str, **kwargs) -> dict:
        req = self._service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_, **kwargs
        )
        return self._exec(req)

    def values_update(self, spreadsheet_id: str, range_: str, value_input_option: str, body: dict) -> dict:
        req = self._service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption=value_input_option,
            body=body,
        )
        return self._exec(req)

    def values_clear(self, spreadsheet_id: str, range_: str) -> dict:
        req = self._service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=range_, body={}
        )
        return self._exec(req)

    def values_append(self, spreadsheet_id: str, range_: str, value_input_option: str, body: dict) -> dict:
        req = self._service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption=value_input_option,
            body=body,
        )
        return self._exec(req)

    def spreadsheets_get_with_grid(self, spreadsheet_id: str, ranges: list[str]) -> dict:
        req = self._service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=ranges,
            includeGridData=True,
        )
        return self._exec(req)
