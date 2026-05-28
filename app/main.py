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
    log = logging.getLogger("ig_pulse")
    conn = connect()
    run_migrations(conn)
    conn.close()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    rconn = _registry.connect()
    _registry.run_migrations(rconn)
    # Apply data-DB migrations to every existing per-account database so
    # schema changes (e.g. 002_user_stopwords.sql) reach accounts that
    # haven't fetched/analyzed since the deploy. Failures are logged but
    # don't crash startup — individual route handlers degrade gracefully.
    account_paths = [r[0] for r in rconn.execute("SELECT db_path FROM ig_accounts").fetchall()]
    rconn.close()
    for db_path in account_paths:
        try:
            aconn = connect(db_path)
            try:
                run_migrations(aconn)
            finally:
                aconn.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("account migration failed for %s: %s", db_path, exc)
    log.info(
        "IG Pulse started; db=%s accounts_migrated=%d",
        settings.database_path, len(account_paths),
    )
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
