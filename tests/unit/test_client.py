"""Tests for SheetsClient — mocks the googleapiclient Resource."""
import pytest
from unittest.mock import MagicMock, call, patch

from pydantic_gsheets.api.client import SheetsClient, _chunked
from pydantic_gsheets.api.rate_limiter import TokenBucketLimiter
from pydantic_gsheets.api.retry import RetryConfig


def _make_service():
    """Build a deeply mocked googleapiclient Resource."""
    svc = MagicMock()
    return svc


def _make_client(service=None, limiter=None):
    if service is None:
        service = _make_service()
    if limiter is None:
        limiter = MagicMock(spec=TokenBucketLimiter)
    return SheetsClient(service, limiter=limiter, retry_config=RetryConfig(max_attempts=1, jitter=False)), service, limiter


# --- _chunked helper ---

def test_chunked_splits_list_correctly():
    assert list(_chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_chunked_empty_list():
    assert list(_chunked([], 3)) == []


def test_chunked_exact_multiple():
    assert list(_chunked([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]


def test_chunked_larger_than_list():
    assert list(_chunked([1, 2], 10)) == [[1, 2]]


# --- _exec: rate limiter and retry ---

def test_exec_acquires_rate_limiter():
    limiter = MagicMock(spec=TokenBucketLimiter)
    client, svc, _ = _make_client(limiter=limiter)
    mock_request = MagicMock()
    mock_request.execute.return_value = {}
    client._exec(mock_request)
    limiter.acquire.assert_called_once()


def test_exec_calls_request_execute():
    client, svc, limiter = _make_client()
    mock_request = MagicMock()
    mock_request.execute.return_value = {"ok": True}
    result = client._exec(mock_request)
    assert result == {"ok": True}
    mock_request.execute.assert_called_once()


# --- spreadsheets_get ---

def test_spreadsheets_get_calls_correct_endpoint():
    client, svc, limiter = _make_client()
    svc.spreadsheets().get.return_value.execute.return_value = {"spreadsheetId": "abc"}
    result = client.spreadsheets_get("abc")
    svc.spreadsheets().get.assert_called_once_with(spreadsheetId="abc")
    assert result["spreadsheetId"] == "abc"


# --- spreadsheets_batch_update ---

def test_batch_update_calls_correct_endpoint():
    client, svc, limiter = _make_client()
    svc.spreadsheets().batchUpdate.return_value.execute.return_value = {}
    client.spreadsheets_batch_update("sheet1", [{"req": 1}])
    svc.spreadsheets().batchUpdate.assert_called_once_with(
        spreadsheetId="sheet1", body={"requests": [{"req": 1}]}
    )


def test_batch_update_chunks_large_request():
    """Requests > 500 should be split across multiple batchUpdate calls."""
    client, svc, limiter = _make_client()
    svc.spreadsheets().batchUpdate.return_value.execute.return_value = {}
    requests = [{"i": i} for i in range(501)]
    client.spreadsheets_batch_update("sheet1", requests)
    assert svc.spreadsheets().batchUpdate.call_count == 2


# --- values_get ---

def test_values_get_calls_correct_endpoint():
    client, svc, limiter = _make_client()
    svc.spreadsheets().values().get.return_value.execute.return_value = {"values": []}
    result = client.values_get("sid", "Sheet1!A1:Z10")
    svc.spreadsheets().values().get.assert_called_with(
        spreadsheetId="sid", range="Sheet1!A1:Z10"
    )


# --- values_update ---

def test_values_update_calls_correct_endpoint():
    client, svc, limiter = _make_client()
    svc.spreadsheets().values().update.return_value.execute.return_value = {}
    client.values_update("sid", "Sheet1!A1", "RAW", {"values": [["hello"]]})
    svc.spreadsheets().values().update.assert_called_with(
        spreadsheetId="sid",
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": [["hello"]]},
    )


# --- values_clear ---

def test_values_clear_calls_correct_endpoint():
    client, svc, limiter = _make_client()
    svc.spreadsheets().values().clear.return_value.execute.return_value = {}
    client.values_clear("sid", "Sheet1!A1:Z1")
    svc.spreadsheets().values().clear.assert_called_with(
        spreadsheetId="sid", range="Sheet1!A1:Z1", body={}
    )


# --- values_append ---

def test_values_append_calls_correct_endpoint():
    client, svc, limiter = _make_client()
    svc.spreadsheets().values().append.return_value.execute.return_value = {}
    client.values_append("sid", "Sheet1!A1", "USER_ENTERED", {"values": [["a"]]})
    svc.spreadsheets().values().append.assert_called_with(
        spreadsheetId="sid",
        range="Sheet1!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [["a"]]},
    )


# --- spreadsheets_get_with_grid ---

def test_spreadsheets_get_with_grid_passes_include_grid_data():
    client, svc, limiter = _make_client()
    svc.spreadsheets().get.return_value.execute.return_value = {}
    client.spreadsheets_get_with_grid("sid", ["Sheet1!A1:B2"])
    svc.spreadsheets().get.assert_called_with(
        spreadsheetId="sid",
        ranges=["Sheet1!A1:B2"],
        includeGridData=True,
    )
