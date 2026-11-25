import httpx
import pytest

from app.services.gemini_client import GeminiAPIError, GeminiClient, MissingAPIKeyError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=''):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, response=None, error=None, **kwargs):
        self.response = response
        self.error = error
        self.kwargs = kwargs
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, endpoint, headers, json):
        self.request = {"endpoint": endpoint, "headers": headers, "json": json}
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_missing_key_fails_before_network_call():
    client = GeminiClient(api_key='', model='gemini-3.5-flash-lite')
    with pytest.raises(MissingAPIKeyError):
        await client.generate_svg('make a diagram')


@pytest.mark.asyncio
async def test_successful_response_extracts_text_and_token_usage(monkeypatch):
    response = FakeResponse(payload={
        "candidates": [{"content": {"parts": [{"text": "<svg></svg>"}]}}],
        "usageMetadata": {"promptTokenCount": 31, "candidatesTokenCount": 72},
    })
    fake = FakeAsyncClient(response=response)
    monkeypatch.setattr('app.services.gemini_client.httpx.AsyncClient', lambda **kwargs: fake)

    result = await GeminiClient(api_key='secret-not-returned', model='gemini-3.5-flash-lite').generate_svg('prompt')

    assert result.text == '<svg></svg>'
    assert result.input_tokens == 31
    assert result.output_tokens == 72
    assert result.model == 'gemini-3.5-flash-lite'
    assert fake.request['headers']['x-goog-api-key'] == 'secret-not-returned'
    assert 'secret-not-returned' not in result.text


@pytest.mark.asyncio
async def test_http_error_extracts_message_and_retry_after(monkeypatch):
    response = FakeResponse(
        status_code=429,
        payload={"error": {"message": "rate limit reached"}},
        headers={"Retry-After": "2"},
    )
    fake = FakeAsyncClient(response=response)
    monkeypatch.setattr('app.services.gemini_client.httpx.AsyncClient', lambda **kwargs: fake)

    with pytest.raises(GeminiAPIError) as caught:
        await GeminiClient(api_key='x').generate_svg('prompt')
    assert caught.value.status_code == 429
    assert str(caught.value) == 'rate limit reached'
    assert caught.value.retry_after == 2.0


@pytest.mark.asyncio
async def test_timeout_is_translated_to_controlled_api_error(monkeypatch):
    fake = FakeAsyncClient(error=httpx.ReadTimeout('timed out'))
    monkeypatch.setattr('app.services.gemini_client.httpx.AsyncClient', lambda **kwargs: fake)
    with pytest.raises(GeminiAPIError) as caught:
        await GeminiClient(api_key='x').generate_svg('prompt')
    assert caught.value.status_code == 408


@pytest.mark.asyncio
async def test_network_error_is_translated_to_controlled_api_error(monkeypatch):
    fake = FakeAsyncClient(error=httpx.ConnectError('offline'))
    monkeypatch.setattr('app.services.gemini_client.httpx.AsyncClient', lambda **kwargs: fake)
    with pytest.raises(GeminiAPIError) as caught:
        await GeminiClient(api_key='x').generate_svg('prompt')
    assert caught.value.status_code == 0


@pytest.mark.asyncio
async def test_invalid_model_response_is_translated_to_bad_gateway(monkeypatch):
    fake = FakeAsyncClient(response=FakeResponse(payload={"candidates": []}))
    monkeypatch.setattr('app.services.gemini_client.httpx.AsyncClient', lambda **kwargs: fake)
    with pytest.raises(GeminiAPIError) as caught:
        await GeminiClient(api_key='x').generate_svg('prompt')
    assert caught.value.status_code == 502


@pytest.mark.asyncio
async def test_missing_usage_metadata_is_not_reported_as_zero_cost_data(monkeypatch):
    response = FakeResponse(payload={
        "candidates": [{"content": {"parts": [{"text": "<svg></svg>"}]}}],
    })
    fake = FakeAsyncClient(response=response)
    monkeypatch.setattr('app.services.gemini_client.httpx.AsyncClient', lambda **kwargs: fake)
    result = await GeminiClient(api_key='x').generate_svg('prompt')
    assert result.usage_metadata_available is False
    assert result.input_tokens == 0
    assert result.output_tokens == 0
