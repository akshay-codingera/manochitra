"""Small HTTP client for Google's Gemini generateContent REST endpoint.

Using HTTP directly keeps the request/response contract visible and easy to
explain: endpoint, authentication header, JSON body, status code, text and usage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core import config
from app.core.models import validate_model_id


class MissingAPIKeyError(RuntimeError):
    """Raised when generation is requested without server-side credentials."""


class GeminiAPIError(RuntimeError):
    """An API error with the upstream HTTP status and retry metadata."""

    def __init__(self, status_code: int, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.retry_count = 0


@dataclass
class ModelResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    usage_metadata_available: bool = True
    thinking_tokens: int = 0


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = (api_key if api_key is not None else config.GEMINI_API_KEY).strip()
        self.model = validate_model_id(model or config.GEMINI_MODEL)

    async def generate_svg(self, prompt: str) -> ModelResponse:
        if not self.api_key:
            raise MissingAPIKeyError(
                "GEMINI_API_KEY is missing. Add it to the backend .env file or the hosting environment."
            )

        endpoint = f"{config.GEMINI_API_BASE}/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": config.GEMINI_MAX_OUTPUT_TOKENS,
                "responseMimeType": "text/plain",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=config.GEMINI_TIMEOUT_SECONDS) as client:
                response = await client.post(endpoint, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise GeminiAPIError(408, "Gemini request timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            raise GeminiAPIError(0, f"Could not reach Gemini API: {exc.__class__.__name__}") from exc

        if response.status_code >= 400:
            try:
                payload = response.json()
                message = payload.get("error", {}).get("message", response.text)
            except ValueError:
                message = response.text or "Gemini returned an error."

            retry_after: float | None = None
            header_value = response.headers.get("Retry-After")
            if header_value:
                try:
                    retry_after = float(header_value)
                except ValueError:
                    retry_after = None

            raise GeminiAPIError(response.status_code, str(message), retry_after)

        try:
            payload: dict[str, Any] = response.json()
            candidate = payload["candidates"][0]
            parts = candidate["content"]["parts"]
            text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise GeminiAPIError(502, "Gemini returned a response without usable text content.") from exc

        usage = payload.get("usageMetadata") or {}
        usage_available = (
            isinstance(usage, dict)
            and "promptTokenCount" in usage
            and "candidatesTokenCount" in usage
        )
        thinking_tokens = 0
        if isinstance(usage, dict):
            thinking_tokens = int(usage.get("thoughtsTokenCount") or 0)
            if not thinking_tokens and isinstance(usage.get("candidatesTokensDetails"), dict):
                thinking_tokens = int(usage.get("candidatesTokensDetails", {}).get("thoughtsTokenCount", 0) or 0)

        return ModelResponse(
            text=text,
            input_tokens=int(usage.get("promptTokenCount", 0) or 0),
            output_tokens=int(usage.get("candidatesTokenCount", 0) or 0),
            model=self.model,
            usage_metadata_available=usage_available,
            thinking_tokens=thinking_tokens,
        )
