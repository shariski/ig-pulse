"""
Word frequency analysis for IG Pulse.

Public API
----------
    word_frequencies(comments: list[Comment], top_n: int = 100,
                     exclude_words: set[str] | None = None,
                     *, db_path: str | Path | None = None) -> list[tuple[str, int]]
    comments_with_word(comments: list[Comment], word: str, n: int = 5,
                       seed: int | None = None) -> list[Comment]

The keyword-only ``db_path`` parameter on ``word_frequencies`` is threaded
through to ``get_stopwords()`` so the user-stopword overlay is read from the
correct per-account DB in multi-account installs. ``None`` falls back to
``settings.database_path`` (single-DB legacy behaviour).

Design decisions (explicit — no silent behaviour)
--------------------------------------------------
Emoji-only comments
    tokenize() returns emoji as individual tokens; stopwords_custom.txt
    contains common emoji noise. Any emoji that survive stopword filtering
    are counted and ranked normally — never silently dropped (B3).

Empty comments
    tokenize() returns [] for empty/whitespace-only text. They contribute
    zero tokens and are safely ignored.

Stopwords
    get_stopwords() is called once before the loop (not per comment) to
    avoid repeated cache lookups (though get_stopwords() is O(1) after
    first call, the set() call overhead is still avoided).

Tie-breaking
    Equal counts are broken alphabetically (ascending) for determinism.
"""

from collections import Counter
from pathlib import Path

from app.analysis.stopwords import get_stopwords
from app.analysis.tokenize import tokenize
from app.models import Comment


def word_frequencies(
    comments: list[Comment],
    top_n: int = 100,
    exclude_words: set[str] | None = None,
    *,
    db_path: str | Path | None = None,
) -> list[tuple[str, int]]:
    """Return the top *top_n* word frequencies across all comments.

    For each comment: tokenize the text, drop stopwords, optionally drop any
    word in *exclude_words*, and count what remains across all comments.

    Parameters
    ----------
    comments:
        List of Comment objects to analyse. May be empty.
    top_n:
        Maximum number of (word, count) pairs to return.
    exclude_words:
        Optional set of tokens to remove from the result, in addition to the
        global stopwords. Tokens are compared lowercase (caller is expected
        to lowercase, but we lowercase defensively).

    Returns
    -------
    list[tuple[str, int]]
        Sorted by count descending, then alphabetically ascending on ties.
        Length is min(top_n, distinct_words_after_filters).
    """
    stopwords = get_stopwords(db_path=db_path)
    exclude_lc: set[str] = {w.lower() for w in exclude_words} if exclude_words else set()
    counts: Counter[str] = Counter()

    for comment in comments:
        tokens = tokenize(comment.text)
        for token in tokens:
            if token in stopwords or token in exclude_lc:
                continue
            counts[token] += 1

    sorted_items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return sorted_items[:top_n]


import random as _random


def comments_with_word(
    comments: list[Comment],
    word: str,
    n: int = 5,
    seed: int | None = None,
) -> list[Comment]:
    """Random sample of comments whose tokenized text contains *word*.

    Match semantics intentionally mirror word_frequencies: the comment text is
    tokenized via tokenize() (lowercase + emoji-aware + URL/mention stripping)
    and *word* is matched against the resulting token set via equality —
    NOT substring. "promo" does not match "promosi". B3 compliance: emoji-only
    comments are reachable when *word* is an emoji.

    Parameters
    ----------
    comments:
        Full pool to sample from. Caller has already applied scope + sentiment
        filtering, so this function is purely about matching the word.
    word:
        Target token (case-insensitive). Whitespace is stripped.
    n:
        Maximum number of results.
    seed:
        Optional RNG seed for deterministic sampling (tests pass an int; the
        route passes None for true randomness).

    Returns
    -------
    list[Comment]
        Up to *n* comments. Empty if no comment contains the word.
    """
    target = word.strip().lower()
    if not target:
        return []
    matches = [c for c in comments if target in set(tokenize(c.text))]
    if not matches:
        return []
    rng = _random.Random(seed)
    if len(matches) <= n:
        return matches
    return rng.sample(matches, n)
