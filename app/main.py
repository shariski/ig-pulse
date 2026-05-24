"""FastAPI entrypoint for the IG Pulse dashboard.

Local-first, single process. Runs migrations on startup, configures stdlib
logging to logs/ig_pulse.log with daily rotation (B11), serves the HTMX
dashboard and analysis/export fragments.

Run:  uv run uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from logging.handlers import TimedRotatingFileHandler

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import registry as _registry
from app.auth import _Redirect
from app.config import ensure_session_secret, settings
from app.db import connect, run_migrations
from app.routes import accounts, analysis, auth_routes, dashboard, export


def configure_logging() -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    file_handler = TimedRotatingFileHandler(
        settings.logs_dir / "ig_pulse.log", when="midnight", backupCount=14, encoding="utf-8"
    )
    logging.basicConfig(
        level=settings.log_level,
        format=fmt,
        handlers=[file_handler, logging.StreamHandler()],
    )
    # httpx logs full request URLs at INFO, and our Graph API URLs carry
    # ?access_token=... — mute it to WARNING so the token never reaches logs (B2).
    logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    conn = connect()
    run_migrations(conn)
    conn.close()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    rconn = _registry.connect()
    _registry.run_migrations(rconn)
    rconn.close()
    logging.getLogger("ig_pulse").info("IG Pulse started; db=%s", settings.database_path)
    yield


app = FastAPI(title="IG Pulse", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key=ensure_session_secret())


@app.exception_handler(_Redirect)
async def _redirect_handler(request, exc: _Redirect):
    return RedirectResponse(exc.to, status_code=302)


app.include_router(auth_routes.router)
app.include_router(accounts.router)
app.include_router(dashboard.router)
app.include_router(analysis.router)
app.include_router(export.router)
