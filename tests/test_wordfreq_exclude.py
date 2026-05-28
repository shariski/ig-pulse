"""
Tests for the new `exclude_words` parameter on word_frequencies(),
plus the backward-compat snapshot.

Each test names the CLAUDE.md rule it enforces.
"""

import json
from pathlib import Path

from app.analysis.wordfreq import word_frequencies
from app.models import Comment

_NOW = "2024-01-01T00:00:00"


def _c(text: str, cid: str = "c") -> Comment:
    return Comment(id=cid, post_id="p", text=text, timestamp=_NOW, fetched_at=_NOW)


# --- backward compatibility (rule: no silent behaviour change) ---


def _fixture_comments() -> list[Comment]:
    """A deterministic list used by the snapshot test. Keep stable."""
    raw = [
        "nasi goreng enak banget",
        "nasi padang juga enak",
        "wkwk lucu banget",
        "iya kak setuju",
        "promo apa kak",
        "harga promo masih sama?",
        "pengiriman cepat sekali",
        "produk bagus sekali sayang",
        "kapan restock kak?",
        "😂😂😂",
    ]
    return [_c(t, f"c{i}") for i, t in enumerate(raw)]


def test_default_args_match_snapshot():
    """word_frequencies(comments, 100) with no exclude_words produces a
    locked-in result for the fixture comments. Regression alarm for any
    accidental behaviour change.

    To intentionally update the snapshot after a deliberate algorithm change,
    re-run with: UPDATE_SNAPSHOTS=1 pytest tests/test_wordfreq_exclude.py
    """
    import os
    result = word_frequencies(_fixture_comments(), 100)
    snapshot_path = Path(__file__).parent / "snapshots" / "wordfreq_top100.json"

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        snapshot_path.parent.mkdir(exist_ok=True)
        snapshot_path.write_text(
            json.dumps([list(t) for t in result], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return  # don't compare to what we just wrote

    assert snapshot_path.exists(), (
        f"Snapshot missing: {snapshot_path}. Re-run with UPDATE_SNAPSHOTS=1 "
        f"to regenerate after a deliberate algorithm change."
    )
    expected = [tuple(t) for t in json.loads(snapshot_path.read_text(encoding="utf-8"))]
    assert result == expected


# --- exclude_words behaviour ---


def test_exclude_words_drops_listed_tokens():
    comments = [_c("nasi goreng nasi padang", "c1"), _c("padang enak", "c2")]
    result = dict(word_frequencies(comments, 100, exclude_words={"nasi"}))
    assert "nasi" not in result
    assert result.get("padang") == 2


def test_exclude_words_case_insensitive():
    """exclude_words matches against tokenize() output, which is lowercase."""
    comments = [_c("Promo PROMO promo", "c1")]
    result = dict(word_frequencies(comments, 100, exclude_words={"PROMO"}))
    assert "promo" not in result


def test_exclude_words_reranks_remaining():
    comments = [
        _c("nasi nasi nasi", "c1"),       # nasi = 3
        _c("padang padang", "c2"),         # padang = 2
        _c("enak", "c3"),                  # enak = 1
    ]
    result = word_frequencies(comments, 100, exclude_words={"nasi"})
    words = [w for w, _ in result]
    # 'padang' now leads, 'enak' next; 'nasi' is gone.
    assert "nasi" not in words
    assert words[0] == "padang"


def test_exclude_words_empty_is_noop():
    """Empty exclude_words == None. Verifies backward compat at the param level."""
    comments = [_c("nasi goreng", "c1")]
    a = word_frequencies(comments, 100)
    b = word_frequencies(comments, 100, exclude_words=None)
    c = word_frequencies(comments, 100, exclude_words=set())
    assert a == b == c
