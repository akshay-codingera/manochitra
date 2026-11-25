"""FastAPI application, initial HTML bootstrap and static asset hosting."""

import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import model_runs_repository, pipeline, repository, router
from app.core.concepts import CONCEPTS
from app.core.config import APP_NAME, FRONTEND_PATH

app = FastAPI(
    title=APP_NAME,
    description="Generate, validate and review animated science SVG diagrams.",
    version="1.0.0",
)
app.include_router(router)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add conservative response headers without breaking the SVG preview iframe."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path == "/" or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _safe_json_for_script(payload: dict) -> str:
    """Escape HTML-significant characters before embedding JSON in a script node."""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


from app.core.models import MODEL_CATALOGUE


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> HTMLResponse:
    # The saved results and model catalogue are embedded into the initial HTML response.
    # The browser makes no fetch/XHR or Gemini inference request when the page first opens.
    payload = {
        "concepts": CONCEPTS,
        "results": repository.all(),
        "model_runs": model_runs_repository.all(),
        "model_configured": bool(pipeline.client.api_key),
        "model": pipeline.client.model,
        "models": list(MODEL_CATALOGUE.values()),
        "default_model": pipeline.client.model,
    }
    template = (FRONTEND_PATH / "index.html").read_text(encoding="utf-8")
    html = template.replace("__BOOTSTRAP_JSON__", _safe_json_for_script(payload))
    return HTMLResponse(content=html)


# Serve the CSS, JavaScript modules and static design reference from one origin.
app.mount("/static", StaticFiles(directory=str(FRONTEND_PATH)), name="static")
