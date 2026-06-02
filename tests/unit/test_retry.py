"""Tests for retry logic."""
import pytest
from unittest.mock import MagicMock, patch, call
from httplib2 import Response

from pydantic_gsheets.api.retry import RetryConfig, retry_on_http_error
from pydantic_gsheets.exceptions import RateLimitError, TransientAPIError


def _make_http_error(status: int):
    from googleapiclient.errors import HttpError
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"error")


def test_429_exhausted_raises_rate_limit_error():
    cfg = RetryConfig(max_attempts=3, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(429))

    with patch("time.sleep"):
        with pytest.raises(RateLimitError):
            retry_on_http_error(cfg)(fn)()

    assert fn.call_count == 3


def test_400_raises_immediately_no_sleep():
    cfg = RetryConfig(max_attempts=5, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(400))

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(Exception):  # raw HttpError
            retry_on_http_error(cfg)(fn)()

    mock_sleep.assert_not_called()
    assert fn.call_count == 1


def test_503_exhausted_raises_transient_error():
    cfg = RetryConfig(max_attempts=3, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(503))

    with patch("time.sleep"):
        with pytest.raises(TransientAPIError):
            retry_on_http_error(cfg)(fn)()


def test_succeeds_on_third_attempt():
    cfg = RetryConfig(max_attempts=5, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=[
        _make_http_error(429),
        _make_http_error(429),
        "ok",
    ])

    with patch("time.sleep"):
        result = retry_on_http_error(cfg)(fn)()

    assert result == "ok"
    assert fn.call_count == 3
