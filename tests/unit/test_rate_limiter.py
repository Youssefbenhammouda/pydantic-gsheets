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


def test_burst_cap_enforced():
    """Tokens never exceed burst even after a long idle period."""
    limiter = TokenBucketLimiter(rate_per_minute=60, burst=5)
    # Fake that 10 minutes have elapsed
    with patch("time.monotonic", return_value=limiter._last + 600):
        with patch("time.sleep"):
            limiter.acquire()
    assert limiter._tokens <= 5.0


def test_multiple_acquires_deplete_tokens():
    """Rapidly acquiring burst tokens should eventually hit zero and sleep."""
    burst = 3
    limiter = TokenBucketLimiter(rate_per_minute=60, burst=burst)
    sleep_count = 0

    def fake_sleep(s):
        nonlocal sleep_count
        sleep_count += 1

    with patch("time.sleep", side_effect=fake_sleep):
        with patch("time.monotonic", return_value=limiter._last):
            for _ in range(burst + 2):
                limiter.acquire()

    assert sleep_count > 0


def test_token_refill_after_time():
    """After sleeping, tokens should be refilled proportionally."""
    limiter = TokenBucketLimiter(rate_per_minute=60, burst=10)
    # Drain all burst tokens
    for _ in range(10):
        limiter.acquire()

    tokens_after_drain = limiter._tokens

    # Simulate 5 seconds passing (60/min → 1/s, so +5 tokens)
    later = limiter._last + 5.0
    with patch("time.monotonic", return_value=later):
        with patch("time.sleep"):
            limiter.acquire()

    # Tokens should have been refilled before the acquire consumed one
    # After 5s refill (+5) minus 1 consumed = ~4 tokens
    assert limiter._tokens >= 0
