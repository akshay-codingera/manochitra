"""Regression tests for rejection-driven SVG improvement and versioning workflow."""

import pytest
from fastapi.testclient import TestClient

from app.core.concepts import CONCEPT_BY_ID
from app.main import app
from app.persistence.results_repository import (
    ModelRunsRepository,
    ResultsRepository,
    ReviewsRepository,
    VersionsRepository,
)
from app.services.prompt_builder import (
    MANDATORY_ANIMATION_REQUIREMENTS,
    build_feedback_regeneration_prompt,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_workflow_repositories(tmp_path, monkeypatch):
    """Provide isolated repositories for workflow tests under tmp_path/isolated."""
    app_data = tmp_path / "isolated"
    app_data.mkdir(parents=True, exist_ok=True)
    from app.api import routes

    tmp_results = ResultsRepository(app_data / "results.json")
    tmp_versions = VersionsRepository(app_data / "versions.json")
    tmp_reviews = ReviewsRepository(app_data / "reviews.json")
    tmp_runs = ModelRunsRepository(app_data / "model_runs.json")

    from conftest import make_valid_svg
    for cid in ["pythagoras", "circle", "series-circuit", "photosynthesis", "states-of-matter"]:
        concept = CONCEPT_BY_ID[cid]
        tmp_results.upsert({
            "concept_id": cid,
            "status": "PASS",
            "model": "gemini-3.5-flash-lite",
            "svg": make_valid_svg(concept),
            "version": 1,
        })
    tmp_versions.seed_initial_versions_from_results(tmp_results.all())

    monkeypatch.setattr(routes, "repository", tmp_results)
    monkeypatch.setattr(routes, "versions_repository", tmp_versions)
    monkeypatch.setattr(routes, "reviews_repository", tmp_reviews)
    monkeypatch.setattr(routes, "model_runs_repository", tmp_runs)


def test_versions_repository_preserves_versions_and_increments_number(tmp_path):
    repo = VersionsRepository(tmp_path / "versions.json")
    assert repo.get_versions("pythagoras") == []

    v1_data = {
        "concept_id": "pythagoras",
        "version": 1,
        "svg": "<svg id='v1'/>",
        "status": "PASS",
        "review_status": "approved",
    }
    repo.add_version("pythagoras", v1_data)
    assert len(repo.get_versions("pythagoras")) == 1
    assert repo.get_version("pythagoras", 1)["svg"] == "<svg id='v1'/>"

    v2_data = {
        "concept_id": "pythagoras",
        "version": 2,
        "svg": "<svg id='v2'/>",
        "status": "PASS",
        "review_status": "pending_review",
        "rejection_reason": "Visible hypotenuse pulse required",
    }
    repo.add_version("pythagoras", v2_data)

    versions = repo.get_versions("pythagoras")
    assert len(versions) == 2
    # Ensure v1 is not overwritten
    assert repo.get_version("pythagoras", 1)["svg"] == "<svg id='v1'/>"
    assert repo.get_version("pythagoras", 2)["svg"] == "<svg id='v2'/>"
    assert repo.get_latest_version("pythagoras")["version"] == 2


def test_review_rejection_does_not_call_gemini_or_spend_tokens(monkeypatch):
    """Rejecting a diagram must simply record the decision/feedback without generating."""
    from app.api import routes

    called = False

    async def fake_generate(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(routes.pipeline, "generate", fake_generate)
    monkeypatch.setattr(routes.pipeline, "regenerate_with_feedback", fake_generate)

    response = client.post(
        "/api/reviews/pythagoras",
        json={"decision": "rejected", "note": "Animation needs to be more visible", "version": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["review"]["decision"] == "rejected"
    assert payload["review"]["note"] == "Animation needs to be more visible"
    assert not called, "Gemini was called when only a rejection decision was submitted!"


def test_build_feedback_regeneration_prompt_contains_all_mandated_sections():
    concept = CONCEPT_BY_ID["pythagoras"]
    prev_svg = "<svg><polygon points='360,220 360,420 600,420' /></svg>"
    user_feedback = "The hypotenuse pulse animation is too subtle; make it prominent."

    prompt = build_feedback_regeneration_prompt(
        concept=concept,
        previous_svg=prev_svg,
        user_feedback=user_feedback,
        failure_reasons=["within_viewbox: Label clipped"],
        visual_quality_issues=["Ensure 28px margin from border"],
    )

    # 1. Original concept requirements
    assert "Pythagoras' theorem" in prompt
    assert "hypotenuse" in prompt.lower()
    assert "360,220 360,420 600,420" in prompt

    # 2. Previous SVG
    assert prev_svg in prompt

    # 3. User feedback note
    assert user_feedback in prompt

    # 4. Mandatory animation requirements
    assert "MANDATORY ANIMATION REQUIREMENT FOR PYTHAGORAS" in prompt
    assert "Visible side tracing or prominent hypotenuse pulse highlight" in prompt

    # 5. Explicit instructions
    assert "CORRECT THE DEFECTS" in prompt
    assert "PRESERVE ACCURATE GEOMETRY" in prompt
    assert "DO NOT DUPLICATE" in prompt
    assert "SATISFY ALL SIX MANDATORY QUALITY GATES" in prompt


def test_regenerate_endpoint_propagates_model_and_creates_version_2(monkeypatch):
    from app.api import routes

    fake_v2 = {
        "concept_id": "pythagoras",
        "concept": "Pythagoras' theorem",
        "subject": "Maths",
        "source_text": "In a right-angled triangle...",
        "svg": "<svg id='pythagoras_v2' />",
        "model": "gemini-3.5-flash-lite",
        "status": "PASS",
        "checks": {
            "valid_svg": {"passed": True},
            "within_viewbox": {"passed": True},
            "title_and_labels": {"passed": True},
            "has_animation": {"passed": True},
            "scientific_terms": {"passed": True},
            "concept_structure": {"passed": True},
        },
        "retries": {"api_retries": 0, "validation_retries": 0, "total_retries": 0},
        "latency_ms": 3200.0,
    }

    async def fake_regen(concept_id, feedback, previous_version_data, model):
        assert concept_id == "pythagoras"
        assert "prominent" in feedback
        assert model == "gemini-3.5-flash-lite"
        return dict(fake_v2)

    monkeypatch.setattr(routes.pipeline, "regenerate_with_feedback", fake_regen)

    response = client.post(
        "/api/regenerate/pythagoras",
        json={"feedback": "Make hypotenuse pulse prominent", "model": "gemini-3.5-flash-lite", "from_version": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["result"]["version"] >= 2
    assert data["result"]["svg"] == "<svg id='pythagoras_v2' />"


def test_failed_regeneration_preserves_previous_data(monkeypatch):
    from app.api import routes
    from app.services.gemini_client import GeminiAPIError

    initial_versions = len(routes.versions_repository.get_versions("pythagoras"))

    async def fake_fail(*args, **kwargs):
        raise GeminiAPIError(503, "Upstream timeout")

    monkeypatch.setattr(routes.pipeline, "regenerate_with_feedback", fake_fail)

    response = client.post(
        "/api/regenerate/pythagoras",
        json={"feedback": "Try again", "model": "gemini-3.5-flash-lite"},
    )
    assert response.status_code == 503
    # Previous versions count unchanged
    assert len(routes.versions_repository.get_versions("pythagoras")) == initial_versions


def test_approve_specific_version_promotes_to_canonical():
    # Fetch current versions of circle
    resp = client.get("/api/versions/circle")
    assert resp.status_code == 200
    versions = resp.json()["versions"]
    assert len(versions) >= 1

    # Approve version 1
    approve_resp = client.post("/api/versions/circle/approve/1")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["approved_version"] == 1

    # Check /api/results reflects approved version
    results_resp = client.get("/api/results")
    assert results_resp.status_code == 200
    circle_result = next(r for r in results_resp.json()["results"] if r["concept_id"] == "circle")
    assert circle_result["status"] == "PASS"


def test_persistence_of_reviews_in_api_results():
    # Save a review note on series-circuit
    client.post(
        "/api/reviews/series-circuit",
        json={"decision": "approved", "note": "Verified continuous loop", "version": 1},
    )

    # Query /api/results
    resp = client.get("/api/results")
    assert resp.status_code == 200
    payload = resp.json()
    assert "reviews" in payload
    assert payload["reviews"]["series-circuit"]["decision"] == "approved"
    assert payload["reviews"]["series-circuit"]["note"] == "Verified continuous loop"
