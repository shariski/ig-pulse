"""Pydantic v2 models for IG Pulse data, matching the SQLite schema exactly."""

from __future__ import annotations

import sqlite3

from pydantic import BaseModel


class Post(BaseModel):
    id: str
    caption: str | None = None
    media_type: str | None = None
    permalink: str
    timestamp: str
    like_count: int | None = None
    comment_count: int | None = None
    thumbnail_url: str | None = None
    fetched_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Post:
        return cls(**dict(row))


class Comment(BaseModel):
    id: str
    post_id: str
    parent_comment_id: str | None = None
    author_handle: str | None = None
    text: str
    timestamp: str
    like_count: int | None = None
    fetched_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Comment:
        return cls(**dict(row))


class CommentAnalysis(BaseModel):
    comment_id: str
    sentiment_label: str
    sentiment_score: float | None = None
    model_name: str
    model_version: str
    analyzed_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CommentAnalysis:
        return cls(**dict(row))


class FetchLog(BaseModel):
    run_id: str
    scope_type: str
    scope_value: str | None = None
    started_at: str
    ended_at: str | None = None
    api_calls_made: int = 0
    comments_fetched: int = 0
    error: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> FetchLog:
        return cls(**dict(row))
