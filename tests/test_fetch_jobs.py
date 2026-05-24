"""Per-account guard so two fetch+analyze jobs never run against the same
SQLite file concurrently.

Incident 2026-05-24: adding an account (first fetch) and a manual refresh both
ran fetch_all + analyze_comments on acct_2.db at once -> "database is locked".
The two code paths must share one guard, keyed per account DB.
"""

from __future__ import annotations

import threading
import time

from app import fetch_jobs


def test_acquire_blocks_second_concurrent_job_on_same_db():
    assert fetch_jobs.acquire("/data/acct_2.db") is True
    assert fetch_jobs.acquire("/data/acct_2.db") is False  # already running
    fetch_jobs.release("/data/acct_2.db")
    assert fetch_jobs.acquire("/data/acct_2.db") is True  # freed -> can start again
    fetch_jobs.release("/data/acct_2.db")


def test_acquire_is_independent_per_db():
    assert fetch_jobs.acquire("/data/acct_1.db") is True
    assert fetch_jobs.acquire("/data/acct_2.db") is True  # different account -> independent
    fetch_jobs.release("/data/acct_1.db")
    fetch_jobs.release("/data/acct_2.db")


def test_start_fetch_runs_worker_once_then_frees(monkeypatch):
    started = threading.Event()
    proceed = threading.Event()
    calls: list[str] = []

    def fake_job(db_path, token, ig_user_id):
        calls.append(db_path)
        started.set()
        proceed.wait(2)

    monkeypatch.setattr(fetch_jobs, "_do_fetch_job", fake_job)

    assert fetch_jobs.start_fetch("/data/acct_9.db", "tok", "IG9") is True
    started.wait(2)
    # while the first job is still running, a second start is refused
    assert fetch_jobs.is_running("/data/acct_9.db") is True
    assert fetch_jobs.start_fetch("/data/acct_9.db", "tok", "IG9") is False

    proceed.set()
    deadline = time.time() + 2
    while fetch_jobs.is_running("/data/acct_9.db") and time.time() < deadline:
        time.sleep(0.01)

    assert fetch_jobs.is_running("/data/acct_9.db") is False
    assert calls == ["/data/acct_9.db"]  # worker ran exactly once
