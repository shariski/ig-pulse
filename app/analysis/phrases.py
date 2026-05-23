"""N-gram dominant-phrase extraction for IG Pulse.

Public API
----------
    top_phrases(comments, top_n=20, min_count=3) -> list[tuple[str, int]]

Design decisions
----------------
Bigrams + trigrams:
    Generated within each comment only — never bridging across comment
    boundaries. Two consecutive tokens in the same comment form a bigram;
    three consecutive tokens form a trigram.

Filtering (applied per unique n-gram, after counting across all comments):
    1. count >= min_count  — phrases that appear fewer times are noise.
    2. No stopword tokens  — if ANY token in the n-gram is in get_stopwords()
       the phrase is dropped. Both bigrams and trigrams must be content-only.
    3. Not entirely emoji/symbols — the phrase must contain at least one token
       with an alphanumeric character (a-z, 0-9). Emoji-only sequences carry
       visual emotion but not "narrative dominan" content.

Stopwords loaded once:
    get_stopwords() is called once at function entry; its own module-level
    cache means the cost is amortised across multiple top_phrases() calls.

No DB access:
    Pure function over list[Comment]. The caller fetches comments from SQLite.
"""

from __future__ import annotations

from collections import Counter

from app.analysis.stopwords import get_stopwords
from app.analysis.tokenize import tokenize
from app.models import Comment

_ALPHANUMERIC_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")


def _has_alphanumeric(token: str) -> bool:
    return any(ch in _ALPHANUMERIC_CHARS for ch in token)


def top_phrases(
    comments: list[Comment],
    top_n: int = 20,
    min_count: int = 3,
) -> list[tuple[str, int]]:
    """Return the top *top_n* bigrams+trigrams across *comments*.

    Parameters
    ----------
    comments:
        List of Comment objects. Only comment.text is read; no DB access.
    top_n:
        Maximum number of phrases to return.
    min_count:
        Phrases occurring fewer than this many times are excluded.

    Returns
    -------
    list[tuple[str, int]]
        Sorted by count descending, then alphabetically for determinism.
        Each entry is (phrase_string, count) where phrase_string is tokens
        joined by a single space.
    """
    stopwords = get_stopwords()
    counts: Counter[str] = Counter()

    for comment in comments:
        tokens = tokenize(comment.text)
        n = len(tokens)

        # Bigrams: pairs of consecutive tokens within this comment
        for i in range(n - 1):
            gram = (tokens[i], tokens[i + 1])
            counts[" ".join(gram)] += 1

        # Trigrams: triples of consecutive tokens within this comment
        for i in range(n - 2):
            gram = (tokens[i], tokens[i + 1], tokens[i + 2])
            counts[" ".join(gram)] += 1

    results: list[tuple[str, int]] = []
    for phrase, count in counts.items():
        if count < min_count:
            continue
        tokens_in_phrase = phrase.split(" ")
        # Reject if any token is a stopword
        if any(t in stopwords for t in tokens_in_phrase):
            continue
        # Reject if no token has an alphanumeric character (all-emoji/symbol)
        if not any(_has_alphanumeric(t) for t in tokens_in_phrase):
            continue
        results.append((phrase, count))

    # Sort: count descending, then phrase alphabetically for determinism
    results.sort(key=lambda x: (-x[1], x[0]))
    return results[:top_n]
