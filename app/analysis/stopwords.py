"""
Stopword set for IG Pulse analysis modules.

Public API
----------
    get_stopwords() -> set[str]

The returned set is the union of:
    1. Sastrawi Indonesian stopwords (126 words, always available)
    2. NLTK English stopwords (198 words, downloaded on first use)
    3. Custom list at app/analysis/stopwords_custom.txt (~60–70 tokens)

All entries are lowercased. The result is cached after first call
(module-level _cache variable) so subsequent calls are O(1).

NLTK download handling
----------------------
On first use, the module calls nltk.download('stopwords', quiet=True).
If this fails for any reason (no network, disk full, permission error),
the error is caught and logged at WARNING level. In that case the
English stopword set falls back to an empty set — import never crashes
and tokenization / analysis continues with Indonesian + custom only.
"""

from __future__ import annotations

import logging
from pathlib import Path

from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

logger = logging.getLogger(__name__)

# Module-level cache; None means "not yet computed".
_cache: set[str] | None = None

# Path to the custom file is resolved relative to *this* module, not CWD.
_CUSTOM_FILE = Path(__file__).parent / "stopwords_custom.txt"


def _load_nltk_english() -> set[str]:
    """Return NLTK English stopwords, or empty set on any failure."""
    try:
        import nltk

        nltk.download("stopwords", quiet=True)
        from nltk.corpus import stopwords

        return set(stopwords.words("english"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLTK English stopwords unavailable: %s. Using empty EN set.", exc)
        return set()


def _load_custom() -> set[str]:
    """Return tokens from stopwords_custom.txt (comments and blanks stripped)."""
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


def get_stopwords() -> set[str]:
    """Return the composed stopword set (Sastrawi ID ∪ NLTK EN ∪ custom).

    The set is computed once and cached for the lifetime of the process.
    All tokens are lowercase strings, matching the output of tokenize().

    Returns
    -------
    set[str]
        Non-empty set (at minimum the 126 Sastrawi words are always present).
    """
    global _cache
    if _cache is not None:
        return _cache

    sastrawi: set[str] = set(StopWordRemoverFactory().get_stop_words())
    english: set[str] = _load_nltk_english()
    custom: set[str] = _load_custom()

    _cache = sastrawi | english | custom
    logger.debug(
        "Stopwords loaded: %d Sastrawi + %d EN + %d custom = %d total",
        len(sastrawi),
        len(english),
        len(custom),
        len(_cache),
    )
    return _cache
