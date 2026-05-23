"""Tests for app.analysis.phrases — synthetic Comment lists only, no DB access."""

from __future__ import annotations

from app.analysis.phrases import top_phrases
from app.models import Comment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_comment(text: str) -> Comment:
    """Build a minimal valid Comment with the given text."""
    return Comment(
        id="x",
        post_id="p",
        text=text,
        timestamp="2024-01-01T00:00:00Z",
        fetched_at="2024-01-01T00:00:00Z",
    )


def _comments(*texts: str) -> list[Comment]:
    return [_make_comment(t) for t in texts]


# ---------------------------------------------------------------------------
# Bigram generation
# ---------------------------------------------------------------------------

def test_bigram_generated_within_comment():
    """A 2-token comment produces exactly one bigram."""
    # Repeat the same comment 3 times so it clears min_count=3
    comments = _comments(
        "produk bagus",
        "produk bagus",
        "produk bagus",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "produk bagus" in phrases


def test_bigram_count_correct():
    """Bigram count equals the number of comments containing it."""
    comments = _comments(
        "konten menarik",
        "konten menarik",
        "konten menarik",
        "konten menarik",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    counts = dict(result)
    assert counts.get("konten menarik") == 4


# ---------------------------------------------------------------------------
# Trigram generation
# ---------------------------------------------------------------------------

def test_trigram_generated_within_comment():
    """A 3-token comment produces one trigram (and two bigrams)."""
    comments = _comments(
        "konten sangat menarik",
        "konten sangat menarik",
        "konten sangat menarik",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "konten sangat menarik" in phrases


def test_four_token_comment_produces_two_trigrams():
    """'a b c d' → trigrams 'a b c' and 'b c d', each count 3."""
    # Use words unlikely to be stopwords
    comments = _comments(
        "konten keren mantap sekali",
        "konten keren mantap sekali",
        "konten keren mantap sekali",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "konten keren mantap" in phrases
    assert "keren mantap sekali" in phrases


# ---------------------------------------------------------------------------
# min_count threshold
# ---------------------------------------------------------------------------

def test_phrase_below_min_count_excluded():
    """A phrase appearing only twice is excluded when min_count=3."""
    comments = _comments(
        "produk bagus",
        "produk bagus",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "produk bagus" not in phrases


def test_phrase_exactly_at_min_count_included():
    """A phrase appearing exactly min_count times is included."""
    comments = _comments(
        "produk keren",
        "produk keren",
        "produk keren",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "produk keren" in phrases


# ---------------------------------------------------------------------------
# Stopword-token rejection
# ---------------------------------------------------------------------------

def test_phrase_with_stopword_token_excluded():
    """Phrases containing a stopword token must be filtered out.

    'yang' is a Sastrawi Indonesian stopword. Any bigram/trigram containing
    it should be dropped.
    """
    # 'produk yang' — 'yang' is a stopword → should be excluded
    comments = _comments(
        "produk yang bagus",
        "produk yang bagus",
        "produk yang bagus",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    # The only bigrams are "produk yang" and "yang bagus" — both contain "yang"
    assert "produk yang" not in phrases
    assert "yang bagus" not in phrases
    # The trigram "produk yang bagus" also contains "yang"
    assert "produk yang bagus" not in phrases


def test_phrase_all_content_words_kept():
    """Phrases with no stopword tokens are included."""
    comments = _comments(
        "produk keren mantap",
        "produk keren mantap",
        "produk keren mantap",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "produk keren" in phrases
    assert "keren mantap" in phrases
    assert "produk keren mantap" in phrases


# ---------------------------------------------------------------------------
# All-emoji rejection
# ---------------------------------------------------------------------------

def test_all_emoji_phrase_excluded():
    """An n-gram composed entirely of emoji tokens is excluded."""
    # Each comment is two emoji — the only bigram is emoji+emoji
    comments = _comments("😂🔥", "😂🔥", "😂🔥")
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "😂 🔥" not in phrases


def test_mixed_emoji_word_phrase_kept_if_no_stopword():
    """A phrase with at least one alphanumeric token is kept (if no stopword).

    Uses 🎉 (not in the custom stopword list) to avoid the stopword filter.
    Common emoji like 😍/🔥/😂 ARE in the custom stopword list by design.
    """
    comments = _comments(
        "bagus 🎉 keren",
        "bagus 🎉 keren",
        "bagus 🎉 keren",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    # "bagus 🎉" and "🎉 keren" both have alphanumeric tokens and no stopwords → kept
    assert "bagus 🎉" in phrases or "🎉 keren" in phrases


# ---------------------------------------------------------------------------
# No cross-comment n-grams
# ---------------------------------------------------------------------------

def test_no_cross_comment_bigrams():
    """The last token of comment N and the first token of comment N+1
    must NOT form a bigram."""
    # If cross-comment bigrams were generated, "keren produk" would appear 3 times
    # (end of each "sangat keren" and start of next "produk mantap")
    comments = _comments(
        "sangat keren",
        "produk mantap",
        "sangat keren",
        "produk mantap",
        "sangat keren",
        "produk mantap",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "keren produk" not in phrases


def test_no_cross_comment_trigrams():
    """Trigrams must not span comment boundaries."""
    # If cross-comment, "c a b" or "b c a" style leaks would appear
    comments = _comments(
        "produk mantap sekali",
        "sangat keren banget",
        "produk mantap sekali",
        "sangat keren banget",
        "produk mantap sekali",
        "sangat keren banget",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    # "sekali sangat" would only exist if we bridged comments
    assert "sekali sangat" not in phrases
    assert "sekali sangat keren" not in phrases


# ---------------------------------------------------------------------------
# Top-N limit and tie-break ordering
# ---------------------------------------------------------------------------

def test_top_n_limits_output():
    """top_n=2 returns at most 2 phrases."""
    # Create 3 distinct phrases each appearing 3 times
    comments = _comments(
        "produk keren mantap",
        "produk keren mantap",
        "produk keren mantap",
        "konten bagus sekali",
        "konten bagus sekali",
        "konten bagus sekali",
    )
    result = top_phrases(comments, top_n=2, min_count=3)
    assert len(result) <= 2


def test_sorted_by_count_descending():
    """Higher-count phrases appear before lower-count ones."""
    comments = _comments(
        "produk keren",
        "produk keren",
        "produk keren",
        "produk keren",   # count=4
        "konten bagus",
        "konten bagus",
        "konten bagus",   # count=3
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    counts = dict(result)
    assert counts.get("produk keren", 0) > counts.get("konten bagus", 0)
    # "produk keren" should appear first
    phrases = [p for p, _ in result]
    assert phrases.index("produk keren") < phrases.index("konten bagus")


def test_tie_break_alphabetical():
    """When two phrases have equal counts, alphabetically earlier comes first."""
    comments = _comments(
        "zebra mantap",
        "zebra mantap",
        "zebra mantap",
        "alfa keren",
        "alfa keren",
        "alfa keren",
    )
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    # Both have count=3; "alfa keren" < "zebra mantap" alphabetically
    assert phrases.index("alfa keren") < phrases.index("zebra mantap")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_comment_list():
    assert top_phrases([], top_n=20, min_count=3) == []


def test_single_token_comment_no_ngrams():
    """A comment with only one token produces no bigrams or trigrams."""
    comments = _comments("bagus", "bagus", "bagus")
    result = top_phrases(comments, top_n=20, min_count=3)
    assert result == []


def test_two_token_comment_only_bigram():
    """A comment with exactly 2 tokens produces a bigram but no trigram."""
    comments = _comments("produk keren", "produk keren", "produk keren")
    result = top_phrases(comments, top_n=20, min_count=3)
    phrases = [p for p, _ in result]
    assert "produk keren" in phrases
    # No trigram possible from 2 tokens
    assert all(len(p.split()) <= 2 for p in phrases)
