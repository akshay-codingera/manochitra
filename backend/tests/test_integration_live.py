"""Live integration tests against the real Gemini API.

These tests are skipped by default unless a valid GEMINI_API_KEY is present
in the environment. They do NOT consume API quota during standard CI or offline runs.
"""

from __future__ import annotations

import os
import pytest

from app.core.concepts import CONCEPTS
from app.core.config import GEMINI_API_KEY
from app.services.gemini_client import GeminiClient
from app.services.generation_pipeline import GenerationPipeline


_HAS_REAL_KEY = bool(
    os.getenv("RUN_LIVE_TESTS") == "1"
    and GEMINI_API_KEY
    and not GEMINI_API_KEY.startswith("test-")
    and len(GEMINI_API_KEY) > 10
)


@pytest.mark.skipif(not _HAS_REAL_KEY, reason="Live tests require RUN_LIVE_TESTS=1 and a configured GEMINI_API_KEY.")
@pytest.mark.asyncio
async def test_live_gemini_client_smoke():
    """Verify live connectivity and structured token usage metadata extraction."""
    client = GeminiClient(api_key=GEMINI_API_KEY, model="gemini-3.5-flash-lite")
    response = await client.generate_svg("Respond with the exact word 'READY' and nothing else.")
    assert "READY" in response.text
    assert response.input_tokens > 0
    assert response.output_tokens > 0
    assert response.usage_metadata_available is True


@pytest.mark.skipif(not _HAS_REAL_KEY, reason="Live tests require RUN_LIVE_TESTS=1 and a configured GEMINI_API_KEY.")
@pytest.mark.asyncio
async def test_live_pipeline_single_concept():
    """Verify end-to-end generation for a single concept with real Gemini model."""
    client = GeminiClient(api_key=GEMINI_API_KEY, model="gemini-3.5-flash-lite")
    pipeline = GenerationPipeline(client=client)
    result = await pipeline.generate("circle", model="gemini-3.5-flash-lite")
    assert result["concept_id"] == "circle"
    assert result["model"] == "gemini-3.5-flash-lite"
    assert len(result["checks"]) == 6
    assert result["usage"]["metadata_available"] is True
    assert result["usage"]["input_tokens"] > 0
    assert result["usage"]["output_tokens"] > 0
    assert isinstance(result["cost"]["estimated_cost_usd"], float)
