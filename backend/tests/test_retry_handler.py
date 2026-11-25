import pytest

from app.services.gemini_client import GeminiAPIError
from app.services.retry_handler import call_with_transient_retries


@pytest.mark.asyncio
async def test_429_then_success_retries_once():
    calls = 0
    waits = []

    async def operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GeminiAPIError(429, "rate limited")
        return "ok"

    async def no_sleep(seconds):
        waits.append(seconds)

    outcome = await call_with_transient_retries(operation, sleep=no_sleep, base_seconds=1)
    assert outcome.value == "ok"
    assert outcome.retries == 1
    assert calls == 2
    assert len(waits) == 1


@pytest.mark.asyncio
async def test_503_stops_after_three_retries():
    calls = 0
    waits = []

    async def operation():
        nonlocal calls
        calls += 1
        raise GeminiAPIError(503, "unavailable")

    async def no_sleep(seconds):
        waits.append(seconds)

    with pytest.raises(GeminiAPIError) as captured:
        await call_with_transient_retries(operation, sleep=no_sleep, base_seconds=1)

    assert calls == 4  # initial request + three retries
    assert len(waits) == 3
    assert captured.value.retry_count == 3


@pytest.mark.asyncio
async def test_non_transient_error_is_not_retried():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise GeminiAPIError(400, "bad request")

    with pytest.raises(GeminiAPIError):
        await call_with_transient_retries(operation, sleep=lambda _: None)
    assert calls == 1
