"""SQLite overlay for user-defined stopwords.

Layered on top of app/analysis/stopwords_custom.txt without modifying it.
All entries are normalised to lowercase + stripped + truncated to 50 chars,
matching the tokenize() output and the URL-abuse defense documented in
docs/superpowers/specs/2026-05-28-wordfreq-enhancement-design.md.

Functions take an already-open sqlite3 Connection so callers can compose
inside a request handler's connection lifecycle (no implicit connect).
"""

from __future__ import annotations

import sqlite3

_MAX_WORD_LEN = 50


def _normalise(word: str) -> str:
    """Lowercase, strip, truncate. Raises ValueError if empty after stripping."""
    cleaned = (word or "").strip().lower()
    if not cleaned:
        raise ValueError("user stopword cannot be empty")
    return cleaned[:_MAX_WORD_LEN]


def list_user_stopwords(conn: sqlite3.Connection) -> list[str]:
    """Return all saved user stopwords, sorted alphabetically ascending."""
    return [
        row[0]
        for row in conn.execute("SELECT word FROM user_stopwords ORDER BY word")
    ]


def add_user_stopword(conn: sqlite3.Connection, word: str) -> None:
    """Insert *word* into user_stopwords. Idempotent (INSERT OR IGNORE).

    Word is normalised before insert. Raises ValueError on empty input.
    """
    normalised = _normalise(word)
    conn.execute(
        "INSERT OR IGNORE INTO user_stopwords (word) VALUES (?)",
        (normalised,),
    )
    conn.commit()


def remove_user_stopword(conn: sqlite3.Connection, word: str) -> None:
    """Delete *word* from user_stopwords. Silent no-op if not present.

    Word is normalised before delete (so saved 'iya' is found by 'IYA').
    Empty input is silently ignored (deletion is forgiving, not strict).
    """
    try:
        normalised = _normalise(word)
    except ValueError:
        return
    conn.execute("DELETE FROM user_stopwords WHERE word = ?", (normalised,))
    conn.commit()
