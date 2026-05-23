"""Tests for app/db.py — migrations, upserts, scoped queries, FK enforcement."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import connect, get_comments_in_scope, run_migrations, upsert_comment, upsert_post
from app.models import Comment, Post

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def conn(db_path: Path) -> sqlite3.Connection:
    c = connect(db_path)
    run_migrations(c)
    return c


def _make_post(id: str = "p1", **kwargs) -> Post:
    defaults = dict(
        id=id,
        permalink=f"https://ig.com/p/{id}",
        timestamp="2024-01-01T00:00:00Z",
        fetched_at="2024-01-02T00:00:00Z",
    )
    defaults.update(kwargs)
    return Post(**defaults)


def _make_comment(
    id: str = "c1",
    post_id: str = "p1",
    timestamp: str = "2024-01-01T10:00:00Z",
    **kwargs,
) -> Comment:
    defaults = dict(
        id=id,
        post_id=post_id,
        text="test comment",
        timestamp=timestamp,
        fetched_at="2024-01-01T11:00:00Z",
    )
    defaults.update(kwargs)
    return Comment(**defaults)


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_tables_created(self, conn: sqlite3.Connection):
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"posts", "comments", "comment_analysis", "fetch_log", "_migrations"} <= tables

    def test_indexes_created(self, conn: sqlite3.Connection):
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        assert "idx_comments_post" in indexes
        assert "idx_comments_parent" in indexes
        assert "idx_comments_timestamp" in indexes

    def test_idempotent_double_run(self, db_path: Path):
        """Running migrations twice must not raise and must not duplicate records."""
        c = connect(db_path)
        run_migrations(c)
        run_migrations(c)  # second call must be a no-op
        versions = [row[0] for row in c.execute("SELECT version FROM _migrations")]
        assert len(versions) == len(set(versions)), "Duplicate migration versions recorded"

    def test_migration_version_recorded(self, conn: sqlite3.Connection):
        versions = [row[0] for row in conn.execute("SELECT version FROM _migrations")]
        assert "001_initial.sql" in versions


# ---------------------------------------------------------------------------
# Upsert tests
# ---------------------------------------------------------------------------

class TestUpsertPost:
    def test_insert(self, conn: sqlite3.Connection):
        upsert_post(conn, _make_post("p1", caption="Hello"))
        row = conn.execute("SELECT * FROM posts WHERE id='p1'").fetchone()
        assert row is not None
        assert row["caption"] == "Hello"

    def test_update_no_dupe(self, conn: sqlite3.Connection):
        upsert_post(conn, _make_post("p1", caption="First"))
        upsert_post(conn, _make_post("p1", caption="Updated"))
        rows = conn.execute("SELECT * FROM posts WHERE id='p1'").fetchall()
        assert len(rows) == 1
        assert rows[0]["caption"] == "Updated"

    def test_nullable_fields(self, conn: sqlite3.Connection):
        upsert_post(conn, _make_post("p2"))
        row = conn.execute("SELECT * FROM posts WHERE id='p2'").fetchone()
        assert row["caption"] is None
        assert row["thumbnail_url"] is None


class TestUpsertComment:
    def test_insert(self, conn: sqlite3.Connection):
        upsert_post(conn, _make_post("p1"))
        upsert_comment(conn, _make_comment("c1", post_id="p1", text="nice"))
        row = conn.execute("SELECT * FROM comments WHERE id='c1'").fetchone()
        assert row["text"] == "nice"

    def test_update_no_dupe(self, conn: sqlite3.Connection):
        upsert_post(conn, _make_post("p1"))
        upsert_comment(conn, _make_comment("c1", text="original"))
        upsert_comment(conn, _make_comment("c1", text="edited"))
        rows = conn.execute("SELECT * FROM comments WHERE id='c1'").fetchall()
        assert len(rows) == 1
        assert rows[0]["text"] == "edited"

    def test_reply_stored(self, conn: sqlite3.Connection):
        upsert_post(conn, _make_post("p1"))
        upsert_comment(conn, _make_comment("c1"))
        upsert_comment(conn, _make_comment("c2", parent_comment_id="c1", text="reply"))
        row = conn.execute("SELECT * FROM comments WHERE id='c2'").fetchone()
        assert row["parent_comment_id"] == "c1"


# ---------------------------------------------------------------------------
# Foreign key enforcement
# ---------------------------------------------------------------------------

class TestForeignKeys:
    def test_comment_requires_existing_post(self, conn: sqlite3.Connection):
        """Inserting a comment for a non-existent post should fail."""
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO comments (id, post_id, text, timestamp, fetched_at)
                VALUES ('c99', 'no-such-post', 'oops',
                        '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
                """
            )
            conn.commit()


# ---------------------------------------------------------------------------
# get_comments_in_scope tests
# ---------------------------------------------------------------------------

class TestGetCommentsInScope:
    @pytest.fixture(autouse=True)
    def seed(self, conn: sqlite3.Connection):
        """Two posts, three comments across them, one reply."""
        upsert_post(conn, _make_post("p1"))
        upsert_post(conn, _make_post("p2"))
        upsert_comment(conn, _make_comment("c1", post_id="p1", timestamp="2024-01-10T08:00:00Z"))
        upsert_comment(conn, _make_comment("c2", post_id="p1", timestamp="2024-01-15T08:00:00Z"))
        upsert_comment(conn, _make_comment("c3", post_id="p2", timestamp="2024-02-01T08:00:00Z"))

    def test_scope_post(self, conn: sqlite3.Connection):
        result = get_comments_in_scope(conn, "post", "p1")
        assert len(result) == 2
        ids = {c.id for c in result}
        assert ids == {"c1", "c2"}

    def test_scope_post_other(self, conn: sqlite3.Connection):
        result = get_comments_in_scope(conn, "post", "p2")
        assert len(result) == 1
        assert result[0].id == "c3"

    def test_scope_all(self, conn: sqlite3.Connection):
        result = get_comments_in_scope(conn, "all")
        assert len(result) == 3

    def test_scope_period_inclusive(self, conn: sqlite3.Connection):
        result = get_comments_in_scope(conn, "period", "2024-01-01/2024-01-31")
        ids = {c.id for c in result}
        assert ids == {"c1", "c2"}
        assert "c3" not in ids

    def test_scope_period_excludes_outside(self, conn: sqlite3.Connection):
        result = get_comments_in_scope(conn, "period", "2024-02-01/2024-02-28")
        assert len(result) == 1
        assert result[0].id == "c3"

    def test_scope_post_empty(self, conn: sqlite3.Connection):
        result = get_comments_in_scope(conn, "post", "p-nonexistent")
        assert result == []

    def test_returns_comment_models(self, conn: sqlite3.Connection):
        result = get_comments_in_scope(conn, "all")
        assert all(isinstance(c, Comment) for c in result)

    def test_invalid_scope_type(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError):
            get_comments_in_scope(conn, "unknown")

    def test_invalid_period_format(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError):
            get_comments_in_scope(conn, "period", "2024-01-01")
