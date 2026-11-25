import json
import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_home_embeds_initial_snapshot_in_html_without_a_startup_fetch():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "__BOOTSTRAP_JSON__" not in html
    match = re.search(r'<script id="initial-data" type="application/json">(.*?)</script>', html, re.DOTALL)
    assert match
    payload = json.loads(match.group(1))
    assert len(payload["concepts"]) == 5
    assert "results" in payload
    assert "fetchDashboard" not in html


def test_health_route():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_static_frontend_assets_are_served():
    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert "--lime" in response.text


def test_diagnostics_does_not_expose_api_secret():
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["api_connection_verified"] is False
    assert "api_key" not in payload
    assert payload["concepts_total"] == 5


def test_results_route_returns_five_concepts_without_generation():
    response = client.get("/api/results")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["concepts"]) == 5
    assert isinstance(payload["results"], list)


def test_generate_unknown_concept_returns_404():
    response = client.post('/api/generate/not-a-concept')
    assert response.status_code == 404


def test_generate_missing_api_key_returns_clear_503(monkeypatch):
    from app.api import routes
    from app.services.gemini_client import MissingAPIKeyError

    async def fail(_concept_id):
        raise MissingAPIKeyError('GEMINI_API_KEY is not configured.')

    monkeypatch.setattr(routes.pipeline, 'generate', fail)
    response = client.post('/api/generate/circle')
    assert response.status_code == 503
    assert 'GEMINI_API_KEY' in response.json()['detail']


def test_generate_value_error_returns_400(monkeypatch):
    from app.api import routes

    async def fail(_concept_id):
        raise ValueError('Invalid generation settings.')

    monkeypatch.setattr(routes.pipeline, 'generate', fail)
    response = client.post('/api/generate/circle')
    assert response.status_code == 400
    assert response.json()['detail'] == 'Invalid generation settings.'


def test_generate_success_saves_and_returns_result(monkeypatch):
    from app.api import routes

    result = {'concept_id': 'circle', 'status': 'PASS', 'svg': '<svg />'}
    saved = []

    async def succeed(_concept_id):
        return result

    monkeypatch.setattr(routes.pipeline, 'generate', succeed)
    monkeypatch.setattr(routes.repository, 'upsert', saved.append)
    monkeypatch.setattr(routes.model_runs_repository, 'upsert', lambda *a, **k: None)
    response = client.post('/api/generate/circle')
    assert response.status_code == 200
    assert response.json() == result
    assert saved == [result]


def test_security_headers_are_present():
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_model_runs_endpoint():
    response = client.get("/api/model-runs")
    assert response.status_code == 200
    payload = response.json()
    assert "runs" in payload
    assert isinstance(payload["runs"], list)
    assert payload["total"] == len(payload["runs"])


def test_diagnostics_includes_separated_telemetry():
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert "diagrams_ready" in payload
    assert "results_passed" in payload
    assert "results_failed" in payload
    assert "api_retries_total" in payload
    assert "validation_repairs_total" in payload
    assert "failed_api_retries" in payload
    assert "failed_validation_repairs" in payload
    assert "experimental_model_runs_total" in payload


def test_generate_experimental_model_saves_to_model_runs_only(monkeypatch):
    from app.api import routes

    result = {
        'concept_id': 'circle',
        'status': 'PASS',
        'model': 'gemini-3.8-flash',
        'svg': '<svg />',
    }
    canonical_saved = []
    runs_saved = []

    async def succeed(_concept_id, model=None):
        return result

    monkeypatch.setattr(routes.pipeline, 'generate', succeed)
    monkeypatch.setattr(routes.repository, 'upsert', canonical_saved.append)
    monkeypatch.setattr(routes.model_runs_repository, 'upsert', runs_saved.append)

    response = client.post('/api/generate/circle', json={'model': 'gemini-3.8-flash'})
    assert response.status_code == 200
    assert response.json() == result
    # Experimental run must be recorded in model_runs.json
    assert runs_saved == [result]
    # Canonical results.json must NOT be touched by experimental model run
    assert canonical_saved == []

