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


def test_first_try_success_no_sleep():
    cfg = RetryConfig(max_attempts=5, initial_delay_s=1.0, jitter=False)
    fn = MagicMock(return_value="ok")

    with patch("time.sleep") as mock_sleep:
        result = retry_on_http_error(cfg)(fn)()

    assert result == "ok"
    mock_sleep.assert_not_called()
    assert fn.call_count == 1


def test_500_retries_then_raises_transient():
    cfg = RetryConfig(max_attempts=3, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(500))

    with patch("time.sleep"):
        with pytest.raises(TransientAPIError):
            retry_on_http_error(cfg)(fn)()

    assert fn.call_count == 3


def test_502_retries_then_raises_transient():
    cfg = RetryConfig(max_attempts=2, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(502))

    with patch("time.sleep"):
        with pytest.raises(TransientAPIError):
            retry_on_http_error(cfg)(fn)()


def test_504_retries_then_raises_transient():
    cfg = RetryConfig(max_attempts=2, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(504))

    with patch("time.sleep"):
        with pytest.raises(TransientAPIError):
            retry_on_http_error(cfg)(fn)()


def test_403_raises_immediately():
    cfg = RetryConfig(max_attempts=5, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(403))

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(Exception):
            retry_on_http_error(cfg)(fn)()

    mock_sleep.assert_not_called()
    assert fn.call_count == 1


def test_404_raises_immediately():
    cfg = RetryConfig(max_attempts=5, initial_delay_s=0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(404))

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(Exception):
            retry_on_http_error(cfg)(fn)()

    mock_sleep.assert_not_called()


def test_backoff_grows_exponentially():
    """Sleep durations should double on each retry (jitter=False)."""
    cfg = RetryConfig(max_attempts=4, initial_delay_s=1.0, backoff_multiplier=2.0, jitter=False)
    fn = MagicMock(side_effect=_make_http_error(503))
    sleep_calls = []

    with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        with pytest.raises(TransientAPIError):
            retry_on_http_error(cfg)(fn)()

    # 3 sleeps for 4 attempts: 1.0, 2.0, 4.0
    assert len(sleep_calls) == 3
    assert sleep_calls[1] == pytest.approx(sleep_calls[0] * 2.0)
    assert sleep_calls[2] == pytest.approx(sleep_calls[1] * 2.0)


def test_jitter_varies_sleep():
    """With jitter=True, consecutive sleep values should differ."""
    import random
    cfg = RetryConfig(max_attempts=5, initial_delay_s=1.0, backoff_multiplier=1.0, jitter=True)
    fn = MagicMock(side_effect=_make_http_error(503))
    sleep_calls = []

    random.seed(99)
    with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        with pytest.raises(TransientAPIError):
            retry_on_http_error(cfg)(fn)()

    # All sleeps are in [1.0, 1.1]; with jitter they needn't all be equal
    assert all(1.0 <= s <= 1.1 + 1e-9 for s in sleep_calls)
