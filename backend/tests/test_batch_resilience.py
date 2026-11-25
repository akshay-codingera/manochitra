"""Unit tests for batch generation resilience, skipping, and interrupt recovery."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_initial


@pytest.fixture
def mock_concepts():
    return [
        {"id": "pythagoras", "name": "Pythagoras' Theorem", "subject": "Maths"},
        {"id": "circle", "name": "Circle Geometry", "subject": "Maths"},
    ]


@pytest.fixture
def make_mock_result():
    def _builder(concept_id: str, passed_checks: int = 6, status: str = "PASS"):
        checks = {
            "valid_svg": {"name": "Valid SVG", "passed": True, "detail": "ok"},
            "within_viewbox": {"name": "Within ViewBox", "passed": True, "detail": "ok"},
            "title_and_labels": {"name": "Title and Labels", "passed": True, "detail": "ok"},
            "has_animation": {"name": "Has Animation", "passed": True, "detail": "ok"},
            "scientific_terms": {"name": "Scientific Terms", "passed": True, "detail": "ok"},
        }
        if passed_checks >= 6:
            checks["concept_structure"] = {"name": "Concept Structure", "passed": True, "detail": "ok"}

        return {
            "concept_id": concept_id,
            "concept_name": f"Concept {concept_id}",
            "status": status,
            "model": "gemini-3.5-flash-lite",
            "checks": checks,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 200,
                "metadata_available": True,
            },
            "cost": {
                "estimated_cost_usd": 0.0001,
            },
            "retries": {"total_retries": 0},
            "latency_ms": 1200,
            "last_error": None,
        }
    return _builder


@pytest.mark.asyncio
async def test_batch_run_missing_api_key_returns_code_2():
    with patch("generate_initial.GEMINI_API_KEY", ""):
        code = await generate_initial.run(force=False)
        assert code == 2


@pytest.mark.asyncio
async def test_batch_run_skips_complete_pass(mock_concepts, make_mock_result):
    existing_items = [
        make_mock_result("pythagoras", passed_checks=6, status="PASS"),
        make_mock_result("circle", passed_checks=6, status="PASS"),
    ]

    mock_repo = MagicMock()
    mock_repo.all.return_value = existing_items

    mock_pipeline = MagicMock()
    mock_pipeline.generate = AsyncMock()

    with patch("generate_initial.GEMINI_API_KEY", "test-key"), \
         patch("generate_initial.CONCEPTS", mock_concepts), \
         patch("generate_initial.ResultsRepository", return_value=mock_repo), \
         patch("generate_initial.GenerationPipeline", return_value=mock_pipeline):

        code = await generate_initial.run(force=False)

        assert code == 0
        mock_pipeline.generate.assert_not_called()
        mock_repo.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_batch_run_regenerates_when_incomplete(mock_concepts, make_mock_result):
    # 'pythagoras' has only 5 checks (missing concept_structure)
    existing_items = [
        make_mock_result("pythagoras", passed_checks=5, status="PASS"),
        make_mock_result("circle", passed_checks=6, status="PASS"),
    ]

    mock_repo = MagicMock()
    fresh_pyth = make_mock_result("pythagoras", passed_checks=6, status="PASS")
    mock_repo.all.side_effect = [existing_items, [fresh_pyth, existing_items[1]]]

    mock_pipeline = MagicMock()
    mock_pipeline.generate = AsyncMock(return_value=fresh_pyth)

    with patch("generate_initial.GEMINI_API_KEY", "test-key"), \
         patch("generate_initial.CONCEPTS", mock_concepts), \
         patch("generate_initial.ResultsRepository", return_value=mock_repo), \
         patch("generate_initial.GenerationPipeline", return_value=mock_pipeline):

        code = await generate_initial.run(force=False)

        assert code == 0
        mock_pipeline.generate.assert_called_once_with("pythagoras", model="gemini-3.5-flash-lite")
        mock_repo.upsert.assert_called_once_with(fresh_pyth)


@pytest.mark.asyncio
async def test_batch_run_force_flag_regenerates_all(mock_concepts, make_mock_result):
    existing_items = [
        make_mock_result("pythagoras", passed_checks=6, status="PASS"),
        make_mock_result("circle", passed_checks=6, status="PASS"),
    ]

    mock_repo = MagicMock()
    mock_repo.all.return_value = existing_items

    mock_pipeline = MagicMock()
    res1 = make_mock_result("pythagoras", passed_checks=6, status="PASS")
    res2 = make_mock_result("circle", passed_checks=6, status="PASS")
    mock_pipeline.generate = AsyncMock(side_effect=[res1, res2])

    with patch("generate_initial.GEMINI_API_KEY", "test-key"), \
         patch("generate_initial.CONCEPTS", mock_concepts), \
         patch("generate_initial.ResultsRepository", return_value=mock_repo), \
         patch("generate_initial.GenerationPipeline", return_value=mock_pipeline):

        code = await generate_initial.run(force=True)

        assert code == 0
        assert mock_pipeline.generate.call_count == 2
        assert mock_repo.upsert.call_count == 2


@pytest.mark.asyncio
async def test_batch_run_keyboard_interrupt_returns_130(mock_concepts, make_mock_result):
    mock_repo = MagicMock()
    mock_repo.all.return_value = []

    mock_pipeline = MagicMock()
    mock_pipeline.generate = AsyncMock(side_effect=KeyboardInterrupt())

    with patch("generate_initial.GEMINI_API_KEY", "test-key"), \
         patch("generate_initial.CONCEPTS", mock_concepts), \
         patch("generate_initial.ResultsRepository", return_value=mock_repo), \
         patch("generate_initial.GenerationPipeline", return_value=mock_pipeline):

        code = await generate_initial.run(force=False)
        assert code == 130
