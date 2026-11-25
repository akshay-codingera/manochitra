"""Bounded retry policy for Gemini HTTP 429 and 503 responses."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from app.core import config
from app.services.gemini_client import GeminiAPIError

T = TypeVar("T")


@dataclass
class RetryOutcome:
    value: T
    retries: int


async def call_with_transient_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = config.MAX_TRANSIENT_RETRIES,
    base_seconds: float = config.RETRY_BASE_SECONDS,
    max_seconds: float = config.RETRY_MAX_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> RetryOutcome:
    """Retry only 429/503, waiting exponentially and respecting Retry-After.

    max_retries=3 means at most four total HTTP attempts: the original request
    plus three retries. Jitter avoids every client retrying at the same instant.
    """
    retries = 0
    while True:
        try:
            return RetryOutcome(value=await operation(), retries=retries)
        except GeminiAPIError as exc:
            if exc.status_code not in (429, 503) or retries >= max_retries:
                exc.retry_count = retries
                raise

            exponential_delay = min(base_seconds * (2 ** retries), max_seconds)
            requested_delay = exc.retry_after if exc.retry_after is not None else exponential_delay
            delay = min(max(requested_delay, 0.0), max_seconds)
            delay += random.uniform(0.0, min(0.25, delay * 0.1)) if delay else 0.0
            retries += 1
            await sleep(delay)
