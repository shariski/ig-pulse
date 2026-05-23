"""Tests for the fetch orchestrator's pure API->model mappers (no network)."""

from __future__ import annotations

from app.fetch import _comment_from_api, _post_from_api


def test_post_mapper_maps_comments_count_to_comment_count():
    api = {
        "id": "p1",
        "caption": "halo",
        "media_type": "IMAGE",
        "permalink": "https://instagram.com/p/abc",
        "timestamp": "2024-01-01T00:00:00+0000",
        "like_count": 12,
        "comments_count": 5,  # API name differs from the model field
        "thumbnail_url": None,
    }
    post = _post_from_api(api, fetched_at="2024-01-02T00:00:00Z")
    assert post.id == "p1"
    assert post.comment_count == 5  # mapped from comments_count
    assert post.like_count == 12
    assert post.fetched_at == "2024-01-02T00:00:00Z"


def test_post_mapper_tolerates_missing_optional_fields():
    api = {
        "id": "p2",
        "permalink": "https://instagram.com/p/x",
        "timestamp": "2024-01-01T00:00:00+0000",
    }
    post = _post_from_api(api, fetched_at="2024-01-02T00:00:00Z")
    assert post.caption is None
    assert post.comment_count is None
    assert post.media_type is None


def test_comment_mapper_maps_username_to_author_and_keeps_emoji():
    api = {
        "id": "c1",
        "text": "mantap 🔥",
        "username": "someone",
        "timestamp": "2024-01-01T10:00:00+0000",
        "like_count": 2,
    }
    c = _comment_from_api(api, post_id="p1", parent_id=None, fetched_at="2024-01-01T11:00:00Z")
    assert c.author_handle == "someone"
    assert c.text == "mantap 🔥"  # emoji preserved, not dropped (B3)
    assert c.parent_comment_id is None


def test_comment_mapper_sets_parent_for_replies_and_handles_empty_text():
    api = {"id": "r1", "username": "u", "timestamp": "2024-01-01T12:00:00+0000"}
    r = _comment_from_api(api, post_id="p1", parent_id="c1", fetched_at="2024-01-01T12:00:00Z")
    assert r.parent_comment_id == "c1"
    assert r.text == ""  # missing text -> empty string, never None (text is NOT NULL)
