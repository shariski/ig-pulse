"""SQLite connection and raw-SQL helpers for IG Pulse.

No ORM. No migration framework. Just stdlib sqlite3.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import settings
from app.models import Comment, Post

# Path to the migrations directory (relative to this file's package root)
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a sqlite3 connection with row_factory and foreign keys enabled.

    WAL mode + a busy timeout let the dashboard's constant read-polling coexist
    with a background fetch/analysis write — without WAL the writer hits
    "database is locked" against concurrent readers (deployed multi-user case).
    """
    path = db_path if db_path is not None else settings.database_path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply any unapplied numbered *.sql migrations. Idempotent."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            version     TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL
        )
        """
    )
    conn.commit()

    applied: set[str] = {
        row[0] for row in conn.execute("SELECT version FROM _migrations")
    }

    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for sql_file in sql_files:
        version = sql_file.name
        if version in applied:
            continue
        sql = sql_file.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO _migrations (version, applied_at) VALUES (?, datetime('now'))",
            (version,),
        )
        conn.commit()


def upsert_post(conn: sqlite3.Connection, post: Post) -> None:
    """Insert or update a Post row. Re-upserting the same id updates in place."""
    conn.execute(
        """
        INSERT INTO posts (id, caption, media_type, permalink, timestamp,
                           like_count, comment_count, thumbnail_url, fetched_at)
        VALUES (:id, :caption, :media_type, :permalink, :timestamp,
                :like_count, :comment_count, :thumbnail_url, :fetched_at)
        ON CONFLICT(id) DO UPDATE SET
            caption       = excluded.caption,
            media_type    = excluded.media_type,
            permalink     = excluded.permalink,
            timestamp     = excluded.timestamp,
            like_count    = excluded.like_count,
            comment_count = excluded.comment_count,
            thumbnail_url = excluded.thumbnail_url,
            fetched_at    = excluded.fetched_at
        """,
        post.model_dump(),
    )
    conn.commit()


def upsert_comment(conn: sqlite3.Connection, comment: Comment) -> None:
    """Insert or update a Comment row. Re-upserting the same id updates in place."""
    conn.execute(
        """
        INSERT INTO comments (id, post_id, parent_comment_id, author_handle,
                              text, timestamp, like_count, fetched_at)
        VALUES (:id, :post_id, :parent_comment_id, :author_handle,
                :text, :timestamp, :like_count, :fetched_at)
        ON CONFLICT(id) DO UPDATE SET
            post_id           = excluded.post_id,
            parent_comment_id = excluded.parent_comment_id,
            author_handle     = excluded.author_handle,
            text              = excluded.text,
            timestamp         = excluded.timestamp,
            like_count        = excluded.like_count,
            fetched_at        = excluded.fetched_at
        """,
        comment.model_dump(),
    )
    conn.commit()


def get_comments_in_scope(
    conn: sqlite3.Connection,
    scope_type: str,
    scope_value: str | None = None,
) -> list[Comment]:
    """Return comments matching the given scope.

    scope_type:
      "post"   — scope_value is a post id; returns all comments for that post.
      "period" — scope_value is an ISO date range "YYYY-MM-DD/YYYY-MM-DD" (inclusive).
      "all"    — returns every comment; scope_value ignored.
    """
    if scope_type == "post":
        rows = conn.execute(
            "SELECT * FROM comments WHERE post_id = ? ORDER BY timestamp",
            (scope_value,),
        ).fetchall()
    elif scope_type == "period":
        if not scope_value or "/" not in scope_value:
            raise ValueError(
                "scope_value for 'period' must be 'YYYY-MM-DD/YYYY-MM-DD'"
            )
        start, end = scope_value.split("/", 1)
        # timestamp is ISO-8601; string comparison works for UTC dates
        rows = conn.execute(
            "SELECT * FROM comments WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
            (start, end + "T23:59:59Z"),
        ).fetchall()
    elif scope_type == "all":
        rows = conn.execute(
            "SELECT * FROM comments ORDER BY timestamp"
        ).fetchall()
    else:
        raise ValueError(f"Unknown scope_type: {scope_type!r}")

    return [Comment.from_row(row) for row in rows]
