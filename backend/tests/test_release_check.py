"""Unit tests for fail-closed release_check.py verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import release_check
from app.core.concepts import CONCEPTS
from app.validators.concept_structure_validator import validate_concept_structure
from app.validators.svg_validator import validate_svg
from conftest import make_valid_svg


def _build_valid_results_payload() -> dict:
    results = []
    for concept in CONCEPTS:
        svg = make_valid_svg(concept)
        report = validate_svg(svg, concept)
        cs_res = validate_concept_structure(report.parsed_root, concept)
        report.checks["concept_structure"] = cs_res

        results.append({
            "concept_id": concept["id"],
            "concept_name": concept["name"],
            "subject": concept["subject"],
            "status": "PASS",
            "model": "gemini-3.5-flash-lite",
            "prompt": "Test prompt",
            "svg": svg,
            "checks": report.as_dict(),
            "retries": {"total_retries": 0, "transient_api_retries": 0, "validation_repairs": 0},
            "usage": {"input_tokens": 500, "output_tokens": 1200, "metadata_available": True},
            "cost": {"estimated_cost_usd": 0.0003},
            "latency_ms": 1500,
            "last_error": None,
        })
    return {"results": results}


def test_release_check_missing_results_file_returns_1(tmp_path):
    missing_file = tmp_path / "nonexistent.json"
    with patch("release_check.RESULTS_PATH", missing_file):
        code = release_check.main()
        assert code == 1


def test_release_check_corrupt_results_file_returns_1(tmp_path):
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{not-valid-json", encoding="utf-8")
    with patch("release_check.RESULTS_PATH", corrupt_file):
        code = release_check.main()
        assert code == 1


def test_release_check_missing_concept_returns_1(tmp_path):
    payload = _build_valid_results_payload()
    payload["results"] = payload["results"][:4]  # Remove 5th concept
    res_file = tmp_path / "results.json"
    res_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch("release_check.RESULTS_PATH", res_file), \
         patch("release_check.GEMINI_API_KEY", "test-key"):
        code = release_check.main()
        assert code == 1


def test_release_check_duplicate_concept_returns_1(tmp_path):
    payload = _build_valid_results_payload()
    payload["results"].append(payload["results"][0])  # Duplicate first concept
    res_file = tmp_path / "results.json"
    res_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch("release_check.RESULTS_PATH", res_file), \
         patch("release_check.GEMINI_API_KEY", "test-key"):
        code = release_check.main()
        assert code == 1


def test_release_check_failed_status_returns_1(tmp_path):
    payload = _build_valid_results_payload()
    payload["results"][0]["status"] = "FAIL"
    res_file = tmp_path / "results.json"
    res_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch("release_check.RESULTS_PATH", res_file), \
         patch("release_check.GEMINI_API_KEY", "test-key"):
        code = release_check.main()
        assert code == 1


def test_release_check_missing_api_key_returns_1(tmp_path):
    payload = _build_valid_results_payload()
    res_file = tmp_path / "results.json"
    res_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch("release_check.RESULTS_PATH", res_file), \
         patch("release_check.GEMINI_API_KEY", ""):
        code = release_check.main()
        assert code == 1


def test_release_check_all_valid_and_configured_returns_0(tmp_path):
    payload = _build_valid_results_payload()
    res_file = tmp_path / "results.json"
    res_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch("release_check.RESULTS_PATH", res_file), \
         patch("release_check.GEMINI_API_KEY", "test-key"):
        code = release_check.main()
        assert code == 0
