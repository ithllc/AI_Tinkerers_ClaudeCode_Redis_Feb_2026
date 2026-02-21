"""
VoxVisual — FastAPI backend.

Endpoints:
    POST /api/generate-ui   — voice/text query → SVG visualization
    GET  /api/health         — health check
    GET  /                   — serves the frontend
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root before any other imports that need env vars
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.claude_integration import generate_visualization

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="VoxVisual", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def serve_frontend():
    """Serve the single-page frontend."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/generate-ui")
async def generate_ui(request: Request):
    """Accept a text query and return an SVG visualization."""
    body = await request.json()
    query = body.get("query", "").strip()
    session_id = body.get("session_id", "default-session")
    user_id = body.get("user_id", "default")

    if not query:
        return JSONResponse(
            {"error": "No query provided"}, status_code=400
        )

    try:
        result = await generate_visualization(
            user_query=query,
            session_id=session_id,
            user_id=user_id,
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse(
            {"error": str(e), "explanation": f"Error: {e}", "svg_code": "", "css_styles": ""},
            status_code=500,
        )


# Mount static files (CSS, JS, images if any)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
