from __future__ import annotations

import functools
import random
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

from googleapiclient.errors import HttpError

from ..exceptions import RateLimitError, TransientAPIError
from .._logging import logger

F = TypeVar("F", bound=Callable)


@dataclass
class RetryConfig:
    max_attempts: int = 5
    initial_delay_s: float = 1.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )


def retry_on_http_error(cfg: RetryConfig = RetryConfig()) -> Callable[[F], F]:
    """Decorator: retry callables that raise HttpError with exponential backoff."""
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = cfg.initial_delay_s
            for attempt in range(1, cfg.max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except HttpError as exc:
                    status = int(exc.resp.status)
                    if status not in cfg.retryable_status_codes:
                        raise
                    if attempt == cfg.max_attempts:
                        if status == 429:
                            raise RateLimitError(
                                f"Rate limit exceeded after {cfg.max_attempts} attempts."
                            ) from exc
                        raise TransientAPIError(
                            f"API error {status} after {cfg.max_attempts} attempts."
                        ) from exc
                    sleep_s = delay + (random.uniform(0, delay * 0.1) if cfg.jitter else 0)
                    logger.warning(
                        "HTTP %d on attempt %d/%d; retrying in %.2fs",
                        status, attempt, cfg.max_attempts, sleep_s,
                    )
                    time.sleep(sleep_s)
                    delay *= cfg.backoff_multiplier
        return wrapper  # type: ignore[return-value]
    return decorator
