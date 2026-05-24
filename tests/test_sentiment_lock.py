"""analyze_comments must NOT hold the SQLite write lock during the (slow) model
run — otherwise a concurrent writer on the same DB hits "database is locked"
(incident 2026-05-24, acct_2.db).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.analysis import sentiment
from app.analysis.sentiment import analyze_comments
from app.db import connect, run_migrations, upsert_comment, upsert_post
from app.models import Comment, Post


def _comment(cid: str, text: str) -> Comment:
    return Comment(
        id=cid, post_id="p1", text=text,
        timestamp="2024-01-01T10:00:00Z", fetched_at="2024-01-01T11:00:00Z",
    )


def _seed(conn: sqlite3.Connection) -> None:
    upsert_post(conn, Post(
        id="p1", permalink="https://ig.com/p/p1",
        timestamp="2024-01-01T00:00:00Z", fetched_at="2024-01-01T00:00:00Z",
    ))
    # one analyzable comment + one emoji-only (the emoji-only takes the "skipped"
    # path, which is what opened the write txn early in the buggy version).
    upsert_comment(conn, _comment("c1", "bagus banget kontennya"))
    upsert_comment(conn, _comment("c2", "😀😀😀"))


def test_analyze_does_not_block_concurrent_writer_during_model(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "acct.db"
    conn = connect(db_path)
    run_migrations(conn)
    _seed(conn)

    def fake_classify(texts, model_name=None, *, batch_size=32, revision=None):
        # Simulate the slow CPU model: while it "runs", a separate connection
        # (like a concurrent fetch) must be able to write within its busy_timeout.
        probe = sqlite3.connect(db_path)
        probe.execute("PRAGMA busy_timeout=1500")
        probe.execute("INSERT INTO _migrations (version, applied_at) VALUES ('probe', 'x')")
        probe.commit()
        probe.close()
        return [("positive", 0.99) for _ in texts]

    monkeypatch.setattr(sentiment, "classify_texts", fake_classify)

    result = analyze_comments(conn)

    assert result == {"analyzed": 1, "skipped": 1}
    # The concurrent write landed; before the fix this raised "database is locked".
    assert conn.execute(
        "SELECT 1 FROM _migrations WHERE version = 'probe'"
    ).fetchone() is not None
    conn.close()
