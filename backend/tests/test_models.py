"""Comprehensive tests for the multi-model Gemini selection system and pricing engine."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.core.concepts import CONCEPTS
from app.core.models import (
    ALLOWED_MODEL_IDS,
    DEFAULT_MODEL_ID,
    MODEL_CATALOGUE,
    calculate_token_cost,
    get_model_info,
    get_rates_for_date,
    validate_model_id,
)
from app.main import app
from app.services.gemini_client import GeminiAPIError, GeminiClient, ModelResponse
from app.services.generation_pipeline import GenerationPipeline

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_initial


client = TestClient(app)


# 1. Both models present in catalogue
def test_both_models_present_in_catalogue():
    assert "gemini-3.5-flash-lite" in MODEL_CATALOGUE
    assert "gemini-3.8-flash" in MODEL_CATALOGUE
    assert len(MODEL_CATALOGUE) == 2
    assert ALLOWED_MODEL_IDS == frozenset({"gemini-3.5-flash-lite", "gemini-3.8-flash"})

    lite = MODEL_CATALOGUE["gemini-3.5-flash-lite"]
    assert lite["name"] == "Gemini 3.5 Flash-Lite"
    assert lite["role"] == "Efficient, cost-conscious generation."
    assert lite["free_tier_listed"] is True
    assert lite["account_access_status"] == "UNVERIFIED"

    flash = MODEL_CATALOGUE["gemini-3.8-flash"]
    assert flash["name"] == "Gemini 3.8 Flash"
    assert flash["role"] == "Higher-capability generation."
    assert flash["free_tier_listed"] is True
    assert flash["account_access_status"] == "UNVERIFIED"


# 2. Default model selection
def test_default_model_selection():
    assert DEFAULT_MODEL_ID == "gemini-3.5-flash-lite"
    assert validate_model_id(None) == DEFAULT_MODEL_ID
    assert validate_model_id("") == DEFAULT_MODEL_ID
    assert validate_model_id("   ") == DEFAULT_MODEL_ID


# 3. Valid model acceptance
def test_valid_model_acceptance():
    assert validate_model_id("gemini-3.5-flash-lite") == "gemini-3.5-flash-lite"
    assert validate_model_id("gemini-3.8-flash") == "gemini-3.8-flash"
    assert validate_model_id("  gemini-3.8-flash  ") == "gemini-3.8-flash"


# 4. Invalid model rejection
def test_invalid_model_rejection():
    with pytest.raises(ValueError, match="Unsupported model 'gpt-4'"):
        validate_model_id("gpt-4")
    with pytest.raises(ValueError, match="Unsupported model 'gemini-1.5-pro'"):
        validate_model_id("gemini-1.5-pro")


# 5. Deprecated alias rejection
def test_deprecated_alias_rejection():
    with pytest.raises(ValueError, match="deprecated alias"):
        validate_model_id("gemini-3.5-flash")


# 6. Correct API endpoint model routing
@pytest.mark.asyncio
async def test_correct_api_endpoint_model_routing():
    client_lite = GeminiClient(api_key="test-key", model="gemini-3.5-flash-lite")
    assert client_lite.model == "gemini-3.5-flash-lite"

    client_flash = GeminiClient(api_key="test-key", model="gemini-3.8-flash")
    assert client_flash.model == "gemini-3.8-flash"

    # Mock httpx.AsyncClient to verify endpoint URL constructed
    mock_post_response = MagicMock()
    mock_post_response.status_code = 200
    mock_post_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "<svg></svg>"}]}}],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 200},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_post_response
        await client_flash.generate_svg("Test prompt")
        mock_post.assert_called_once()
        endpoint_called = mock_post.call_args[0][0]
        assert "models/gemini-3.8-flash:generateContent" in endpoint_called


# 7. Same model during HTTP retries
@pytest.mark.asyncio
async def test_same_model_during_http_retries():
    pipeline = GenerationPipeline(client=GeminiClient(api_key="test-key", model="gemini-3.8-flash"))

    attempts = []

    def mock_generate_svg(prompt: str):
        attempts.append(pipeline.client.model)
        if len(attempts) < 2:
            raise GeminiAPIError(429, "Rate limit", retry_after=0.01)
        return ModelResponse(
            text="<svg xmlns='http://www.w3.org/2000/svg'><title>T</title><desc>D</desc><text x='10' y='20'>a</text><text x='10' y='40'>b</text><text x='10' y='60'>c</text><text x='10' y='80'>d</text></svg>",
            input_tokens=100,
            output_tokens=150,
            model=pipeline.client.model,
        )

    with patch.object(pipeline.client, "generate_svg", side_effect=mock_generate_svg), \
         patch("app.services.retry_handler.asyncio.sleep", new_callable=AsyncMock):
        result = await pipeline.generate("circle", model="gemini-3.8-flash")
        assert len(attempts) >= 2
        assert all(m == "gemini-3.8-flash" for m in attempts)
        assert result["model"] == "gemini-3.8-flash"


# 8. Same model during validation repair
@pytest.mark.asyncio
async def test_same_model_during_validation_repair():
    pipeline = GenerationPipeline(client=GeminiClient(api_key="test-key", model="gemini-3.8-flash"))
    call_models = []

    def mock_generate_svg(prompt: str):
        call_models.append(pipeline.client.model)
        if len(call_models) == 1:
            # First attempt fails validation (no text)
            return ModelResponse(
                text="<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                input_tokens=100,
                output_tokens=100,
                model=pipeline.client.model,
            )
        # Second attempt (repair)
        return ModelResponse(
            text="<svg xmlns='http://www.w3.org/2000/svg'><title>T</title><desc>D</desc><text x='10' y='20'>a</text><text x='10' y='40'>b</text><text x='10' y='60'>c</text><text x='10' y='80'>d</text></svg>",
            input_tokens=150,
            output_tokens=150,
            model=pipeline.client.model,
        )

    with patch.object(pipeline.client, "generate_svg", side_effect=mock_generate_svg):
        result = await pipeline.generate("circle", model="gemini-3.8-flash")
        assert len(call_models) == 2
        assert all(m == "gemini-3.8-flash" for m in call_models)
        assert result["model"] == "gemini-3.8-flash"


# 9. Model recorded in attempt history
@pytest.mark.asyncio
async def test_model_recorded_in_attempt_history():
    pipeline = GenerationPipeline(client=GeminiClient(api_key="test-key", model="gemini-3.8-flash"))

    responses = [
        ModelResponse(text="<svg></svg>", input_tokens=100, output_tokens=50, model="gemini-3.8-flash"),
        ModelResponse(text="<svg><title>T</title></svg>", input_tokens=120, output_tokens=80, model="gemini-3.8-flash"),
    ]

    with patch.object(pipeline.client, "generate_svg", side_effect=responses):
        result = await pipeline.generate("circle", model="gemini-3.8-flash")
        assert len(result["attempt_history"]) == 2
        for attempt in result["attempt_history"]:
            assert attempt["model"] == "gemini-3.8-flash"


# 10. Model-specific cost calculation
def test_model_specific_cost_calculation():
    # 1M input, 1M output on Flash-Lite (as of 2026-11-25)
    cost_lite = calculate_token_cost(1_000_000, 1_000_000, "gemini-3.5-flash-lite", billing_tier="paid")
    assert cost_lite["paid_equivalent_cost_usd"] == pytest.approx(0.30 + 2.50)

    # 1M input, 1M output on Flash (2026 rates: $0.75 in, $3.75 out)
    cost_flash = calculate_token_cost(1_000_000, 1_000_000, "gemini-3.8-flash", billing_tier="paid", as_of_date=date(2026, 11, 25))
    assert cost_flash["paid_equivalent_cost_usd"] == pytest.approx(0.75 + 3.75)


# 11. Effective-dated pricing changes
def test_effective_dated_pricing_changes():
    # 2026 rates for Gemini 3.8 Flash
    r_in_2026, r_out_2026 = get_rates_for_date("gemini-3.8-flash", as_of_date=date(2026, 12, 31))
    assert r_in_2026 == 0.75
    assert r_out_2026 == 3.75

    # 2027 rates for Gemini 3.8 Flash
    r_in_2027, r_out_2027 = get_rates_for_date("gemini-3.8-flash", as_of_date=date(2027, 1, 1))
    assert r_in_2027 == 1.50
    assert r_out_2027 == 7.50

    cost_2027 = calculate_token_cost(1_000_000, 1_000_000, "gemini-3.8-flash", billing_tier="paid", as_of_date=date(2027, 2, 1))
    assert cost_2027["paid_equivalent_cost_usd"] == pytest.approx(1.50 + 7.50)


# 12. Missing usage metadata
def test_missing_usage_metadata():
    cost = calculate_token_cost(0, 0, "gemini-3.5-flash-lite", usage_metadata_available=False)
    assert cost["estimated_cost_usd"] is None
    assert cost["paid_equivalent_cost_usd"] is None
    assert cost["usage_metadata_available"] is False
    assert "Unavailable" in cost["pricing_assumption"]


# 13. GET /api/models endpoint
def test_get_api_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) == 2
    model_ids = [m["id"] for m in data["models"]]
    assert "gemini-3.5-flash-lite" in model_ids
    assert "gemini-3.8-flash" in model_ids
    assert data["default_model"] in ALLOWED_MODEL_IDS
    assert "allowed_ids" in data


# 14. Diagnostics without secrets
def test_diagnostics_without_secrets():
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    diag = response.json()
    assert "supported_models" in diag
    assert "gemini-3.5-flash-lite" in diag["supported_models"]
    assert "gemini-3.8-flash" in diag["supported_models"]
    assert "api_key" not in str(diag).lower() or diag.get("api_key_configured") is not None
    assert config.GEMINI_API_KEY not in str(diag)


# API POST generate validation tests
def test_api_generate_accepts_valid_model():
    mock_pipeline = MagicMock()
    mock_pipeline.generate = AsyncMock(return_value={
        "concept_id": "circle",
        "concept": "Circle",
        "status": "PASS",
        "model": "gemini-3.8-flash",
        "svg": "<svg></svg>",
        "checks": {},
        "usage": {"input_tokens": 100, "output_tokens": 200, "metadata_available": True},
        "cost": {},
        "retries": {"total_retries": 0},
        "latency_ms": 1000,
    })

    with patch("app.api.routes.pipeline", mock_pipeline), \
         patch("app.api.routes.repository"), \
         patch("app.api.routes.model_runs_repository"):
        # JSON body request
        res = client.post("/api/generate/circle", json={"model": "gemini-3.8-flash"})
        assert res.status_code == 200
        mock_pipeline.generate.assert_called_with("circle", model="gemini-3.8-flash")


def test_api_generate_rejects_invalid_model():
    res = client.post("/api/generate/circle", json={"model": "invalid-engine"})
    assert res.status_code == 400
    assert "Unsupported model" in res.json()["detail"]


def test_api_generate_rejects_deprecated_model():
    res = client.post("/api/generate/circle", json={"model": "gemini-3.5-flash"})
    assert res.status_code == 400
    assert "deprecated alias" in res.json()["detail"]


# 15. Batch model selection
@pytest.mark.asyncio
async def test_batch_model_selection():
    mock_repo = MagicMock()

    mock_pipeline = MagicMock()
    fake_result = {
        "concept_id": "circle",
        "concept_name": "Circle",
        "status": "PASS",
        "model": "gemini-3.8-flash",
        "checks": {"c1": {"passed": True}},
        "usage": {"input_tokens": 100, "output_tokens": 100, "metadata_available": True},
        "cost": {"estimated_cost_usd": 0.001},
        "retries": {"total_retries": 0},
        "latency_ms": 1000,
        "last_error": None,
    }
    mock_pipeline.generate = AsyncMock(return_value=fake_result)
    mock_repo.all.return_value = [fake_result]

    with patch("generate_initial.GEMINI_API_KEY", "test-key"), \
         patch("generate_initial.CONCEPTS", [{"id": "circle", "name": "Circle", "subject": "Maths"}]), \
         patch("generate_initial.ResultsRepository", return_value=mock_repo), \
         patch("generate_initial.GenerationPipeline", return_value=mock_pipeline):

        code = await generate_initial.run(force=False, model="gemini-3.8-flash")
        assert code == 0
        mock_pipeline.generate.assert_called_once_with("circle", model="gemini-3.8-flash")


# 16. Resume behaviour for same model (skips)
@pytest.mark.asyncio
async def test_batch_resume_skips_matching_model():
    existing = [{
        "concept_id": "circle",
        "status": "PASS",
        "model": "gemini-3.8-flash",
        "checks": {f"c{i}": {"passed": True} for i in range(6)},
        "usage": {"input_tokens": 100, "output_tokens": 100, "metadata_available": True},
        "cost": {"estimated_cost_usd": 0.001},
    }]

    mock_repo = MagicMock()
    mock_repo.all.return_value = existing

    mock_pipeline = MagicMock()
    mock_pipeline.generate = AsyncMock()

    with patch("generate_initial.GEMINI_API_KEY", "test-key"), \
         patch("generate_initial.CONCEPTS", [{"id": "circle", "name": "Circle", "subject": "Maths"}]), \
         patch("generate_initial.ResultsRepository", return_value=mock_repo), \
         patch("generate_initial.GenerationPipeline", return_value=mock_pipeline):

        code = await generate_initial.run(force=False, model="gemini-3.8-flash")
        assert code == 0
        mock_pipeline.generate.assert_not_called()


# 17. Re-generation with another model (does NOT skip)
@pytest.mark.asyncio
async def test_batch_regenerates_when_model_differs():
    # Existing result was generated with gemini-3.5-flash-lite
    existing = [{
        "concept_id": "circle",
        "status": "PASS",
        "model": "gemini-3.5-flash-lite",
        "checks": {f"c{i}": {"passed": True} for i in range(6)},
        "usage": {"input_tokens": 100, "output_tokens": 100, "metadata_available": True},
        "cost": {"estimated_cost_usd": 0.001},
    }]

    mock_repo = MagicMock()
    mock_repo.all.return_value = existing

    fresh_result = {
        "concept_id": "circle",
        "status": "PASS",
        "model": "gemini-3.8-flash",
        "checks": {f"c{i}": {"passed": True} for i in range(6)},
        "usage": {"input_tokens": 120, "output_tokens": 150, "metadata_available": True},
        "cost": {"estimated_cost_usd": 0.002},
        "retries": {"total_retries": 0},
        "latency_ms": 1200,
        "last_error": None,
    }
    mock_pipeline = MagicMock()
    mock_pipeline.generate = AsyncMock(return_value=fresh_result)

    with patch("generate_initial.GEMINI_API_KEY", "test-key"), \
         patch("generate_initial.CONCEPTS", [{"id": "circle", "name": "Circle", "subject": "Maths"}]), \
         patch("generate_initial.ResultsRepository", return_value=mock_repo), \
         patch("generate_initial.GenerationPipeline", return_value=mock_pipeline):

        # Run with gemini-3.8-flash: must NOT skip!
        code = await generate_initial.run(force=False, model="gemini-3.8-flash")
        assert code == 0
        mock_pipeline.generate.assert_called_once_with("circle", model="gemini-3.8-flash")
        mock_repo.upsert.assert_called_once_with(fresh_result)
