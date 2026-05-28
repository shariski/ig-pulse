"""Tests for app.analysis.wordfreq.comments_with_word — qualitative drill-down."""

from app.analysis.wordfreq import comments_with_word
from app.models import Comment

_NOW = "2024-01-01T00:00:00"


def _c(text: str, cid: str = "c1") -> Comment:
    return Comment(id=cid, post_id="p", text=text, timestamp=_NOW, fetched_at=_NOW)


def test_returns_only_matches():
    comments = [
        _c("nasi goreng enak", "c1"),
        _c("padang juga enak", "c2"),
        _c("wkwk", "c3"),
    ]
    out = comments_with_word(comments, "enak", n=10, seed=42)
    ids = {c.id for c in out}
    assert ids == {"c1", "c2"}


def test_match_is_token_equality_not_substring():
    """B3 evidence: 'promo' should NOT match 'promosi'."""
    comments = [
        _c("ada promo gak", "c1"),
        _c("promosi besar", "c2"),
    ]
    out = comments_with_word(comments, "promo", n=10, seed=42)
    assert {c.id for c in out} == {"c1"}


def test_match_case_insensitive():
    comments = [_c("Promo Besar PROMO", "c1")]
    out = comments_with_word(comments, "PROMO", n=10, seed=42)
    assert len(out) == 1


def test_emoji_word_matches_emoji_comment():
    """B3 compliance: emoji-only comments must be reachable from drill-down."""
    comments = [
        _c("😂😂😂", "c1"),
        _c("biasa aja", "c2"),
    ]
    out = comments_with_word(comments, "😂", n=10, seed=42)
    assert [c.id for c in out] == ["c1"]


def test_seed_makes_sample_deterministic():
    comments = [_c(f"nasi enak {i}", f"c{i}") for i in range(20)]
    a = comments_with_word(comments, "nasi", n=5, seed=42)
    b = comments_with_word(comments, "nasi", n=5, seed=42)
    assert [c.id for c in a] == [c.id for c in b]


def test_no_matches_returns_empty_list():
    comments = [_c("nasi goreng", "c1")]
    assert comments_with_word(comments, "doesnotexist", n=5, seed=42) == []


def test_n_caps_result_length():
    comments = [_c("nasi enak", f"c{i}") for i in range(20)]
    out = comments_with_word(comments, "nasi", n=3, seed=42)
    assert len(out) == 3
