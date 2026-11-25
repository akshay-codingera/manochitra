"""Central model catalogue and effective-dated pricing for Google Gemini models.

Supports exactly two models:
1. Gemini 3.5 Flash-Lite (gemini-3.5-flash-lite) — Efficiency
2. Gemini 3.8 Flash (gemini-3.8-flash) — Advanced

Note: gemini-3.5-flash is deprecated and automatically routed by Google
to gemini-3.6/3.8-flash. It is not listed as a separate selectable model.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

DEFAULT_MODEL_ID = "gemini-3.5-flash-lite"
PRICING_VERSION = "2026-11-25-v1"
PRICING_SOURCE = "Google AI Studio pricing schedule (checked Nov 2026)"

MODEL_CATALOGUE: dict[str, dict[str, Any]] = {
    "gemini-3.5-flash-lite": {
        "id": "gemini-3.5-flash-lite",
        "name": "Gemini 3.5 Flash-Lite",
        "short_name": "3.5 Flash-Lite",
        "role": "Efficient, cost-conscious generation.",
        "tagline": "Ultra-Low Latency & High Throughput",
        "position": "left",
        "gauge_angle_deg": -45,
        "free_tier_listed": True,
        "account_access_status": "UNVERIFIED",
        "pricing_effective_date": "2026-11-25",
        "pricing_source": PRICING_SOURCE,
        "input_price_per_million": 0.30,
        "output_price_per_million": 2.50,
        "pricing_schedule": [
            {
                "effective_from": "2026-01-01",
                "effective_to": None,
                "input_usd_per_million": 0.30,
                "output_usd_per_million": 2.50,
            }
        ],
        "is_default": True,
    },
    "gemini-3.8-flash": {
        "id": "gemini-3.8-flash",
        "name": "Gemini 3.8 Flash",
        "short_name": "3.8 Flash",
        "role": "Higher-capability generation.",
        "tagline": "Advanced Multimodal & Complex Reasoning",
        "position": "right",
        "gauge_angle_deg": 45,
        "free_tier_listed": True,
        "account_access_status": "UNVERIFIED",
        "pricing_effective_date": "2026-11-25",
        "pricing_source": PRICING_SOURCE,
        "input_price_per_million": 0.75,
        "output_price_per_million": 3.75,
        "pricing_schedule": [
            {
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
                "input_usd_per_million": 0.75,
                "output_usd_per_million": 3.75,
            },
            {
                "effective_from": "2027-01-01",
                "effective_to": None,
                "input_usd_per_million": 1.50,
                "output_usd_per_million": 7.50,
            },
        ],
        "is_default": False,
    },
}

ALLOWED_MODEL_IDS: frozenset[str] = frozenset(MODEL_CATALOGUE.keys())


def validate_model_id(model_id: str | None) -> str:
    """Validate and resolve model ID, falling back to default if None.

    Raises ValueError for unsupported models or deprecated aliases.
    """
    if model_id is None or (isinstance(model_id, str) and not model_id.strip()):
        return DEFAULT_MODEL_ID

    clean_id = model_id.strip()
    if clean_id not in ALLOWED_MODEL_IDS:
        allowed_list = ", ".join(sorted(ALLOWED_MODEL_IDS))
        if clean_id == "gemini-3.5-flash":
            raise ValueError(
                f"Model 'gemini-3.5-flash' is a deprecated alias. Use 'gemini-3.8-flash' instead. Allowed models: {allowed_list}."
            )
        raise ValueError(
            f"Unsupported model '{clean_id}'. Allowed models: {allowed_list}."
        )
    return clean_id


def get_model_info(model_id: str) -> dict[str, Any]:
    """Retrieve metadata copy for a validated model ID."""
    valid_id = validate_model_id(model_id)
    return dict(MODEL_CATALOGUE[valid_id])


def get_rates_for_date(model_id: str, as_of_date: date | None = None) -> tuple[float, float]:
    """Determine effective input and output USD rates per million tokens for a given date."""
    valid_id = validate_model_id(model_id)
    target_date = as_of_date or datetime.now(timezone.utc).date()
    model_data = MODEL_CATALOGUE[valid_id]
    schedule = model_data.get("pricing_schedule", [])

    for entry in schedule:
        eff_from = datetime.strptime(entry["effective_from"], "%Y-%m-%d").date()
        eff_to = datetime.strptime(entry["effective_to"], "%Y-%m-%d").date() if entry.get("effective_to") else None
        if eff_from <= target_date:
            if eff_to is None or target_date <= eff_to:
                return float(entry["input_usd_per_million"]), float(entry["output_usd_per_million"])

    return float(model_data["input_price_per_million"]), float(model_data["output_price_per_million"])


def calculate_token_cost(
    input_tokens: int,
    output_tokens: int,
    model_id: str,
    billing_tier: str = "free",
    usage_metadata_available: bool = True,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Calculate estimated API charge and paid-tier equivalent cost for given token usage."""
    valid_id = validate_model_id(model_id)

    if not usage_metadata_available:
        return {
            "estimated_cost_usd": None,
            "paid_equivalent_cost_usd": None,
            "billing_tier": billing_tier,
            "pricing_version": PRICING_VERSION,
            "pricing_effective_date": MODEL_CATALOGUE[valid_id]["pricing_effective_date"],
            "usage_metadata_available": False,
            "pricing_assumption": "Unavailable: Gemini response omitted required token usage metadata.",
        }

    input_rate, output_rate = get_rates_for_date(valid_id, as_of_date)
    input_cost = (input_tokens * input_rate) / 1_000_000
    output_cost = (output_tokens * output_rate) / 1_000_000
    paid_equivalent = input_cost + output_cost

    # The assignment calls for free-tier usage.
    estimated = 0.0 if billing_tier.lower() == "free" else paid_equivalent

    return {
        "estimated_cost_usd": round(estimated, 8),
        "paid_equivalent_cost_usd": round(paid_equivalent, 8),
        "billing_tier": billing_tier,
        "pricing_version": PRICING_VERSION,
        "pricing_effective_date": MODEL_CATALOGUE[valid_id]["pricing_effective_date"],
        "usage_metadata_available": True,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_rate_per_million": input_rate,
        "output_rate_per_million": output_rate,
        "pricing_assumption": (
            f"{MODEL_CATALOGUE[valid_id]['name']} standard reference rates "
            f"(${input_rate:.2f} in / ${output_rate:.2f} out per 1M tokens; source: {PRICING_SOURCE})"
        ),
    }
