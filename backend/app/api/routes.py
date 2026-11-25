"""HTTP endpoints used by the browser UI."""

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import config
from app.core.concepts import CONCEPTS, CONCEPT_BY_ID
from app.core.models import (
    ALLOWED_MODEL_IDS,
    DEFAULT_MODEL_ID,
    MODEL_CATALOGUE,
    get_model_info,
    validate_model_id,
)
from app.persistence.results_repository import (
    ModelRunsRepository,
    ResultsRepository,
    ReviewsRepository,
    VersionsRepository,
)
from app.services.gemini_client import GeminiAPIError, MissingAPIKeyError
from app.services.generation_pipeline import GenerationPipeline

router = APIRouter(prefix="/api")
repository = ResultsRepository()
model_runs_repository = ModelRunsRepository()
versions_repository = VersionsRepository()
reviews_repository = ReviewsRepository()
pipeline = GenerationPipeline()

# Ensure initial version records are populated from existing canonical results
versions_repository.seed_initial_versions_from_results(repository.all())


class GenerateRequest(BaseModel):
    model: str | None = Field(
        default=None,
        description="Gemini model ID to use for generation (defaults to server-configured default)",
    )


class ReviewRequest(BaseModel):
    decision: str = Field(..., description="'approved', 'rejected', or 'pending'")
    note: str = Field(default="", description="Reviewer feedback or rejection reason")
    version: int | None = Field(default=None, description="Specific version number reviewed")


class RegenerateRequest(BaseModel):
    feedback: str = Field(default="", description="Rejection feedback or improvement note")
    model: str | None = Field(default=None, description="Gemini model ID")
    from_version: int | None = Field(default=None, description="Source version being revised")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "science-diagram-maker"}


@router.get("/models")
async def get_models() -> dict[str, Any]:
    """Return catalogue of supported Gemini models and default selection."""
    return {
        "models": list(MODEL_CATALOGUE.values()),
        "allowed_ids": sorted(ALLOWED_MODEL_IDS),
        "default_model": config.GEMINI_MODEL,
    }


@router.get("/results")
async def get_results() -> dict:
    """Return the saved snapshot, version history, and human review status; this never calls Gemini."""
    canonical_results = repository.all()
    versions_repository.seed_initial_versions_from_results(canonical_results)
    all_versions = versions_repository.all_by_concept()
    all_reviews = reviews_repository.all()

    enriched_results = []
    for r in canonical_results:
        cid = r.get("concept_id")
        versions = all_versions.get(cid, [])
        review = all_reviews.get(cid, {"concept_id": cid, "decision": "pending", "note": "", "version": 1})
        latest_v = max(versions, key=lambda v: v.get("version", 0)) if versions else None

        enriched = dict(r)
        enriched["version"] = r.get("version", 1)
        enriched["review"] = review
        enriched["versions_count"] = len(versions)
        enriched["versions"] = versions
        enriched["latest_version"] = latest_v
        enriched_results.append(enriched)

    return {
        "concepts": CONCEPTS,
        "results": enriched_results,
        "versions": all_versions,
        "reviews": all_reviews,
        "model_runs": model_runs_repository.all(),
        "model_configured": bool(pipeline.client.api_key),
        "model": pipeline.client.model,
        "models": list(MODEL_CATALOGUE.values()),
        "default_model": config.GEMINI_MODEL,
    }


@router.get("/model-runs")
async def get_model_runs() -> dict[str, Any]:
    """Return all experimental multi-model runs from data/model_runs.json."""
    runs = model_runs_repository.all()
    return {
        "runs": runs,
        "total": len(runs),
    }


