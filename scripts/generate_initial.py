"""Generate the five required assignment diagrams and update data/results.json.

Run from the repository root:
    python scripts/generate_initial.py

Add --force to regenerate concepts that already have a saved result.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.concepts import CONCEPTS
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.core.models import ALLOWED_MODEL_IDS, MODEL_CATALOGUE, validate_model_id
from app.persistence.results_repository import ResultsRepository
from app.services.gemini_client import MissingAPIKeyError
from app.services.generation_pipeline import GenerationPipeline


async def run(force: bool, model: str | None = None) -> int:
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is missing. Copy .env.example to .env and add your key.")
        return 2

    selected_model = validate_model_id(model or GEMINI_MODEL)
    model_info = MODEL_CATALOGUE[selected_model]
    print(f"MANOCHITRA BATCH GENERATOR")
    print(f"Target Model: {model_info['name']} ({selected_model}) · {model_info['role']}")

    repository = ResultsRepository()
    pipeline = GenerationPipeline()
    existing = {item.get("concept_id"): item for item in repository.all()}
    overall_success = True

    try:
        for concept in CONCEPTS:
            previous = existing.get(concept["id"], {})
            previous_model = previous.get("model")
            previous_usage = previous.get("usage", {})
            previous_cost = previous.get("cost", {})
            previous_checks = previous.get("checks", {})
            all_six_passed = (
                isinstance(previous_checks, dict)
                and len(previous_checks) >= 6
                and all(c.get("passed") is True for c in previous_checks.values())
            )
            previous_is_complete = (
                previous.get("status") == "PASS"
                and previous_model == selected_model
                and all_six_passed
                and previous_usage.get("metadata_available") is True
                and isinstance(previous_usage.get("input_tokens"), int)
                and isinstance(previous_usage.get("output_tokens"), int)
                and isinstance(previous_cost.get("estimated_cost_usd"), (int, float))
            )
            if not force and previous_is_complete:
                print(f"SKIP  {concept['name']} [{selected_model}]: an existing PASS result with 6/6 checks is already saved.")
                continue

            print(f"\nGENERATING  {concept['name']} ({concept['subject']}) using {selected_model} ...")
            try:
                result = await pipeline.generate(concept["id"], model=selected_model)
            except MissingAPIKeyError as exc:
                print(f"ERROR: {exc}")
                return 2

            repository.upsert(result)
            overall_success = overall_success and result["status"] == "PASS"
            estimated_cost = result["cost"].get("estimated_cost_usd")
            cost_text = f"${estimated_cost:.8f}" if isinstance(estimated_cost, (int, float)) else "NOT AVAILABLE"
            checks_passed = sum(1 for c in result["checks"].values() if c.get("passed") is True)
            total_checks = len(result["checks"])
            print(
                f"{result['status']:<6} {concept['name']} | "
                f"model={result.get('model', selected_model)} | "
                f"checks={checks_passed}/{total_checks} | "
                f"tokens={result['usage']['input_tokens']} in / {result['usage']['output_tokens']} out | "
                f"retries={result['retries']['total_retries']} | "
                f"cost={cost_text} | latency={result['latency_ms']}ms"
            )
            if result.get("last_error"):
                print(f"       {result['last_error']}")

    except KeyboardInterrupt:
        print("\n\nINTERRUPTED: Batch run stopped by user. Already generated concepts remain saved in results.json.")
        return 130

    # Keep the README result table consistent with the real JSON measurements.
    try:
        from update_readme_results import main as update_readme
        update_readme()
    except Exception as exc:
        print(f"Warning: could not update README results: {exc}")

    print(f"\nSaved results: {ROOT / 'data' / 'results.json'}")
    final = repository.all()
    pass_count = sum(1 for item in final if item.get("status") == "PASS")
    print(f"Current saved PASS results: {pass_count}/{len(CONCEPTS)}")
    return 0 if overall_success and pass_count == len(CONCEPTS) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the five initial Udhi science diagrams.")
    parser.add_argument("--force", action="store_true", help="Regenerate all concepts, including existing PASS results.")
    parser.add_argument(
        "--model",
        choices=sorted(ALLOWED_MODEL_IDS),
        default=GEMINI_MODEL,
        help=f"Gemini model to use (default: {GEMINI_MODEL}; choices: {', '.join(sorted(ALLOWED_MODEL_IDS))}).",
    )
    args = parser.parse_args()
    return asyncio.run(run(force=args.force, model=args.model))


if __name__ == "__main__":
    raise SystemExit(main())
