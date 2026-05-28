"""
Stopword set for IG Pulse analysis modules.

Public API
----------
    get_stopwords() -> set[str]
    get_base_stopwords() -> set[str]   # base layer only (used by transparency UI)

The returned set is the union of:
    1. Sastrawi Indonesian stopwords (126 words, always available)
    2. NLTK English stopwords (198 words, downloaded on first use)
    3. Custom list at app/analysis/stopwords_custom.txt
    4. User overlay rows from the user_stopwords SQLite table (queried per call)

The "base" union (1+2+3) is computed once and cached. The DB overlay (4) is
re-queried on every call — the overlay table is small and avoiding cache
invalidation bugs (when the UI adds/removes a word) is worth the few SQL
microseconds.

NLTK download handling
----------------------
On first use, the module calls nltk.download('stopwords', quiet=True). On any
failure the English set falls back to empty and the rest of the pipeline still
works.

User-stopwords DB unavailability
--------------------------------
If the DB file is missing or unreadable, the overlay falls back to an empty
set and the base stopwords are returned. The user sees their saved words stop
filtering — visible degradation, not a crash.
"""

from __future__ import annotations

import logging
from pathlib import Path

from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

from app.config import settings

logger = logging.getLogger(__name__)

_base_cache: set[str] | None = None
_CUSTOM_FILE = Path(__file__).parent / "stopwords_custom.txt"


def _load_nltk_english() -> set[str]:
    try:
        import nltk

        nltk.download("stopwords", quiet=True)
        from nltk.corpus import stopwords

        return set(stopwords.words("english"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLTK English stopwords unavailable: %s. Using empty EN set.", exc)
        return set()


def _load_custom() -> set[str]:
    words: set[str] = set()
    if not _CUSTOM_FILE.exists():
        logger.warning("Custom stopwords file not found: %s", _CUSTOM_FILE)
        return words
    with _CUSTOM_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                words.add(line.lower())
    return words


def _load_user_overlay(db_path: str | Path | None = None) -> set[str]:
    """Query user_stopwords table at *db_path*. Falls back to settings.database_path
    when db_path is None (single-DB legacy callers). Empty set on any failure."""
    try:
        from app.db import connect
        from app.analysis.user_stopwords import list_user_stopwords

        target = db_path if db_path is not None else settings.database_path
        conn = connect(target)
        try:
            return set(list_user_stopwords(conn))
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("user_stopwords overlay unavailable: %s. Using empty overlay.", exc)
        return set()


def get_base_stopwords() -> set[str]:
    """Public: base stopwords (Sastrawi ∪ NLTK ∪ custom file), cached for the process.

    Exposed so the wordfreq /filtered transparency panel can show what's being
    hidden by the built-in layer (B3 visibility).
    """
    global _base_cache
    if _base_cache is not None:
        return _base_cache

    sastrawi: set[str] = set(StopWordRemoverFactory().get_stop_words())
    english: set[str] = _load_nltk_english()
    custom: set[str] = _load_custom()
    _base_cache = sastrawi | english | custom
    logger.debug(
        "Base stopwords loaded: %d Sastrawi + %d EN + %d custom = %d",
        len(sastrawi), len(english), len(custom), len(_base_cache),
    )
    return _base_cache


def get_stopwords(db_path: str | Path | None = None) -> set[str]:
    """Return the composed stopword set.

    Base set (Sastrawi + NLTK + custom file) is cached for the process lifetime.
    User overlay is queried from *db_path* on every call (the per-account DB in
    multi-account installs) so UI changes are reflected immediately without
    cache invalidation logic. Falls back to ``settings.database_path`` when
    ``db_path`` is None — keeps single-DB legacy callers working.

    Returns
    -------
    set[str]
        Non-empty set; lowercase strings matching tokenize() output.
    """
    return get_base_stopwords() | _load_user_overlay(db_path)