@router.get("/diagnostics")
async def get_diagnostics() -> dict:
    """Return operational readiness and saved-result counts without exposing secrets."""
    results = repository.all()
    model_runs = model_runs_repository.all()
    generated = [item for item in results if item.get("status") in {"PASS", "FAIL", "ERROR"}]
    passed_items = [item for item in generated if item.get("status") == "PASS" and bool(item.get("svg"))]
    failed_items = [item for item in generated if item.get("status") in {"FAIL", "ERROR"}]

    checks = [check for item in generated for check in (item.get("checks") or {}).values()]

    # Count retries and repairs across all genuine attempts (do NOT require SVG to exist)
    api_retries_total = sum((item.get("retries") or {}).get("api_retries", 0) for item in generated)
    validation_repairs_total = sum((item.get("retries") or {}).get("validation_retries", 0) for item in generated)

    # Count failed requests' retries and repairs separately
    failed_api_retries = sum((item.get("retries") or {}).get("api_retries", 0) for item in failed_items)
    failed_validation_repairs = sum((item.get("retries") or {}).get("validation_retries", 0) for item in failed_items)

    return {
        "service": "manochitra-science-diagram-maker",
        "status": "ok",
        "default_model": config.GEMINI_MODEL,
        "supported_models": sorted(ALLOWED_MODEL_IDS),
        "api_key_configured": bool(pipeline.client.api_key),
        "api_connection_verified": False,
        "api_connection_note": "A live Generate request is required to verify Gemini connectivity; diagnostics never consumes API quota.",
        "concepts_total": len(CONCEPTS),
        "results_generated": len(generated),
        "diagrams_ready": len(passed_items),
        "results_passed": len(passed_items),
        "results_failed": len(failed_items),
        "checks_passed": sum(1 for check in checks if check.get("passed")),
        "checks_total": len(checks),
        "api_retries_total": api_retries_total,
        "validation_repairs_total": validation_repairs_total,
        "failed_api_retries": failed_api_retries,
        "failed_validation_repairs": failed_validation_repairs,
        "experimental_model_runs_total": len(model_runs),
    }


