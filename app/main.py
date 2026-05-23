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
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import connect, run_migrations
from app.routes import analysis, dashboard, export


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    conn = connect()
    run_migrations(conn)
    conn.close()
    logging.getLogger("ig_pulse").info("IG Pulse started; db=%s", settings.database_path)
    yield


app = FastAPI(title="IG Pulse", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(dashboard.router)
app.include_router(analysis.router)
app.include_router(export.router)
