"""
Word frequency analysis for IG Pulse.

Public API
----------
    word_frequencies(comments: list[Comment], top_n: int = 100) -> list[tuple[str, int]]

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

from app.analysis.stopwords import get_stopwords
from app.analysis.tokenize import tokenize
from app.models import Comment


def word_frequencies(comments: list[Comment], top_n: int = 100) -> list[tuple[str, int]]:
    """Return the top *top_n* word frequencies across all comments.

    For each comment: tokenize the text, drop stopwords, count tokens
    across all comments in the input.

    Parameters
    ----------
    comments:
        List of Comment objects to analyse. May be empty.
    top_n:
        Maximum number of (word, count) pairs to return.

    Returns
    -------
    list[tuple[str, int]]
        Sorted by count descending, then alphabetically ascending on
        equal counts. Length is min(top_n, distinct_words).
    """
    stopwords = get_stopwords()
    counts: Counter[str] = Counter()

    for comment in comments:
        tokens = tokenize(comment.text)
        for token in tokens:
            if token not in stopwords:
                counts[token] += 1

    # Sort: primary = count desc, secondary = word asc (for determinism on ties)
    sorted_items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return sorted_items[:top_n]
