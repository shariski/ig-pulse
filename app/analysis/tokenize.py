"""
Shared text tokenizer for IG Pulse analysis modules.

Public API
----------
    tokenize(text: str) -> list[str]

Design decisions (explicit — no silent behaviour)
--------------------------------------------------
URLs (@mentions, #hashtags)
    Stripped before tokenization. The patterns http://, https://, www.,
    @word, and #word are replaced with a space. Rationale: these are
    structural artefacts, not meaningful content tokens.

Punctuation
    ASCII punctuation characters are treated as separators (they never
    become tokens). A ``\\w+`` / emoji findall approach is used, so commas,
    exclamation marks, tildes, dots, hyphens, etc. are simply skipped.

Emoji
    KEPT as individual tokens at this layer. Each emoji codepoint that
    falls in a recognised Unicode emoji range is returned as its own
    1-character token. Consecutive emoji (e.g. "😂😂") become separate
    tokens ("😂", "😂"), not a single joined token.
    Rationale: the downstream stopwords layer decides whether to filter
    them. Dropping them here would make "emoji-only" comments silently
    return [], which violates the B3 "no silent dropping" rule.
    Variation Selector-16 (U+FE0F) is not matched by any token pattern,
    so it is discarded as a zero-meaning modifier — this is the one
    intentional silent discard, documented here.

Short tokens (1–2 characters)
    NOT dropped at this layer. Single-character tokens such as a lone
    Latin letter ("a", "i") or a digit ("1") pass through unchanged.
    Downstream stopwords (NLTK English list, custom list) will catch
    the ones that matter. This layer stays dumb and fast.

Casing
    All text is lowercased before any other step.

No stemming
    As per architecture.md: "No stemming in MVP". Words are kept in
    their surface form. "memakan" and "makanan" remain distinct.

Empty / whitespace-only input
    Returns [].
"""

import re

# --- pre-compiled patterns ---

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@\w+")
_HASHTAG_RE = re.compile(r"#\w+")

# Match either a run of word characters (letters, digits, _) OR a single
# emoji codepoint from the common Unicode emoji blocks.
# Variation Selector-16 (U+FE0F) and Zero-Width Joiner (U+200D) are NOT
# listed here and will be silently skipped — they carry no standalone meaning.
_TOKEN_RE = re.compile(
    r"\w+"                          # word-like: letters, digits, underscore
    r"|[\U0001F300-\U0001FAFF]"     # Misc Symbols & Pictographs, Emoticons, Transport, etc.
    r"|[\U00002600-\U000027BF]"     # Misc Symbols (☀♥❤…), Dingbats (✨✈…)
    r"|[\U0001F900-\U0001F9FF]"     # Supplemental Symbols and Pictographs
    r"|[\U00002300-\U000023FF]"     # Miscellaneous Technical (⏰⌚…)
    r"|[\U00002B00-\U00002BFF]"     # Miscellaneous Symbols and Arrows (⭐⬛…)
    r"|[\U0001FA00-\U0001FA6F]"     # Chess Symbols, extended emoji
    r"|[\U0001FA70-\U0001FAFF]"     # Symbols and Pictographs Extended-A
)


def tokenize(text: str) -> list[str]:
    """Return a list of lowercase tokens extracted from *text*.

    Steps applied in order:
    1. Lowercase.
    2. Strip URLs (http/https/www prefixes) — replaced with a space.
    3. Strip @mentions — replaced with a space.
    4. Strip #hashtags — replaced with a space.
    5. Extract tokens via findall: runs of ``\\w+`` characters OR single emoji
       codepoints from recognised Unicode emoji ranges.

    Emoji policy: each emoji codepoint becomes its own token.
    Short tokens: not filtered (1-char tokens like "a", "i" are kept).
    Variation Selector-16 (U+FE0F) is silently discarded (see module docstring).

    Parameters
    ----------
    text:
        Raw comment text, any language, may contain emoji, URLs, mentions.

    Returns
    -------
    list[str]
        Possibly empty list of lowercase token strings. Pure and deterministic.
    """
    if not text or not text.strip():
        return []
    text = text.lower()
    text = _URL_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    text = _HASHTAG_RE.sub(" ", text)
    return _TOKEN_RE.findall(text)
