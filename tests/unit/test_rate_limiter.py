"""Tests for token bucket rate limiter."""
import time
import pytest
from unittest.mock import patch
from pydantic_gsheets.api.rate_limiter import TokenBucketLimiter


def test_acquire_immediate_when_tokens_available():
    limiter = TokenBucketLimiter(rate_per_minute=290, burst=30)
    # Should not sleep — tokens available
    with patch("time.sleep") as mock_sleep:
        limiter.acquire()
    mock_sleep.assert_not_called()


def test_acquire_sleeps_when_depleted():
    limiter = TokenBucketLimiter(rate_per_minute=60, burst=1)
    limiter.acquire()  # use the single burst token
    with patch("time.sleep") as mock_sleep:
        limiter.acquire()
    mock_sleep.assert_called_once()
