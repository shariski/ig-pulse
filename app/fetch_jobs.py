"""Background fetch+analyze jobs, guarded so only one runs per account DB.

Adding an account kicks off a first fetch, and the dashboard's Refresh button
starts another — both run fetch_all + analyze_comments against the same SQLite
file. SQLite (even in WAL) allows only one writer; two concurrent jobs make the
loser exceed busy_timeout and raise "database is locked" (incident 2026-05-24,
acct_2.db). This module is the single guard both code paths share, keyed per DB.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

logger = logging.getLogger("ig_pulse.jobs")

_lock = threading.Lock()
_running: set[str] = set()


def is_running(db_path: str) -> bool:
    with _lock:
        return db_path in _running


def acquire(db_path: str) -> bool:
    """Mark a job as running for db_path. Returns False if one already is."""
    with _lock:
        if db_path in _running:
            return False
        _running.add(db_path)
        return True


def release(db_path: str) -> None:
    with _lock:
        _running.discard(db_path)


def _do_fetch_job(db_path: str, token: str, ig_user_id: str) -> None:
    """The actual work: pull fresh data, then run sentiment on the new comments."""
    from app.analysis.sentiment import analyze_comments
    from app.db import connect
    from app.fetch import fetch_all

    asyncio.run(fetch_all(db_path=db_path, access_token=token, ig_user_id=ig_user_id))
    c = connect(Path(db_path))
    analyze_comments(c)
    c.close()


def start_fetch(db_path: str, token: str, ig_user_id: str) -> bool:
    """Start a background fetch+analyze for db_path.

    Returns False (and starts nothing) if a job is already running for that DB.
    """
    if not acquire(db_path):
        return False

    def run() -> None:
        try:
            _do_fetch_job(db_path, token, ig_user_id)
        except Exception:
            logger.exception("fetch job failed for %s", db_path)
        finally:
            release(db_path)

    threading.Thread(target=run, daemon=True).start()
    return True
