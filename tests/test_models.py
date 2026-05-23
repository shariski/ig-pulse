"""Tests for pydantic models — round-trip from sqlite3.Row and field validation."""

from __future__ import annotations

import sqlite3

import pytest

from app.models import Comment, CommentAnalysis, FetchLog, Post


def make_row(data: dict) -> sqlite3.Row:
    """Build a sqlite3.Row from a plain dict via an in-memory query."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cols = ", ".join(f"? AS {k}" for k in data)
    row = conn.execute(f"SELECT {cols}", list(data.values())).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------

class TestPost:
    def test_required_fields(self):
        p = Post(
            id="p1",
            permalink="https://ig.com/p/abc",
            timestamp="2024-01-01T00:00:00Z",
            fetched_at="2024-01-02T00:00:00Z",
        )
        assert p.id == "p1"
        assert p.caption is None
        assert p.like_count is None

    def test_from_row(self):
        data = {
            "id": "p1",
            "caption": "Hello",
            "media_type": "IMAGE",
            "permalink": "https://ig.com/p/abc",
            "timestamp": "2024-01-01T00:00:00Z",
            "like_count": 10,
            "comment_count": 5,
            "thumbnail_url": None,
            "fetched_at": "2024-01-02T00:00:00Z",
        }
        row = make_row(data)
        p = Post.from_row(row)
        assert p.id == "p1"
        assert p.caption == "Hello"
        assert p.like_count == 10
        assert p.thumbnail_url is None

    def test_nullable_fields_default_none(self):
        p = Post(
            id="x",
            permalink="https://example.com",
            timestamp="2024-01-01T00:00:00Z",
            fetched_at="2024-01-01T00:00:00Z",
        )
        assert p.caption is None
        assert p.media_type is None
        assert p.like_count is None
        assert p.comment_count is None
        assert p.thumbnail_url is None


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

class TestComment:
    def test_required_fields(self):
        c = Comment(
            id="c1", post_id="p1", text="nice post",
            timestamp="2024-01-01T10:00:00Z", fetched_at="2024-01-01T11:00:00Z"
        )
        assert c.text == "nice post"
        assert c.parent_comment_id is None
        assert c.author_handle is None

    def test_from_row(self):
        data = {
            "id": "c1",
            "post_id": "p1",
            "parent_comment_id": None,
            "author_handle": "user123",
            "text": "great!",
            "timestamp": "2024-01-01T10:00:00Z",
            "like_count": 3,
            "fetched_at": "2024-01-01T11:00:00Z",
        }
        row = make_row(data)
        c = Comment.from_row(row)
        assert c.id == "c1"
        assert c.author_handle == "user123"
        assert c.like_count == 3

    def test_reply_has_parent(self):
        c = Comment(
            id="c2", post_id="p1", parent_comment_id="c1",
            text="reply", timestamp="2024-01-01T12:00:00Z", fetched_at="2024-01-01T12:00:00Z"
        )
        assert c.parent_comment_id == "c1"


# ---------------------------------------------------------------------------
# CommentAnalysis
# ---------------------------------------------------------------------------

class TestCommentAnalysis:
    def test_from_row(self):
        data = {
            "comment_id": "c1",
            "sentiment_label": "positive",
            "sentiment_score": 0.92,
            "model_name": "test-model",
            "model_version": "1.0",
            "analyzed_at": "2024-01-02T00:00:00Z",
        }
        row = make_row(data)
        ca = CommentAnalysis.from_row(row)
        assert ca.sentiment_label == "positive"
        assert ca.sentiment_score == pytest.approx(0.92)

    def test_nullable_score(self):
        ca = CommentAnalysis(
            comment_id="c1", sentiment_label="unanalyzed",
            model_name="m", model_version="1", analyzed_at="2024-01-01T00:00:00Z"
        )
        assert ca.sentiment_score is None


# ---------------------------------------------------------------------------
# FetchLog
# ---------------------------------------------------------------------------

class TestFetchLog:
    def test_defaults(self):
        fl = FetchLog(
            run_id="run-1", scope_type="all",
            started_at="2024-01-01T00:00:00Z"
        )
        assert fl.api_calls_made == 0
        assert fl.comments_fetched == 0
        assert fl.ended_at is None
        assert fl.error is None

    def test_from_row(self):
        data = {
            "run_id": "run-1",
            "scope_type": "post",
            "scope_value": "p1",
            "started_at": "2024-01-01T00:00:00Z",
            "ended_at": "2024-01-01T01:00:00Z",
            "api_calls_made": 5,
            "comments_fetched": 42,
            "error": None,
        }
        row = make_row(data)
        fl = FetchLog.from_row(row)
        assert fl.run_id == "run-1"
        assert fl.comments_fetched == 42
