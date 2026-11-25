"""Central application configuration.

Keeping settings in one module makes model, timeout and cost assumptions easy
 to inspect and change during the live interview exercise.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

from app.core.models import (
    ALLOWED_MODEL_IDS,
    DEFAULT_MODEL_ID,
    MODEL_CATALOGUE,
    calculate_token_cost,
    get_model_info,
    validate_model_id,
)

APP_NAME = "MANOCHITRA — Science Diagram Review"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Default model resolution: validate against allowlist; fallback to DEFAULT_MODEL_ID if invalid
_env_model = os.getenv("GEMINI_MODEL", "").strip()
GEMINI_MODEL = _env_model if _env_model in ALLOWED_MODEL_IDS else DEFAULT_MODEL_ID

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "90"))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192"))
GEMINI_BILLING_TIER = os.getenv("GEMINI_BILLING_TIER", "free").strip().lower()

RETRY_BASE_SECONDS = float(os.getenv("RETRY_BASE_SECONDS", "1"))
RETRY_MAX_SECONDS = float(os.getenv("RETRY_MAX_SECONDS", "30"))
MAX_TRANSIENT_RETRIES = 3
MAX_VALIDATION_RETRIES = 1

# Backward-compatibility reference rates for the default model
INPUT_USD_PER_MILLION_TOKENS = MODEL_CATALOGUE[DEFAULT_MODEL_ID]["input_price_per_million"]
OUTPUT_USD_PER_MILLION_TOKENS = MODEL_CATALOGUE[DEFAULT_MODEL_ID]["output_price_per_million"]

RESULTS_PATH = PROJECT_ROOT / "data" / "results.json"
MODEL_RUNS_PATH = PROJECT_ROOT / "data" / "model_runs.json"
VERSIONS_PATH = PROJECT_ROOT / "data" / "versions.json"
REVIEWS_PATH = PROJECT_ROOT / "data" / "reviews.json"
FRONTEND_PATH = PROJECT_ROOT / "frontend"
