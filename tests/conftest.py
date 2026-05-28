"""Shared pytest fixtures.

Mirrors the inline client setup in ``tests/test_routes.py`` (isolated registry +
data dir under ``tmp_path``, register a user, create one IG account, switch into
it) and exposes it as a reusable ``authed_client``. Also provides seed helpers
used by route-level tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import registry
from app.config import settings
from app.db import connect as db_connect
from app.db import run_migrations, upsert_comment, upsert_post
from app.models import Comment, Post

_NOW = "2024-01-01T00:00:00"


def _post(post_id: str = "p1", caption: str | None = None) -> Post:
    return Post(
        id=post_id, caption=caption, media_type="IMAGE",
        permalink=f"https://ig/{post_id}", timestamp=_NOW,
        like_count=0, comment_count=0, thumbnail_url=None, fetched_at=_NOW,
    )


def _comment(cid: str, text: str, *, post_id: str = "p1") -> Comment:
    return Comment(
        id=cid, post_id=post_id, parent_comment_id=None,
        author_handle="fan", text=text, timestamp=_NOW,
        like_count=0, fetched_at=_NOW,
    )


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    """A TestClient with an isolated registry/data dir, a registered user, and a
    switched-to IG account. Yields ``(client, account)`` so seed helpers can
    write to the account's per-account DB."""
    monkeypatch.setattr(settings, "database_path", tmp_path / "legacy.db")
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    from app.main import app

    with TestClient(app) as c:
        c.post("/register", data={"username": "u", "password": "password1", "confirm": "password1"})
        rconn = registry.connect()
        uid = registry.get_user_by_name(rconn, "u")["id"]
        aid = registry.create_account(rconn, uid, "1", "u_ig", "tok", None)
        acct = dict(registry.get_account(rconn, aid))
        rconn.close()
        d = db_connect(acct["db_path"])
        run_migrations(d)
        d.close()
        c.post("/accounts/switch", data={"account_id": aid})
        # Stash the account dict on the client so tests can write to its DB.
        c.account = acct  # type: ignore[attr-defined]
        c.db_path = acct["db_path"]  # type: ignore[attr-defined]
        yield c


def _seed(db_path: str, comments: list[Comment], post_ids: set[str]) -> None:
    conn = db_connect(db_path)
    try:
        run_migrations(conn)
        for pid in post_ids:
            upsert_post(conn, _post(pid))
        for c in comments:
            upsert_comment(conn, c)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_comments(authed_client):
    """Seeds enough comments that the word cloud renders non-empty. Includes
    'nasi' and 'mantap' as tokens we can later exclude. Uses 'iya' too (already
    a project stopword, so it never appears in the cloud — useful for the
    'asserts absence' test which is also vacuously true)."""
    comments = [
        _comment("c1", "nasi goreng enak banget"),
        _comment("c2", "nasi padang juga enak"),
        _comment("c3", "mantap mantap mantap"),
        _comment("c4", "iya kak setuju"),
        _comment("c5", "promo apa kak"),
        _comment("c6", "produk bagus sekali"),
    ]
    _seed(authed_client.account["db_path"], comments, {"p1"})
    return comments


@pytest.fixture
def seeded_with_sentiment(authed_client):
    """Seeds comments AND comment_analysis rows so the sentiment filter has data.

    - 'positiveword' appears ONLY in comments classified positive.
    - 'negativeword' appears ONLY in comments classified negative.
    Used by the sentiment-filter test to verify cross-bucket leakage doesn't
    happen.
    """
    comments = [
        _comment("p_a", "positiveword positiveword sangat bagus"),
        _comment("p_b", "positiveword mantap sekali"),
        _comment("n_a", "negativeword rusak sekali"),
        _comment("n_b", "negativeword kecewa banget"),
        _comment("u_a", "kata netral biasa saja"),
    ]
    db_path = authed_client.account["db_path"]
    _seed(db_path, comments, {"p1"})
    conn = db_connect(db_path)
    try:
        rows = [
            ("p_a", "positive"), ("p_b", "positive"),
            ("n_a", "negative"), ("n_b", "negative"),
            ("u_a", "neutral"),
        ]
        for cid, label in rows:
            conn.execute(
                """
                INSERT INTO comment_analysis
                    (comment_id, sentiment_label, sentiment_score, model_name,
                     model_version, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(comment_id) DO UPDATE SET
                    sentiment_label=excluded.sentiment_label
                """,
                (cid, label, 0.9, "test-model", "v0", _NOW),
            )
        conn.commit()
    finally:
        conn.close()
    return comments
