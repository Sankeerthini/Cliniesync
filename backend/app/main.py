"""ClinieSync API - FastAPI application (application layer: APIs, business logic, query orchestration).

Run:  uvicorn backend.app.main:app --reload --port 8000      (from the project root)
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai.llm.client import get_llm
from backend.app.api import analytics, auth, data, followups, kpi, patients, query, reports, reviews, system, trust
from backend.app.security import seed_users
from common.settings import PROJECT_ROOT, get_settings
from database.models import Base
from database.session import create_views, get_engine, session_scope
from guardrails.nemo_adapter import get_nemo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(get_engine())          # app tables (clinical tables come from the ETL)
    try:
        create_views()
    except Exception as exc:  # pragma: no cover - before the first ETL run
        logging.warning("Analytics views not created yet (run the ETL first): %s", exc)
    with session_scope() as s:
        seed_users(s)
    get_nemo().load(get_llm().available())
    yield


app = FastAPI(title="ClinieSync API", version="1.0.0", lifespan=lifespan,
              description="Maternal & Child Healthcare Operations Copilot - assistive, not diagnostic.")
app.add_middleware(CORSMiddleware, allow_origins=list(get_settings().cors_origins), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)   # the UI bundle is ~800 KB raw, ~250 KB compressed

for r in (auth, system, query, patients, followups, analytics, reviews, reports, kpi, trust, data):
    app.include_router(r.router)
app.include_router(reports.public)                  # /r/<token> shared-report links (before the SPA catch-all)

# Serve the built React app (frontend/dist) from the same origin when available.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = FRONTEND_DIST / path
        if path and f.is_file() and Path(f).resolve().is_relative_to(FRONTEND_DIST.resolve()):
            return FileResponse(f)
        return FileResponse(FRONTEND_DIST / "index.html")
