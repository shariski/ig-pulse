"""exclude_self toggle: the account owner's own comments/replies are dropped from
every stat when enabled, and left in when disabled."""

from __future__ import annotations

from app.db import connect, run_migrations, upsert_comment, upsert_post
from app.models import Comment, Post
from app.routes.analysis import drop_self, scope_data


def _comment(cid: str, handle: str | None) -> Comment:
    return Comment(
        id=cid, post_id="p1", parent_comment_id=None, author_handle=handle,
        text="hai", timestamp="2025-01-01T00:00:00+00:00", like_count=0,
        fetched_at="2025-01-02T00:00:00+00:00",
    )


def test_drop_self_filters_owner_case_insensitive():
    rows = [_comment("1", "Owner"), _comment("2", "fan"), _comment("3", None)]
    kept = drop_self(rows, exclude_self=True, self_handle="owner")
    assert [c.id for c in kept] == ["2", "3"]  # owner dropped, others (and None) kept


def test_drop_self_noop_when_off_or_no_handle():
    rows = [_comment("1", "owner"), _comment("2", "fan")]
    assert drop_self(rows, exclude_self=False, self_handle="owner") == rows
    assert drop_self(rows, exclude_self=True, self_handle=None) == rows


def test_scope_data_excludes_self(tmp_path):
    db = tmp_path / "a.db"
    conn = connect(db)
    run_migrations(conn)
    upsert_post(conn, Post(
        id="p1", permalink="https://ig/p1",
        timestamp="2025-01-01T00:00:00+00:00", fetched_at="2025-01-02T00:00:00+00:00",
    ))
    for cid, handle in [("1", "owner"), ("2", "fan"), ("3", "fan")]:
        upsert_comment(conn, _comment(cid, handle))
    conn.commit()
    conn.close()

    all_c, _ = scope_data(str(db), "all", None)
    assert len(all_c) == 3
    no_self, _ = scope_data(str(db), "all", None, exclude_self=True, self_handle="owner")
    assert len(no_self) == 2
    assert all(c.author_handle != "owner" for c in no_self)
