from __future__ import annotations

import threading
import time


class TokenBucketLimiter:
    """
    Token-bucket rate limiter (thread-safe).

    Google Sheets API quota: 300 requests/60s/project.
    Default: 290 tokens/min with burst=30.
    """

    _DEFAULT_RATE_PER_MIN = 290
    _DEFAULT_BURST = 30

    def __init__(
        self,
        rate_per_minute: int = _DEFAULT_RATE_PER_MIN,
        burst: int = _DEFAULT_BURST,
    ) -> None:
        self._rate = rate_per_minute / 60.0
        self._burst = float(burst)
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            deficit = 1.0 - self._tokens
            wait = deficit / self._rate
            self._tokens = 0.0

        time.sleep(wait)


_default_limiter = TokenBucketLimiter()
