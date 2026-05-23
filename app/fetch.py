"""Fetch orchestrator — pull posts + comments (+ depth-1 replies) into SQLite.

SQLite is the source of truth (CLAUDE.md B5); analysis reads from it, never from
the API directly. Every successful upsert commits immediately, so a crashed or
rate-limited fetch is resumable and loses nothing (risks.md R3). Rate-limit
backoff/sleep is handled inside IGClient.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import UTC, datetime

from app.db import connect, run_migrations, upsert_comment, upsert_post
from app.ig_client import IGClient
from app.models import Comment, Post

logger = logging.getLogger("ig_pulse.fetch")

_MEDIA_FIELDS = (
    "id,caption,media_type,permalink,timestamp,like_count,comments_count,thumbnail_url"
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _post_from_api(m: dict, fetched_at: str) -> Post:
    return Post(
        id=m["id"],
        caption=m.get("caption"),
        media_type=m.get("media_type"),
        permalink=m["permalink"],
        timestamp=m["timestamp"],
        like_count=m.get("like_count"),
        comment_count=m.get("comments_count"),  # API: comments_count -> model: comment_count
        thumbnail_url=m.get("thumbnail_url"),
        fetched_at=fetched_at,
    )


def _comment_from_api(c: dict, post_id: str, parent_id: str | None, fetched_at: str) -> Comment:
    return Comment(
        id=c["id"],
        post_id=post_id,
        parent_comment_id=parent_id,
        author_handle=c.get("username"),
        text=c.get("text") or "",  # emoji-only/empty handled downstream, never dropped (B3)
        timestamp=c["timestamp"],
        like_count=c.get("like_count"),
        fetched_at=fetched_at,
    )


async def fetch_all(conn: sqlite3.Connection | None = None, *, with_replies: bool = True) -> dict:
    """Pull all posts + their comments (+ depth-1 replies) into SQLite.

    Returns a summary: {run_id, posts, comments, api_calls}.
    """
    own = conn is None
    db = conn if conn is not None else connect()
    if own:
        run_migrations(db)
    try:
        return await _run_fetch(db, with_replies)
    finally:
        if own:
            db.close()


async def _run_fetch(conn: sqlite3.Connection, with_replies: bool) -> dict:
    run_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO fetch_log (run_id, scope_type, scope_value, started_at) VALUES (?,?,?,?)",
        (run_id, "all", None, _now()),
    )
    conn.commit()

    posts = comments = api_calls = 0
    try:
        async with IGClient() as ig:
            for m in await _all_media(ig):
                upsert_post(conn, _post_from_api(m, _now()))
                posts += 1
                conn.commit()
                if (m.get("comments_count") or 0) == 0:
                    continue
                comments += await _fetch_comments(ig, conn, m["id"], with_replies)
            api_calls = ig.api_calls_made
    except Exception as e:  # record failure in the log, then re-raise
        conn.execute(
            "UPDATE fetch_log SET ended_at=?, api_calls_made=?, comments_fetched=?, "
            "error=? WHERE run_id=?",
            (_now(), api_calls, comments, str(e), run_id),
        )
        conn.commit()
        raise

    conn.execute(
        "UPDATE fetch_log SET ended_at=?, api_calls_made=?, comments_fetched=? WHERE run_id=?",
        (_now(), api_calls, comments, run_id),
    )
    conn.commit()
    logger.info("fetch_all: %d posts, %d comments, %d api calls", posts, comments, api_calls)
    return {"run_id": run_id, "posts": posts, "comments": comments, "api_calls": api_calls}


async def _all_media(ig: IGClient) -> list[dict]:
    items: list[dict] = []
    after = None
    while True:
        page = await ig.list_media(limit=50, after=after, fields=_MEDIA_FIELDS)
        items.extend(page.data)
        if not page.after:
            return items
        after = page.after


async def _fetch_comments(
    ig: IGClient, conn: sqlite3.Connection, post_id: str, with_replies: bool
) -> int:
    """Fetch + upsert top-level comments for a post, then their depth-1 replies."""
    count = 0
    top_level: list[dict] = []
    after = None
    while True:
        page = await ig.get_comments(post_id, limit=50, after=after)
        for c in page.data:
            upsert_comment(conn, _comment_from_api(c, post_id, None, _now()))
            count += 1
            top_level.append(c)
        conn.commit()
        if not page.after:
            break
        after = page.after

    if with_replies:
        for c in top_level:
            rafter = None
            while True:
                rpage = await ig.get_replies(c["id"], limit=50, after=rafter)
                for r in rpage.data:
                    upsert_comment(conn, _comment_from_api(r, post_id, c["id"], _now()))
                    count += 1
                conn.commit()
                if not rpage.after:
                    break
                rafter = rpage.after
    return count