@router.post("/generate/{concept_id}")
async def generate_one(
    concept_id: str,
    request_data: GenerateRequest | None = None,
    model: str | None = None,
) -> dict:
    if concept_id not in CONCEPT_BY_ID:
        raise HTTPException(status_code=404, detail="Unknown concept. Choose one of the five assignment concepts.")

    raw_model = (request_data.model if request_data and request_data.model else model) or config.GEMINI_MODEL
    try:
        valid_model = validate_model_id(raw_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        try:
            result = await pipeline.generate(concept_id, model=valid_model)
        except TypeError as exc:
            if "unexpected keyword argument 'model'" in str(exc):
                result = await pipeline.generate(concept_id)
            else:
                raise
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiAPIError as exc:
        code = exc.status_code if 400 <= getattr(exc, 'status_code', 0) <= 599 else 503
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Always persist into experimental model_runs.json (keyed by concept_id and model)
    model_runs_repository.upsert(result)

    # Add to version history
    versions_repository.add_version(concept_id, result)

    # Only update canonical results.json if this run targets the canonical assignment model and passed
    if valid_model == config.GEMINI_MODEL:
        if result.get("status") == "PASS" and bool(result.get("svg")):
            repository.upsert(result)
        else:
            prev_canonical = repository.by_concept(concept_id)
            if not prev_canonical or prev_canonical.get("status") != "PASS":
                repository.upsert(result)

    return result


@router.post("/reviews/{concept_id}")
async def save_review(
    concept_id: str,
    request_data: ReviewRequest,
) -> dict:
    """Save human review decision without spending tokens."""
    if concept_id not in CONCEPT_BY_ID:
        raise HTTPException(status_code=404, detail="Unknown concept.")

    decision = request_data.decision.lower().strip()
    if decision not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=400, detail="Decision must be 'approved', 'rejected', or 'pending'.")

    note = request_data.note.strip()
    target_version = request_data.version
    if target_version is None:
        latest = versions_repository.get_latest_version(concept_id)
        target_version = latest.get("version", 1) if latest else 1

    try:
        updated_version = versions_repository.update_review(
            concept_id=concept_id,
            decision=decision,
            note=note,
            version=target_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    review_record = reviews_repository.save(
        concept_id=concept_id,
        decision=decision,
        note=note,
        version=target_version,
    )

    # If explicitly approved and passed validation, promote to canonical result
    if decision == "approved" and updated_version.get("status") == "PASS" and updated_version.get("svg"):
        repository.upsert(updated_version)

    return {
        "status": "ok",
        "concept_id": concept_id,
        "review": review_record,
        "version": updated_version,
    }


@router.post("/regenerate/{concept_id}")
async def regenerate_one(
    concept_id: str,
    request_data: RegenerateRequest | None = None,
) -> dict:
    """Regenerate a concept using human rejection feedback as a prompt input.
    
    Only called upon explicit user action ('REGENERATE WITH FEEDBACK').
    Never overwrites rejected versions.
    """
    if concept_id not in CONCEPT_BY_ID:
        raise HTTPException(status_code=404, detail="Unknown concept. Choose one of the five assignment concepts.")

    feedback = (request_data.feedback if request_data and request_data.feedback else "").strip()
    if not feedback:
        stored_review = reviews_repository.get(concept_id)
        feedback = (stored_review.get("note") or "").strip()

    if not feedback:
        feedback = "Improve animation visibility and visual layout."

    raw_model = (request_data.model if request_data and request_data.model else None) or config.GEMINI_MODEL
    try:
        valid_model = validate_model_id(raw_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from_version_num = request_data.from_version if request_data else None
    if from_version_num is not None:
        prev_version_data = versions_repository.get_version(concept_id, from_version_num)
    else:
        prev_version_data = versions_repository.get_latest_version(concept_id)

    if prev_version_data is None:
        prev_version_data = repository.by_concept(concept_id)

    try:
        new_result = await pipeline.regenerate_with_feedback(
            concept_id=concept_id,
            feedback=feedback,
            previous_version_data=prev_version_data,
            model=valid_model,
        )
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiAPIError as exc:
        code = exc.status_code if 400 <= getattr(exc, 'status_code', 0) <= 599 else 503
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    current_versions = versions_repository.get_versions(concept_id)
    next_version = (max((v.get("version", 0) for v in current_versions), default=0)) + 1
    new_result["version"] = next_version
    new_result["review_status"] = "pending_review"

    # Save to versions repository: NEVER overwrites rejected versions
    versions_repository.add_version(concept_id, new_result)

    # Save to model runs repository
    model_runs_repository.upsert(new_result)

    # Promote to canonical results.json if it passed validation and matches the active model
    if (
        new_result.get("status") == "PASS"
        and len(new_result.get("svg", "")) > 100
        and new_result.get("usage", {}).get("metadata_available") is True
        and valid_model == config.GEMINI_MODEL
    ):
        repository.upsert(new_result)

    # Update reviews repository to indicate new version is pending review
    reviews_repository.save(
        concept_id=concept_id,
        decision="pending",
        note=f"Regenerated from v{prev_version_data.get('version', 1)} feedback: {feedback}",
        version=next_version,
    )

    return {
        "status": "ok",
        "result": new_result,
        "versions": versions_repository.get_versions(concept_id),
        "active_version": next_version,
    }


@router.get("/versions/{concept_id}")
async def get_concept_versions(concept_id: str) -> dict:
    """Return all historical versions for a concept."""
    if concept_id not in CONCEPT_BY_ID:
        raise HTTPException(status_code=404, detail="Unknown concept.")

    versions = versions_repository.get_versions(concept_id)
    current_review = reviews_repository.get(concept_id)
    canonical = repository.by_concept(concept_id)

    return {
        "concept_id": concept_id,
        "versions": versions,
        "total_versions": len(versions),
        "review": current_review,
        "canonical_version": canonical.get("version", 1) if canonical else None,
    }


@router.post("/versions/{concept_id}/approve/{version_num}")
async def approve_specific_version(concept_id: str, version_num: int) -> dict:
    """Promote a specific approved version to canonical results."""
    if concept_id not in CONCEPT_BY_ID:
        raise HTTPException(status_code=404, detail="Unknown concept.")

    target = versions_repository.get_version(concept_id, version_num)
    if not target:
        raise HTTPException(status_code=404, detail=f"Version {version_num} not found for concept '{concept_id}'.")

    if target.get("status") != "PASS" or not target.get("svg"):
        raise HTTPException(status_code=400, detail="Cannot promote a failing or empty SVG to the official result.")

    updated_version = versions_repository.update_review(
        concept_id=concept_id,
        decision="approved",
        note="Approved by reviewer.",
        version=version_num,
    )
    reviews_repository.save(
        concept_id=concept_id,
        decision="approved",
        note="Approved by reviewer.",
        version=version_num,
    )
    repository.upsert(updated_version)

    return {
        "status": "ok",
        "concept_id": concept_id,
        "approved_version": version_num,
        "canonical_result": updated_version,
    }

