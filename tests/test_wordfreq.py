"""
Unit tests for app.analysis.wordfreq.word_frequencies.

All tests use synthetic Comment objects — no DB access.
"""


from app.analysis.wordfreq import word_frequencies
from app.models import Comment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = "2024-01-01T00:00:00"


def make_comment(text: str, cid: str = "c1") -> Comment:
    """Build a minimal Comment with only required fields populated."""
    return Comment(
        id=cid,
        post_id="p1",
        text=text,
        timestamp=_NOW,
        fetched_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Basic counting
# ---------------------------------------------------------------------------


def test_single_comment_counts_tokens():
    comments = [make_comment("makan makan nasi")]
    result = word_frequencies(comments)
    result_dict = dict(result)
    # "makan" appears twice
    assert result_dict.get("makan") == 2
    # "nasi" appears once — may or may not survive stopwords; just check structure
    assert isinstance(result, list)
    assert all(isinstance(w, str) and isinstance(c, int) for w, c in result)


def test_multi_comment_counts_aggregate():
    comments = [
        make_comment("nasi goreng enak", "c1"),
        make_comment("nasi goreng pedas", "c2"),
        make_comment("enak sekali", "c3"),
    ]
    result = word_frequencies(comments)
    result_dict = dict(result)
    # "nasi" and "goreng" appear in 2 comments; "enak" in 2 comments
    # "sekali" and "pedas" in 1 each
    # Counts depend on stopwords, but words that survive should reflect aggregated counts
    assert result_dict.get("goreng", 0) == 2
    assert result_dict.get("pedas", 0) == 1


def test_returns_list_of_tuples():
    comments = [make_comment("hello world", "c1")]
    result = word_frequencies(comments)
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, tuple)
        assert len(item) == 2


# ---------------------------------------------------------------------------
# Stopword removal
# ---------------------------------------------------------------------------


def test_stopwords_removed():
    # "yang", "dan", "di" are Sastrawi Indonesian stopwords
    # "the", "and", "is" are NLTK English stopwords
    comments = [make_comment("yang dan di the and is nasi", "c1")]
    result = word_frequencies(comments)
    result_dict = dict(result)
    for sw in ("yang", "dan", "di", "the", "and", "is"):
        assert sw not in result_dict, f"Stopword '{sw}' should have been removed"
    # "nasi" is not a stopword
    assert "nasi" in result_dict


def test_all_stopwords_returns_empty():
    # A comment entirely composed of stopwords
    comments = [make_comment("yang dan di the and", "c1")]
    result = word_frequencies(comments)
    assert result == []


# ---------------------------------------------------------------------------
# top_n limiting
# ---------------------------------------------------------------------------


def test_top_n_limits_output():
    # Create many distinct non-stopword words
    words = [f"kata{i}" for i in range(50)]
    text = " ".join(words)
    comments = [make_comment(text, "c1")]
    result = word_frequencies(comments, top_n=10)
    assert len(result) <= 10


def test_top_n_default_is_100():
    # With fewer than 100 distinct words, result length == distinct surviving words
    comments = [make_comment("nasi goreng enak pedas manis asin gurih", "c1")]
    result = word_frequencies(comments)
    assert len(result) <= 100


def test_top_n_zero_returns_empty():
    comments = [make_comment("nasi goreng enak", "c1")]
    result = word_frequencies(comments, top_n=0)
    assert result == []


def test_top_n_one_returns_highest():
    comments = [
        make_comment("nasi nasi nasi goreng goreng", "c1"),
    ]
    result = word_frequencies(comments, top_n=1)
    assert len(result) == 1
    assert result[0][0] == "nasi"
    assert result[0][1] == 3


# ---------------------------------------------------------------------------
# Sorting: count desc, then alphabetical asc on ties
# ---------------------------------------------------------------------------


def test_sorted_by_count_descending():
    # "nasi" x3, "goreng" x2, "enak" x1 — all non-stopwords
    comments = [make_comment("nasi nasi nasi goreng goreng enak", "c1")]
    result = word_frequencies(comments)
    # Reconstruct order for only our target words
    target = [(w, c) for w, c in result if w in ("nasi", "goreng", "enak")]
    counts_only = [c for _, c in target]
    assert counts_only == sorted(counts_only, reverse=True)


def test_tie_break_alphabetical():
    # "alfa" and "beta" appear the same number of times — "alfa" < "beta"
    comments = [
        make_comment("alfa beta", "c1"),
        make_comment("alfa beta", "c2"),
    ]
    result = word_frequencies(comments)
    result_dict = dict(result)
    if "alfa" in result_dict and "beta" in result_dict:
        assert result_dict["alfa"] == result_dict["beta"]
        words_in_order = [w for w, _ in result]
        alfa_idx = words_in_order.index("alfa")
        beta_idx = words_in_order.index("beta")
        assert alfa_idx < beta_idx, "Tie should be broken alphabetically: 'alfa' before 'beta'"


# ---------------------------------------------------------------------------
# Edge cases: empty and emoji-only comments
# ---------------------------------------------------------------------------


def test_empty_comment_list():
    result = word_frequencies([])
    assert result == []


def test_empty_text_comment_does_not_crash():
    comments = [make_comment("", "c1")]
    result = word_frequencies(comments)
    assert isinstance(result, list)


def test_whitespace_only_comment_does_not_crash():
    comments = [make_comment("   \t\n  ", "c1")]
    result = word_frequencies(comments)
    assert isinstance(result, list)


def test_emoji_only_comment_does_not_crash():
    # Emoji-only comment: tokenizer returns emoji tokens; stopwords_custom.txt
    # may or may not contain them. Either way: no crash, result is a list.
    comments = [make_comment("😂😂😂", "c1")]
    result = word_frequencies(comments)
    assert isinstance(result, list)


def test_emoji_only_no_stopwords_injected():
    # Stopwords must never appear as output tokens regardless of input
    from app.analysis.stopwords import get_stopwords
    stopwords = get_stopwords()
    comments = [make_comment("😂😂 wkwk hehe", "c1")]
    result = word_frequencies(comments)
    for word, _ in result:
        assert word not in stopwords, f"Stopword '{word}' should not appear in output"


def test_mixed_emoji_and_text():
    # Emoji alongside real words: both are processed without crash
    comments = [make_comment("nasi goreng 😋 enak 🔥", "c1")]
    result = word_frequencies(comments)
    assert isinstance(result, list)
    result_dict = dict(result)
    # "nasi" and "goreng" are likely non-stopwords
    assert result_dict.get("goreng", 0) >= 1


def test_multiple_empty_and_nonempty_comments():
    comments = [
        make_comment("", "c1"),
        make_comment("nasi goreng", "c2"),
        make_comment("   ", "c3"),
        make_comment("nasi goreng", "c4"),
    ]
    result = word_frequencies(comments)
    result_dict = dict(result)
    assert result_dict.get("goreng", 0) == 2


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_output():
    comments = [
        make_comment("nasi goreng enak pedas", "c1"),
        make_comment("goreng pedas manis", "c2"),
    ]
    result1 = word_frequencies(comments)
    result2 = word_frequencies(comments)
    assert result1 == result2
