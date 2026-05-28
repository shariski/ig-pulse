# Word Frequency Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-view exclusion chips (with save-to-permanent), a sentiment-bucket input filter, a click-to-drill-down sample modal, and a "what's filtered" transparency panel to the existing word frequency feature in IG Pulse — without adding new ML dependencies.

**Architecture:** Token-based counting stays; one new optional parameter (`exclude_words`) on `word_frequencies()` and one new helper (`comments_with_word()`) carry the analysis layer. A new `user_stopwords` SQLite table overlays the file-based stopword list via a refactored `get_stopwords()`. UI state lives in URL params (`?sentiment=…&exclude=…`) so chips are shareable and back-button-friendly. All interactions are HTMX swaps; no client framework, no JS bundler.

**Tech Stack:** Python 3.12, FastAPI, SQLite (stdlib `sqlite3`), Jinja2, HTMX, pytest. Existing project patterns: file-based migrations under `app/migrations/*.sql`, server-rendered partial templates under `app/templates/partials/`, route handlers under `app/routes/`.

**Spec:** `docs/superpowers/specs/2026-05-28-wordfreq-enhancement-design.md`

---

## File Map

**Create:**
- `app/migrations/002_user_stopwords.sql`
- `app/analysis/user_stopwords.py`
- `app/templates/partials/_wordfreq_sample.html`
- `app/templates/partials/_wordfreq_filtered.html`
- `tests/test_user_stopwords.py`
- `tests/test_wordfreq_comments_with_word.py`
- `tests/test_wordfreq_exclude.py`
- `tests/test_routes_wordfreq.py`
- `tests/test_export_wordfreq_filters.py`

**Modify:**
- `app/analysis/wordfreq.py` — add `exclude_words` param + `comments_with_word()`
- `app/analysis/stopwords.py` — split file cache from DB overlay; recompose on each call
- `app/routes/analysis.py` — wordfreq fragment accepts new params; add 4 new endpoints
- `app/routes/export.py` — `/export/wordfreq` passthrough for the new filter params
- `app/templates/partials/frag_wordfreq.html` — sentiment control, chip area, clickable words
- `tests/test_stopwords.py` — update the identity-cache test (semantics intentionally change)
- `tests/test_wordfreq.py` — only if existing test signatures break (they should not; new param defaults to `None`)

---

## Phase A — Data layer (migration + stopword overlay)

### Task 1: Migration for `user_stopwords` table

**Files:**
- Create: `app/migrations/002_user_stopwords.sql`
- Test: `tests/test_db.py` (extend existing file with one new test)

- [ ] **Step 1: Write the failing test in `tests/test_db.py`**

Append to the end of the file:

```python
def test_user_stopwords_table_created_by_migration(tmp_path):
    """002_user_stopwords.sql creates the table with the expected schema."""
    from app.db import connect, run_migrations
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    try:
        run_migrations(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(user_stopwords)")}
        assert cols == {"word", "created_at"}
        # word is PRIMARY KEY
        pk_rows = [r for r in conn.execute("PRAGMA table_info(user_stopwords)") if r[5] == 1]
        assert len(pk_rows) == 1 and pk_rows[0][1] == "word"
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_user_stopwords_table_created_by_migration -v`
Expected: FAIL with "no such table: user_stopwords" or an empty `PRAGMA table_info`.

- [ ] **Step 3: Create the migration file**

Create `app/migrations/002_user_stopwords.sql`:

```sql
-- Per-user custom stopwords that overlay app/analysis/stopwords_custom.txt
-- without modifying the checked-in file. INSERT OR IGNORE on add makes
-- the add path idempotent.
CREATE TABLE IF NOT EXISTS user_stopwords (
    word        TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py::test_user_stopwords_table_created_by_migration -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/migrations/002_user_stopwords.sql tests/test_db.py
git commit -m "Add user_stopwords table migration"
```

---

### Task 2: `user_stopwords.py` CRUD module

**Files:**
- Create: `app/analysis/user_stopwords.py`
- Test: `tests/test_user_stopwords.py`

- [ ] **Step 1: Write the failing test file `tests/test_user_stopwords.py`**

```python
"""Tests for app.analysis.user_stopwords — SQLite overlay CRUD."""

import pytest

from app.analysis.user_stopwords import (
    add_user_stopword,
    list_user_stopwords,
    remove_user_stopword,
)
from app.db import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    run_migrations(conn)
    yield conn
    conn.close()


def test_list_empty_initially(conn):
    assert list_user_stopwords(conn) == []


def test_add_inserts_lowercase(conn):
    add_user_stopword(conn, "Mantap")
    assert list_user_stopwords(conn) == ["mantap"]


def test_add_strips_whitespace(conn):
    add_user_stopword(conn, "  iya  ")
    assert list_user_stopwords(conn) == ["iya"]


def test_add_is_idempotent(conn):
    add_user_stopword(conn, "iya")
    add_user_stopword(conn, "iya")
    add_user_stopword(conn, "IYA")  # same after lowercasing
    assert list_user_stopwords(conn) == ["iya"]


def test_add_rejects_empty_after_strip(conn):
    with pytest.raises(ValueError):
        add_user_stopword(conn, "   ")
    with pytest.raises(ValueError):
        add_user_stopword(conn, "")


def test_add_truncates_to_50_chars(conn):
    long_word = "a" * 80
    add_user_stopword(conn, long_word)
    assert list_user_stopwords(conn) == ["a" * 50]


def test_remove(conn):
    add_user_stopword(conn, "iya")
    add_user_stopword(conn, "mantap")
    remove_user_stopword(conn, "iya")
    assert list_user_stopwords(conn) == ["mantap"]


def test_remove_missing_is_noop(conn):
    remove_user_stopword(conn, "does-not-exist")
    assert list_user_stopwords(conn) == []


def test_list_sorted_alphabetically(conn):
    for w in ["zeta", "alpha", "mu"]:
        add_user_stopword(conn, w)
    assert list_user_stopwords(conn) == ["alpha", "mu", "zeta"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_user_stopwords.py -v`
Expected: FAIL with `ImportError: cannot import name 'add_user_stopword'`.

- [ ] **Step 3: Implement `app/analysis/user_stopwords.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_user_stopwords.py -v`
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/analysis/user_stopwords.py tests/test_user_stopwords.py
git commit -m "Add user_stopwords CRUD overlay module"
```

---

### Task 3: Refactor `get_stopwords()` to overlay the user table

**Files:**
- Modify: `app/analysis/stopwords.py`
- Modify: `tests/test_stopwords.py`

The current `get_stopwords()` caches a single `set[str]` for the process. The new behavior queries `user_stopwords` on every call and unions it on top of the cached base. This intentionally breaks the existing `test_cached_across_calls` identity assertion (`sw1 is sw2`) — update it to value-equality instead.

- [ ] **Step 1: Update `tests/test_stopwords.py` — replace the identity test with a behavioral test**

Find the existing test:

```python
def test_cached_across_calls():
    """get_stopwords() must return the same object on repeated calls (cached)."""
    sw1 = get_stopwords()
    sw2 = get_stopwords()
    assert sw1 is sw2
```

Replace it with:

```python
def test_returns_equal_set_across_calls():
    """get_stopwords() returns a value-equal set on each call. Identity is
    not guaranteed because the user-stopwords overlay is recomposed per call."""
    sw1 = get_stopwords()
    sw2 = get_stopwords()
    assert sw1 == sw2
```

- [ ] **Step 2: Add a new failing test for the overlay**

Append to `tests/test_stopwords.py`:

```python
def test_user_stopwords_overlay_included(tmp_path, monkeypatch):
    """Words saved into user_stopwords appear in get_stopwords() output."""
    from app.analysis.stopwords import get_stopwords
    from app.analysis.user_stopwords import add_user_stopword
    from app.db import connect, run_migrations
    from app import config

    # Point settings.database_path at a tmp DB and pre-populate one word.
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config.settings, "database_path", db_path)
    conn = connect(db_path)
    try:
        run_migrations(conn)
        add_user_stopword(conn, "totallyuniqueword")
    finally:
        conn.close()

    sw = get_stopwords()
    assert "totallyuniqueword" in sw


def test_user_stopwords_overlay_lowercased(tmp_path, monkeypatch):
    """Case-mixed user stopword still excluded after lowercase normalisation."""
    from app.analysis.stopwords import get_stopwords
    from app.analysis.user_stopwords import add_user_stopword
    from app.db import connect, run_migrations
    from app import config

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config.settings, "database_path", db_path)
    conn = connect(db_path)
    try:
        run_migrations(conn)
        add_user_stopword(conn, "MixedCaseWord")
    finally:
        conn.close()

    sw = get_stopwords()
    assert "mixedcaseword" in sw
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_stopwords.py -v`
Expected: existing tests still pass; the two new overlay tests FAIL (overlay not yet implemented).

- [ ] **Step 4: Refactor `app/analysis/stopwords.py`**

Replace the module body with:

```python
"""
Stopword set for IG Pulse analysis modules.

Public API
----------
    get_stopwords() -> set[str]

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


def _load_user_overlay() -> set[str]:
    """Query user_stopwords table. Empty set on any failure (visible degradation)."""
    try:
        from app.db import connect
        from app.analysis.user_stopwords import list_user_stopwords

        conn = connect(settings.database_path)
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


def get_stopwords() -> set[str]:
    """Return the composed stopword set.

    Base set (Sastrawi + NLTK + custom file) is cached for the process lifetime.
    User overlay is re-queried on every call so UI changes are reflected
    immediately without cache invalidation logic.

    Returns
    -------
    set[str]
        Non-empty set; lowercase strings matching tokenize() output.
    """
    return get_base_stopwords() | _load_user_overlay()
```

- [ ] **Step 5: Run the full stopword test file**

Run: `pytest tests/test_stopwords.py -v`
Expected: all tests PASS, including the two new overlay tests.

- [ ] **Step 6: Commit**

```bash
git add app/analysis/stopwords.py tests/test_stopwords.py
git commit -m "Overlay user_stopwords table on top of base stopword set"
```

---

## Phase B — Analysis API (exclude_words + drill-down)

### Task 4: `word_frequencies()` gains `exclude_words` + backward-compat snapshot

**Files:**
- Modify: `app/analysis/wordfreq.py`
- Create: `tests/test_wordfreq_exclude.py`
- Create: `tests/snapshots/wordfreq_top100.json`

The backward-compat snapshot test locks in the existing algorithm output for a deterministic comment list. If anyone (us, or a future refactor) changes the algorithm by accident, this test fails loudly.

- [ ] **Step 1: Write the new failing test file `tests/test_wordfreq_exclude.py`**

```python
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
    accidental behaviour change."""
    result = word_frequencies(_fixture_comments(), 100)
    snapshot_path = Path(__file__).parent / "snapshots" / "wordfreq_top100.json"
    if not snapshot_path.exists():
        # First run: write the snapshot. Subsequent runs read & compare.
        snapshot_path.parent.mkdir(exist_ok=True)
        snapshot_path.write_text(
            json.dumps([list(t) for t in result], ensure_ascii=False, indent=2),
            encoding="utf-8",
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_wordfreq_exclude.py -v`
Expected: all tests FAIL (exclude_words parameter not yet supported by `word_frequencies`).

- [ ] **Step 3: Modify `app/analysis/wordfreq.py`**

Replace the body of `word_frequencies` (keep the module docstring as-is, but extend the function signature and docstring):

```python
def word_frequencies(
    comments: list[Comment],
    top_n: int = 100,
    exclude_words: set[str] | None = None,
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
    stopwords = get_stopwords()
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wordfreq_exclude.py -v`
Expected: all 5 tests PASS. The first run of `test_default_args_match_snapshot` creates the snapshot file at `tests/snapshots/wordfreq_top100.json` — re-run to confirm it now reads & compares.

```bash
pytest tests/test_wordfreq_exclude.py::test_default_args_match_snapshot -v
pytest tests/test_wordfreq_exclude.py::test_default_args_match_snapshot -v
```

- [ ] **Step 5: Run the existing wordfreq tests to confirm no regression**

Run: `pytest tests/test_wordfreq.py -v`
Expected: all existing tests still PASS (the new parameter is optional with default `None`).

- [ ] **Step 6: Commit**

```bash
git add app/analysis/wordfreq.py tests/test_wordfreq_exclude.py tests/snapshots/wordfreq_top100.json
git commit -m "Add exclude_words parameter to word_frequencies"
```

---

### Task 5: `comments_with_word()` helper

**Files:**
- Modify: `app/analysis/wordfreq.py`
- Create: `tests/test_wordfreq_comments_with_word.py`

- [ ] **Step 1: Write failing tests in `tests/test_wordfreq_comments_with_word.py`**

```python
"""Tests for app.analysis.wordfreq.comments_with_word — qualitative drill-down."""

from app.analysis.wordfreq import comments_with_word
from app.models import Comment

_NOW = "2024-01-01T00:00:00"


def _c(text: str, cid: str = "c1") -> Comment:
    return Comment(id=cid, post_id="p", text=text, timestamp=_NOW, fetched_at=_NOW)


def test_returns_only_matches():
    comments = [
        _c("nasi goreng enak", "c1"),
        _c("padang juga enak", "c2"),
        _c("wkwk", "c3"),
    ]
    out = comments_with_word(comments, "enak", n=10, seed=42)
    ids = {c.id for c in out}
    assert ids == {"c1", "c2"}


def test_match_is_token_equality_not_substring():
    """B3 evidence: 'promo' should NOT match 'promosi'."""
    comments = [
        _c("ada promo gak", "c1"),
        _c("promosi besar", "c2"),
    ]
    out = comments_with_word(comments, "promo", n=10, seed=42)
    assert {c.id for c in out} == {"c1"}


def test_match_case_insensitive():
    comments = [_c("Promo Besar PROMO", "c1")]
    out = comments_with_word(comments, "PROMO", n=10, seed=42)
    assert len(out) == 1


def test_emoji_word_matches_emoji_comment():
    """B3 compliance: emoji-only comments must be reachable from drill-down."""
    comments = [
        _c("😂😂😂", "c1"),
        _c("biasa aja", "c2"),
    ]
    out = comments_with_word(comments, "😂", n=10, seed=42)
    assert [c.id for c in out] == ["c1"]


def test_seed_makes_sample_deterministic():
    comments = [_c(f"nasi enak {i}", f"c{i}") for i in range(20)]
    a = comments_with_word(comments, "nasi", n=5, seed=42)
    b = comments_with_word(comments, "nasi", n=5, seed=42)
    assert [c.id for c in a] == [c.id for c in b]


def test_no_matches_returns_empty_list():
    comments = [_c("nasi goreng", "c1")]
    assert comments_with_word(comments, "doesnotexist", n=5, seed=42) == []


def test_n_caps_result_length():
    comments = [_c("nasi enak", f"c{i}") for i in range(20)]
    out = comments_with_word(comments, "nasi", n=3, seed=42)
    assert len(out) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_wordfreq_comments_with_word.py -v`
Expected: FAIL with `ImportError: cannot import name 'comments_with_word'`.

- [ ] **Step 3: Add `comments_with_word()` to `app/analysis/wordfreq.py`**

Append at the bottom of the module:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wordfreq_comments_with_word.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/analysis/wordfreq.py tests/test_wordfreq_comments_with_word.py
git commit -m "Add comments_with_word drill-down helper"
```

---

## Phase C — Routes

### Task 6: `/analysis/wordfreq` accepts `sentiment` and `exclude` params

**Files:**
- Modify: `app/routes/analysis.py`
- Create: `tests/test_routes_wordfreq.py`

This task only updates the route handler to ACCEPT and APPLY the new params. The template still renders as-is for now — we'll add the chip UI in Task 11. After this task, GET `/analysis/wordfreq?sentiment=negative&exclude=iya` works at the data layer but the page won't show chips yet.

- [ ] **Step 1: Write failing route tests in `tests/test_routes_wordfreq.py`**

```python
"""Integration tests for the wordfreq HTMX fragment route."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Test client with an isolated DB. Uses the existing auth bypass pattern
    if your test suite has one (mirror tests/test_routes.py setup)."""
    # NOTE: If tests/test_routes.py already exposes a conftest fixture for an
    # authenticated client, prefer that. Otherwise, build minimally here:
    return TestClient(app)


def _seed_comments_for_default_account(db_path, comments):
    """Helper to insert comments into the default test account's DB."""
    from app.db import connect, run_migrations, upsert_comment, upsert_post
    from app.models import Comment, Post

    conn = connect(db_path)
    try:
        run_migrations(conn)
        upsert_post(conn, Post(
            id="p1", caption=None, media_type="IMAGE", permalink="x",
            timestamp="2024-01-01T00:00:00", like_count=0,
            comment_count=len(comments), thumbnail_url=None,
            fetched_at="2024-01-01T00:00:00",
        ))
        for c in comments:
            upsert_comment(conn, c)
    finally:
        conn.close()


# These integration tests require the same auth/account scaffolding the
# existing test_routes.py uses. Follow that file's fixture pattern.
# The assertions below are what each test must verify.


def test_wordfreq_fragment_renders_without_filters(authed_client):
    r = authed_client.get("/analysis/wordfreq")
    assert r.status_code == 200
    assert "frekuensi" in r.text.lower() or "cloud-words" in r.text


def test_wordfreq_fragment_excludes_listed_word(authed_client, seeded_comments):
    # seeded_comments fixture has "nasi" appearing N times. Without exclude
    # it appears in the cloud; with ?exclude=nasi it must not.
    r = authed_client.get("/analysis/wordfreq?exclude=nasi")
    assert r.status_code == 200
    # Cloud word spans look like: <span class="cloud-word ...">nasi</span>
    assert '<span class="cloud-word' not in r.text or ">nasi<" not in r.text


def test_wordfreq_fragment_sentiment_filter_negative(authed_client, seeded_with_sentiment):
    """When sentiment=negative is set, only comments classified negative feed the cloud.
    Words that ONLY appear in positive comments must not appear in the cloud."""
    r = authed_client.get("/analysis/wordfreq?sentiment=negative")
    assert r.status_code == 200
    # The fixture seeds 'positiveword' only in positive comments; it must be absent.
    assert "positiveword" not in r.text


def test_wordfreq_fragment_multiple_exclude_params(authed_client, seeded_comments):
    r = authed_client.get("/analysis/wordfreq?exclude=iya&exclude=mantap")
    assert r.status_code == 200
    assert ">iya<" not in r.text
    assert ">mantap<" not in r.text
```

> **Pragmatic note for the implementer:** the `authed_client`, `seeded_comments`, and `seeded_with_sentiment` fixtures should mirror whatever pattern `tests/test_routes.py` already uses for the existing wordfreq smoke test. If those fixtures don't exist yet in `tests/conftest.py`, add minimal ones — but stay within the same conventions used elsewhere. If the existing test suite uses synthetic Comments in a shared conftest, do the same here. **Do not invent a new auth pattern just for these tests.**

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_wordfreq.py -v`
Expected: FAIL because (a) the route doesn't accept the new params yet, and (b) the new fixtures may not exist.

- [ ] **Step 3: Modify `wordfreq_fragment` in `app/routes/analysis.py`**

Locate the existing handler (around `app/routes/analysis.py:153`) and replace with:

```python
@router.get("/analysis/wordfreq", response_class=HTMLResponse)
def wordfreq_fragment(
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    try:
        comments, analyses = scope_data(
            account["db_path"], scope_type, scope_value,
            exclude_self=exclude_self, self_handle=account["username"],
        )
        # Sentiment filter (B4: still using the sentiment model — caveat
        # surfaces in the modal header at render time).
        if sentiment in ("positive", "neutral", "negative"):
            comments = [c for c in comments if analyses.get(c.id) == sentiment]
        elif sentiment != "all":
            # Unknown bucket value -> ignore, treat as "all". Don't 400; HTMX
            # users can land here via a stale URL.
            sentiment = "all"

        if not comments:
            return _empty(f"Tidak ada komentar pada cakupan ini.")

        exclude_words = {w.strip().lower()[:50] for w in exclude if w and w.strip()}
        freqs = wordfreq.word_frequencies(comments, 100, exclude_words=exclude_words or None)
        if not freqs:
            return _empty(
                "Semua kata teratas dikecualikan. Hapus chip di atas untuk melihat hasil."
                if exclude_words else
                "Tidak ada kata tersisa setelah penyaringan stopword."
            )

        cloud_words = []
        for i, (word, _count) in enumerate(freqs[:16]):
            cls = "s1" if i == 0 else "s2" if i < 4 else "s3" if i < 8 else "s4" if i < 12 else "s5"
            cloud_words.append({"word": word, "cls": cls})
        top_items = [{"rank": i + 1, "word": w, "count": c} for i, (w, c) in enumerate(freqs[:10])]

        logger.info(
            "wordfreq scope=%s/%s sentiment=%s excludes=%d results=%d",
            scope_type, scope_value, sentiment, len(exclude_words), len(freqs),
        )

        scope_qs = _scope_qs(scope_type, scope_value, exclude_self)
        return templates.TemplateResponse(request, "partials/frag_wordfreq.html", {
            "cloud_words": cloud_words,
            "top_items": top_items,
            "sentiment": sentiment,
            "excluded": sorted(exclude_words),
            "scope_qs": scope_qs,
        })
    except Exception:
        logger.exception("wordfreq fragment failed")
        return _error(str(request.url))
```

Add `Query` to the FastAPI imports at the top of the file:

```python
from fastapi import APIRouter, Query, Request
```

- [ ] **Step 4: Run the tests to verify the route behaves correctly**

Run: `pytest tests/test_routes_wordfreq.py -v`
Expected: route tests pass. Template-rendering details from Task 11 may still need to land before *every* assertion is fully meaningful — but data-layer behavior (cloud_words list contents) is correct now.

- [ ] **Step 5: Run the full test suite to catch regressions**

Run: `pytest tests/ -x -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/routes/analysis.py tests/test_routes_wordfreq.py
git commit -m "Accept sentiment and exclude params in /analysis/wordfreq"
```

---

### Task 7: `POST` and `DELETE` `/analysis/wordfreq/stopwords`

**Files:**
- Modify: `app/routes/analysis.py`
- Modify: `tests/test_routes_wordfreq.py`

- [ ] **Step 1: Add failing tests to `tests/test_routes_wordfreq.py`**

Append:

```python
import re

_WORD_RE = re.compile(r"^[\w☀-\U0001FAFF]+$")


def test_save_stopword_inserts_row_and_returns_fragment(authed_client, db_path):
    r = authed_client.post("/analysis/wordfreq/stopwords?word=iya")
    assert r.status_code == 200
    assert "cloud-words" in r.text or "frag_wordfreq" in r.text  # refreshed fragment

    # Verify it landed in DB
    from app.db import connect
    conn = connect(db_path)
    try:
        rows = list(conn.execute("SELECT word FROM user_stopwords"))
    finally:
        conn.close()
    assert ("iya",) in rows


def test_save_stopword_rejects_invalid_word(authed_client):
    r = authed_client.post("/analysis/wordfreq/stopwords?word=<script>")
    assert r.status_code == 400


def test_remove_saved_stopword(authed_client, db_path):
    authed_client.post("/analysis/wordfreq/stopwords?word=iya")
    r = authed_client.delete("/analysis/wordfreq/stopwords?word=iya")
    assert r.status_code == 200

    from app.db import connect
    conn = connect(db_path)
    try:
        rows = list(conn.execute("SELECT word FROM user_stopwords"))
    finally:
        conn.close()
    assert rows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_wordfreq.py -v -k stopword`
Expected: FAIL (404 — endpoints don't exist).

- [ ] **Step 3: Add the endpoints to `app/routes/analysis.py`**

Add this constant near the top (with `_BUCKETS`):

```python
# Whitelist: word characters + the emoji ranges tokenize() recognises.
_WORD_PARAM_RE = re.compile(
    r"^["
    r"\w"
    r"⌀-⏿"
    r"☀-➿"
    r"⬀-⯿"
    r"\U0001F300-\U0001FAFF"
    r"\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FAFF"
    r"]+$"
)
```

Add `import re` at the top if not already present.

Then add the endpoints (place after `wordfreq_fragment`):

```python
@router.post("/analysis/wordfreq/stopwords", response_class=HTMLResponse)
def save_user_stopword(
    request: Request,
    word: str,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    """Add *word* to the per-user stopword overlay, then re-render the wordfreq
    fragment so the saved word disappears from the cloud immediately."""
    normalised = word.strip().lower()[:50]
    if not normalised or not _WORD_PARAM_RE.match(normalised):
        return HTMLResponse(
            "<div class='error'>Kata tidak valid.</div>", status_code=400,
        )

    from app.analysis.user_stopwords import add_user_stopword
    conn = connect(account["db_path"])
    try:
        add_user_stopword(conn, normalised)
    finally:
        conn.close()

    logger.info("user_stopword saved: %s", normalised)
    return wordfreq_fragment(
        request,
        scope_type=scope_type, scope_value=scope_value,
        exclude_self=exclude_self, sentiment=sentiment,
        exclude=exclude, account=account,
    )


@router.delete("/analysis/wordfreq/stopwords", response_class=HTMLResponse)
def remove_user_stopword_route(
    request: Request,
    word: str,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    """Remove *word* from the per-user stopword overlay."""
    normalised = word.strip().lower()[:50]
    if not normalised or not _WORD_PARAM_RE.match(normalised):
        return HTMLResponse(
            "<div class='error'>Kata tidak valid.</div>", status_code=400,
        )

    from app.analysis.user_stopwords import remove_user_stopword
    conn = connect(account["db_path"])
    try:
        remove_user_stopword(conn, normalised)
    finally:
        conn.close()

    logger.info("user_stopword removed: %s", normalised)
    return wordfreq_fragment(
        request,
        scope_type=scope_type, scope_value=scope_value,
        exclude_self=exclude_self, sentiment=sentiment,
        exclude=exclude, account=account,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_wordfreq.py -v -k stopword`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/analysis.py tests/test_routes_wordfreq.py
git commit -m "Add save and remove endpoints for user stopwords"
```

---

### Task 8: `GET /analysis/wordfreq/sample` (drill-down modal endpoint)

**Files:**
- Modify: `app/routes/analysis.py`
- Modify: `tests/test_routes_wordfreq.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_routes_wordfreq.py`:

```python
def test_sample_modal_returns_html(authed_client, seeded_comments):
    r = authed_client.get("/analysis/wordfreq/sample?word=nasi&n=5")
    assert r.status_code == 200
    # Renders the partial (we'll create it in Task 12 — for now just assert HTML)
    assert "modal" in r.text.lower() or "sampel" in r.text.lower()


def test_sample_modal_filters_by_sentiment(authed_client, seeded_with_sentiment):
    r = authed_client.get("/analysis/wordfreq/sample?word=nasi&sentiment=negative&n=10")
    assert r.status_code == 200
    # All comments returned should be from the negative bucket; the fixture
    # marks negative-bucket comments with the substring "NEG_MARKER".
    # If your seed strategy differs, adjust accordingly.


def test_sample_modal_rejects_invalid_word(authed_client):
    r = authed_client.get("/analysis/wordfreq/sample?word=<script>")
    assert r.status_code == 400


def test_sample_modal_empty_for_no_match(authed_client, seeded_comments):
    r = authed_client.get("/analysis/wordfreq/sample?word=doesnotexist")
    assert r.status_code == 200
    assert "tidak ada komentar" in r.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes_wordfreq.py -v -k sample`
Expected: FAIL (404).

- [ ] **Step 3: Add the endpoint to `app/routes/analysis.py`**

```python
@router.get("/analysis/wordfreq/sample", response_class=HTMLResponse)
def wordfreq_sample(
    request: Request,
    word: str,
    n: int = 5,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    account=auth.current_account,
):
    """Drill-down: return a modal listing up to *n* random comments containing
    *word*, respecting the current scope and sentiment filter.

    Mirrors the sentiment sample modal pattern (B4-style "see the evidence").
    """
    normalised = word.strip().lower()[:50]
    if not normalised or not _WORD_PARAM_RE.match(normalised):
        return HTMLResponse(
            "<div class='error'>Kata tidak valid.</div>", status_code=400,
        )

    comments, analyses = scope_data(
        account["db_path"], scope_type, scope_value,
        exclude_self=exclude_self, self_handle=account["username"],
    )
    if sentiment in ("positive", "neutral", "negative"):
        comments = [c for c in comments if analyses.get(c.id) == sentiment]

    samples = wordfreq.comments_with_word(comments, normalised, n=n)
    total = sum(1 for c in comments if normalised in set(tokenize(c.text)))

    # Look up post titles for the "Dari: …" link in each card.
    post_titles: dict[str, dict[str, str]] = {}
    conn = connect(account["db_path"])
    try:
        for row in conn.execute("SELECT id, caption, permalink FROM posts"):
            post_titles[row["id"]] = {
                "title": (row["caption"] or "Tanpa caption")[:60],
                "link": row["permalink"],
            }
    finally:
        conn.close()

    view_samples = [
        {
            "handle": c.author_handle or "anon",
            "when": _id_datetime(c.timestamp),
            "text": c.text,
            "post_title": post_titles.get(c.post_id, {}).get("title", "Post"),
            "post_link": post_titles.get(c.post_id, {}).get("link"),
        }
        for c in samples
    ]

    scope_qs = _scope_qs(scope_type, scope_value, exclude_self)
    logger.info(
        "wordfreq sample word=%s sentiment=%s matches=%d returned=%d",
        normalised, sentiment, total, len(view_samples),
    )
    return templates.TemplateResponse(request, "partials/_wordfreq_sample.html", {
        "word": normalised,
        "samples": view_samples,
        "total": total,
        "n": n,
        "sentiment": sentiment,
        "scope_qs": scope_qs,
    })
```

Add to imports at the top of `app/routes/analysis.py` if not already present:

```python
from app.analysis.tokenize import tokenize
```

- [ ] **Step 4: Note that the partial template `_wordfreq_sample.html` will be created in Task 12.**

For now the route will return a 500 in production until the template exists. The test in Step 1 expects 200; that test will pass once Task 12 lands. **Mark this test as `@pytest.mark.skip("template added in Task 12")` for the moment** and unskip in Task 12.

Update the tests:

```python
@pytest.mark.skip(reason="template added in Task 12")
def test_sample_modal_returns_html(...): ...

@pytest.mark.skip(reason="template added in Task 12")
def test_sample_modal_filters_by_sentiment(...): ...

@pytest.mark.skip(reason="template added in Task 12")
def test_sample_modal_empty_for_no_match(...): ...
```

The `test_sample_modal_rejects_invalid_word` test does NOT need the template (it returns 400 before rendering) — leave it unskipped.

- [ ] **Step 5: Run unskipped test to verify it passes**

Run: `pytest tests/test_routes_wordfreq.py::test_sample_modal_rejects_invalid_word -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routes/analysis.py tests/test_routes_wordfreq.py
git commit -m "Add wordfreq drill-down sample endpoint"
```

---

### Task 9: `GET /analysis/wordfreq/filtered` (transparency panel)

**Files:**
- Modify: `app/routes/analysis.py`
- Modify: `tests/test_routes_wordfreq.py`

- [ ] **Step 1: Add failing test**

Append:

```python
@pytest.mark.skip(reason="template added in Task 13")
def test_filtered_panel_lists_saved_stopwords(authed_client, db_path):
    authed_client.post("/analysis/wordfreq/stopwords?word=iya")
    r = authed_client.get("/analysis/wordfreq/filtered")
    assert r.status_code == 200
    assert "iya" in r.text


def test_filtered_panel_endpoint_exists(authed_client):
    r = authed_client.get("/analysis/wordfreq/filtered")
    # Even without the template, the endpoint should be registered (not 404).
    # 500 (template missing) is acceptable here; we just want to confirm routing.
    assert r.status_code != 404
```

- [ ] **Step 2: Run to verify it fails (404)**

Run: `pytest tests/test_routes_wordfreq.py::test_filtered_panel_endpoint_exists -v`
Expected: FAIL with 404.

- [ ] **Step 3: Add the endpoint to `app/routes/analysis.py`**

```python
@router.get("/analysis/wordfreq/filtered", response_class=HTMLResponse)
def wordfreq_filtered(
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    """Transparency panel: list of words currently being filtered.

    Two groups: user-saved (with × buttons) and built-in (read-only).
    Each entry shows what its count *would have been* on the current scope,
    so the user can sanity-check that nothing important is being hidden (B3).
    """
    from app.analysis.user_stopwords import list_user_stopwords
    from app.analysis.stopwords import get_base_stopwords

    conn = connect(account["db_path"])
    try:
        user_words = list_user_stopwords(conn)
    finally:
        conn.close()
    base_words = sorted(get_base_stopwords())

    # Build hidden-counts for both groups against the current scope.
    comments, analyses = scope_data(
        account["db_path"], scope_type, scope_value,
        exclude_self=exclude_self, self_handle=account["username"],
    )
    if sentiment in ("positive", "neutral", "negative"):
        comments = [c for c in comments if analyses.get(c.id) == sentiment]

    counts: Counter = Counter()
    for c in comments:
        counts.update(tokenize(c.text))

    user_entries = [{"word": w, "count": counts.get(w, 0)} for w in user_words]
    # Cap the built-in list to the 50 highest hidden counts to keep the
    # panel readable.
    base_entries = sorted(
        ({"word": w, "count": counts.get(w, 0)} for w in base_words),
        key=lambda e: -e["count"],
    )[:50]

    scope_qs = _scope_qs(scope_type, scope_value, exclude_self)
    return templates.TemplateResponse(request, "partials/_wordfreq_filtered.html", {
        "user_entries": user_entries,
        "base_entries": base_entries,
        "sentiment": sentiment,
        "excluded": sorted({w.strip().lower()[:50] for w in exclude if w and w.strip()}),
        "scope_qs": scope_qs,
    })
```

- [ ] **Step 4: Run test to verify endpoint exists**

Run: `pytest tests/test_routes_wordfreq.py::test_filtered_panel_endpoint_exists -v`
Expected: PASS (status != 404; may be 500 until the template lands in Task 13, which is fine).

- [ ] **Step 5: Commit**

```bash
git add app/routes/analysis.py tests/test_routes_wordfreq.py
git commit -m "Add wordfreq filtered/transparency panel endpoint"
```

---

### Task 10: `/export/wordfreq` passthrough for filter params

**Files:**
- Modify: `app/routes/export.py`
- Create: `tests/test_export_wordfreq_filters.py`

- [ ] **Step 1: Read the existing `/export/wordfreq` handler to see its current shape**

Run: `sed -n '60,100p' app/routes/export.py`

You'll see it currently calls `wordfreq.word_frequencies(comments, 100)` without filter args (line ~81). It does not accept `sentiment` or `exclude` query params.

- [ ] **Step 2: Write failing test in `tests/test_export_wordfreq_filters.py`**

```python
"""Verify /export/wordfreq passes filter params through (B8: export must
reflect what the user is viewing)."""

from unittest.mock import patch


def test_export_wordfreq_passes_exclude_to_word_frequencies(authed_client, seeded_comments):
    with patch(
        "app.routes.export.wordfreq.word_frequencies",
        wraps=__import__("app.analysis.wordfreq", fromlist=["word_frequencies"]).word_frequencies,
    ) as spy:
        r = authed_client.get("/export/wordfreq?exclude=iya&exclude=mantap&sentiment=all")
        assert r.status_code in (200, 503)  # 503 if kaleido / wordcloud missing on test env
        # Confirm wordfreq.word_frequencies received the exclude set
        called_kwargs = spy.call_args.kwargs
        called_args = spy.call_args.args
        ex = called_kwargs.get("exclude_words") or (called_args[2] if len(called_args) > 2 else None)
        assert ex is not None and {"iya", "mantap"}.issubset(ex)


def test_export_wordfreq_sentiment_filter_narrows_comment_set(authed_client, seeded_with_sentiment):
    """When sentiment=negative is passed, the export only sees negative comments."""
    with patch(
        "app.routes.export.wordfreq.word_frequencies",
    ) as spy:
        spy.return_value = []  # short-circuit; we only care about input
        r = authed_client.get("/export/wordfreq?sentiment=negative")
        assert r.status_code in (200, 503)
        comments_passed = spy.call_args.args[0]
        # Every comment in the call must be from the negative bucket
        # (verify via your fixture's marker).
        assert all("NEG_MARKER" in c.text for c in comments_passed)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_export_wordfreq_filters.py -v`
Expected: FAIL (route doesn't accept the new params).

- [ ] **Step 4: Modify `/export/wordfreq` in `app/routes/export.py`**

Locate the chart-routing block (around line 80) and the function signature above it. Extend the signature to accept the new params, then thread them through:

```python
@router.get("/export/{chart_name}")
def export_chart(
    chart_name: str,
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    ...
    if chart_name == "wordfreq":
        if sentiment in ("positive", "neutral", "negative"):
            comments = [c for c in comments if analyses.get(c.id) == sentiment]
        exclude_words = {w.strip().lower()[:50] for w in exclude if w and w.strip()}
        freqs = wordfreq.word_frequencies(comments, 100, exclude_words=exclude_words or None)
        img = wc_render.render_wordcloud(freqs)
        ...
```

Read the actual file before editing — adapt the surrounding code (footer caption, image return) to match its real structure. Add `Query` to the imports if it isn't there already.

Add a footer caption to the rendered PNG (spec section 6 requires this): *"Sentimen: Negatif · 14 kata dikecualikan"* — only emitted when `sentiment != "all"` or `exclude_words` is non-empty.

First inspect `app/render/wordcloud.py` (or wherever `wc_render.render_wordcloud` lives):

```bash
grep -rn "def render_wordcloud" app/
```

If the function does not accept a `footer_caption: str | None = None` parameter, extend it as part of this task:

1. Add the parameter with default `None`.
2. When set, render the caption text as a thin band along the bottom of the PNG (PIL `ImageDraw.text` with the existing font; ~24px high). Match existing visual style.
3. Add a unit test `tests/test_wordcloud.py::test_render_with_footer_caption` that asserts the returned image is N pixels taller than without the caption.

This is a narrow, on-scope extension required by B8 — not feature creep.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_export_wordfreq_filters.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routes/export.py tests/test_export_wordfreq_filters.py
git commit -m "Thread filter params through /export/wordfreq (B8)"
```

---

## Phase D — Templates

### Task 11: Update `frag_wordfreq.html` (sentiment control + chips + clickable words)

**Files:**
- Modify: `app/templates/partials/frag_wordfreq.html`

There is no automated test for HTML structure beyond the integration assertions in Task 6. Validate this task by:

1. Visual inspection in the running app (Step 5).
2. The Task 6 route tests still pass (no template-context errors).

- [ ] **Step 1: Read the current template**

Run: `cat app/templates/partials/frag_wordfreq.html`

You'll see it currently expects `cloud_words` and `top_items` only.

- [ ] **Step 2: Replace with the new template**

Write `app/templates/partials/frag_wordfreq.html`:

```jinja
{# Word frequency card body.
   Context: cloud_words, top_items, sentiment ('all'|'positive'|'neutral'|'negative'),
            excluded (list[str], alphabetically sorted), scope_qs (string). #}

{% set base_qs = scope_qs %}
{% set excl_qs = excluded | map('urlencode') | map('string') | list %}
{% set excl_param = excl_qs | map('regex_replace', '^(.+)$', 'exclude=\\1') | join('&') if excl_qs else '' %}

<div id="wordfreq-card" class="wordfreq-card">
  <div class="wf-controls">
    <div class="wf-sentiment-filter" role="tablist" aria-label="Saring komentar berdasarkan sentimen">
      {% for key, label in [('all','Semua'), ('positive','😊 Positif'), ('neutral','😐 Netral'), ('negative','😡 Negatif')] %}
        <a class="wf-pill {{ 'active' if sentiment == key }}"
           hx-get="/analysis/wordfreq?{{ base_qs }}&sentiment={{ key }}{% if excl_param %}&{{ excl_param }}{% endif %}"
           hx-target="#wordfreq-card"
           hx-swap="outerHTML"
           href="#" role="tab" aria-selected="{{ 'true' if sentiment == key else 'false' }}">{{ label }}</a>
      {% endfor %}
    </div>

    <div class="wf-chips">
      <span class="wf-chips-label">Dikecualikan:</span>
      {% for w in excluded %}
        {% set other_excl = excluded | reject('equalto', w) | list %}
        {% set other_param = other_excl | map('urlencode') | map('string') | map('regex_replace', '^(.+)$', 'exclude=\\1') | join('&') %}
        <span class="wf-chip">
          {{ w }}
          <button type="button" title="Hapus pengecualian"
                  hx-get="/analysis/wordfreq?{{ base_qs }}&sentiment={{ sentiment }}{% if other_param %}&{{ other_param }}{% endif %}"
                  hx-target="#wordfreq-card" hx-swap="outerHTML">×</button>
          <button type="button" title="Simpan sebagai stopword permanen"
                  hx-post="/analysis/wordfreq/stopwords?word={{ w | urlencode }}&{{ base_qs }}&sentiment={{ sentiment }}{% if other_param %}&{{ other_param }}{% endif %}"
                  hx-target="#wordfreq-card" hx-swap="outerHTML">💾</button>
        </span>
      {% endfor %}
      <input class="wf-chip-input" type="text" placeholder="+ tambah pengecualian…"
             hx-get="/analysis/wordfreq?{{ base_qs }}&sentiment={{ sentiment }}{% if excl_param %}&{{ excl_param }}{% endif %}&exclude=__VALUE__"
             hx-trigger="keyup[key=='Enter'] changed"
             hx-target="#wordfreq-card" hx-swap="outerHTML"
             hx-vals='js:{exclude: event.target.value}'/>
    </div>

    <a class="wf-filtered-link" href="#"
       hx-get="/analysis/wordfreq/filtered?{{ base_qs }}&sentiment={{ sentiment }}{% if excl_param %}&{{ excl_param }}{% endif %}"
       hx-target="#wordfreq-filtered-slot" hx-swap="innerHTML">▸ Lihat kata yang tersembunyi</a>
    <div id="wordfreq-filtered-slot"></div>
  </div>

  <div class="cloud-body">
    <div class="cloud-words">
      {% for w in cloud_words %}
        <a class="cloud-word {{ w.cls }}" href="#"
           hx-get="/analysis/wordfreq/sample?word={{ w.word | urlencode }}&n=5&{{ base_qs }}&sentiment={{ sentiment }}"
           hx-target="#modal-root" hx-swap="innerHTML">{{ w.word }}</a>
      {% endfor %}
    </div>
    <div class="top-list">
      <div class="top-list-title">Top {{ top_items | length }}</div>
      {% for it in top_items %}
      <a class="top-item" href="#"
         hx-get="/analysis/wordfreq/sample?word={{ it.word | urlencode }}&n=5&{{ base_qs }}&sentiment={{ sentiment }}"
         hx-target="#modal-root" hx-swap="innerHTML">
        <span class="rank">{{ "%02d" | format(it.rank) }}</span>
        <span class="word">{{ it.word }}</span>
        <span class="count">{{ "{:,}".format(it.count) }}</span>
      </a>
      {% endfor %}
    </div>
  </div>
</div>
```

> **Jinja note:** the `urlencode` and `regex_replace` filters are standard Jinja2 extensions. If `regex_replace` is not available in this codebase's Jinja setup, replace the `excl_param` construction with a small `{% for %}` loop concatenating `exclude=<value>&` parts manually. Verify by checking `app/templating.py`.

- [ ] **Step 3: Add minimal CSS for the new elements**

This template references `.wf-controls`, `.wf-sentiment-filter`, `.wf-pill`, `.wf-chips`, `.wf-chip`, `.wf-chip-input`, `.wf-filtered-link`. Open `app/static/css/<the main stylesheet>` and add styles. Match the existing visual language (font sizes, spacing, dark/light modes). If unsure where to add styles, grep for `.cloud-word` to find the stylesheet currently styling the wordfreq card and append nearby.

```bash
grep -rn ".cloud-word" app/static/
```

Minimal additions (refine to taste):

```css
.wf-controls { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.wf-sentiment-filter { display: flex; gap: 6px; }
.wf-pill { padding: 4px 10px; border-radius: 999px; border: 1px solid var(--border, #ccc);
           font-size: 0.85em; text-decoration: none; color: inherit; }
.wf-pill.active { background: var(--accent, #333); color: #fff; }
.wf-chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 0.85em; }
.wf-chips-label { opacity: 0.6; }
.wf-chip { display: inline-flex; gap: 4px; align-items: center;
           padding: 2px 6px; border-radius: 4px; background: var(--surface-2, #eee); }
.wf-chip button { background: none; border: none; cursor: pointer; padding: 0 2px; }
.wf-chip-input { flex: 1; min-width: 140px; padding: 4px 8px; font-size: 0.85em;
                  border: 1px dashed var(--border, #ccc); background: transparent; }
.wf-filtered-link { font-size: 0.8em; opacity: 0.7; text-decoration: none; }
.wf-filtered-link:hover { opacity: 1; }
```

- [ ] **Step 4: Run the wordfreq integration tests to confirm template context contract**

Run: `pytest tests/test_routes_wordfreq.py -v`
Expected: tests not skipped pass; assertions about `cloud-word` HTML survive.

- [ ] **Step 5: Manual smoke check**

Start the dev server: `uv run uvicorn app.main:app --reload`. Open the dashboard, navigate to a scope with comments, click around: sentiment pills should swap the cloud; clicking a chip × removes it; typing a word in "tambah pengecualian" and pressing Enter adds a chip. Note any visual issues; do not regress existing styling.

- [ ] **Step 6: Commit**

```bash
git add app/templates/partials/frag_wordfreq.html app/static/
git commit -m "Add chips, sentiment filter, and clickable words to wordfreq fragment"
```

---

### Task 12: Create `_wordfreq_sample.html` (drill-down modal)

**Files:**
- Create: `app/templates/partials/_wordfreq_sample.html`
- Modify: `tests/test_routes_wordfreq.py` (unskip Task 8 tests)

- [ ] **Step 1: Inspect the existing sentiment sample modal for pattern reuse**

Run: `cat app/templates/partials/_sample_modal.html`

The new template is structurally identical with three differences: header copy, an additional "exclude this word" footer button, and a conditional B4 disclaimer.

- [ ] **Step 2: Write `app/templates/partials/_wordfreq_sample.html`**

```jinja
{# Wordfreq drill-down modal — qualitative evidence behind a frequency count.
   Context: word, samples (list of {handle, when, text, post_title, post_link}),
            total (int), n (int), sentiment (str), scope_qs (str). #}
<div class="modal-overlay" onclick="if(event.target===this)this.remove()">
  <div class="modal" role="dialog" aria-labelledby="wf-sample-title">
    <header class="modal-header">
      <div class="modal-header-meta">
        <div class="modal-eyebrow">Sampel komentar mengandung <strong>"{{ word }}"</strong></div>
        <h3 class="modal-title" id="wf-sample-title">
          {{ samples | length }} dari {{ "{:,}".format(total) }} komentar
        </h3>
        <div class="modal-sub">
          Lihat komentar asli untuk paham kenapa kata ini sering muncul.
          {% if sentiment != 'all' %}
            <em>Filter sentimen: {{ {'positive':'Positif','neutral':'Netral','negative':'Negatif'}[sentiment] }}.
            Model bisa salah — ini sampel untuk dicek manual.</em>
          {% endif %}
        </div>
      </div>
      <button class="modal-close" type="button" aria-label="Tutup"
              onclick="this.closest('.modal-overlay').remove()">×</button>
    </header>

    <div class="modal-body">
      {% if samples %}
        {% for c in samples %}
        <div class="comment">
          <div class="comment-meta">
            <span class="comment-handle">@{{ c.handle }}</span>
            <span class="comment-sep">·</span>
            <span>{{ c.when }}</span>
          </div>
          <p class="comment-text">{{ c.text }}</p>
          <div class="comment-footer">
            <span class="comment-context">
              {% if c.post_link %}<a href="{{ c.post_link }}" target="_blank" rel="noopener">Dari: {{ c.post_title }} ↗</a>
              {% else %}Dari: {{ c.post_title }}{% endif %}
            </span>
          </div>
        </div>
        {% endfor %}
      {% else %}
        <p style="opacity:0.6;padding:24px 0;">
          Tidak ada komentar yang mengandung kata ini pada filter saat ini.
          {% if sentiment != 'all' %}Coba hapus filter sentimen.{% endif %}
        </p>
      {% endif %}
    </div>

    <footer class="modal-footer">
      <div class="modal-footer-meta">{{ samples | length }} dari {{ "{:,}".format(total) }} · sampel acak</div>
      <div class="modal-footer-actions">
        {% if total > samples | length %}
          <button class="btn-more" type="button"
                  hx-get="/analysis/wordfreq/sample?word={{ word | urlencode }}&n={{ n }}&{{ scope_qs }}&sentiment={{ sentiment }}"
                  hx-target="#modal-root" hx-swap="innerHTML">↻ Ambil ulang</button>
          <button class="btn-more" type="button"
                  hx-get="/analysis/wordfreq/sample?word={{ word | urlencode }}&n={{ n + 5 }}&{{ scope_qs }}&sentiment={{ sentiment }}"
                  hx-target="#modal-root" hx-swap="innerHTML">Tampilkan 5 lagi</button>
        {% endif %}
        <button class="btn-more" type="button"
                hx-get="/analysis/wordfreq?{{ scope_qs }}&sentiment={{ sentiment }}&exclude={{ word | urlencode }}"
                hx-target="#wordfreq-card" hx-swap="outerHTML"
                onclick="document.querySelector('.modal-overlay').remove()">
          Kecualikan kata ini
        </button>
      </div>
    </footer>
  </div>
</div>
<script>
  (function () {
    function esc(e) { if (e.key === 'Escape') { var o = document.querySelector('.modal-overlay'); if (o) o.remove(); document.removeEventListener('keydown', esc); } }
    document.addEventListener('keydown', esc);
  })();
</script>
```

- [ ] **Step 3: Unskip the Task 8 tests in `tests/test_routes_wordfreq.py`**

Remove the three `@pytest.mark.skip(reason="template added in Task 12")` decorators added in Task 8.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes_wordfreq.py -v -k sample`
Expected: all sample tests PASS.

- [ ] **Step 5: Manual smoke check**

Server should be running from Task 11 Step 5. Click any word in the cloud → modal opens with sample comments. Click "Kecualikan kata ini" → modal closes and that word disappears from the cloud (chip appears).

- [ ] **Step 6: Commit**

```bash
git add app/templates/partials/_wordfreq_sample.html tests/test_routes_wordfreq.py
git commit -m "Add wordfreq drill-down sample modal template"
```

---

### Task 13: Create `_wordfreq_filtered.html` (transparency panel)

**Files:**
- Create: `app/templates/partials/_wordfreq_filtered.html`
- Modify: `tests/test_routes_wordfreq.py` (unskip Task 9 test)

- [ ] **Step 1: Write `app/templates/partials/_wordfreq_filtered.html`**

```jinja
{# Wordfreq "what's filtered" panel — transparency over silent dropping (B3).
   Context: user_entries (list of {word, count}), base_entries (list of {word, count}),
            sentiment (str), excluded (list[str]), scope_qs (str). #}
<div class="wf-filtered-panel">
  <section>
    <h4>Kata yang kamu simpan ({{ user_entries | length }})</h4>
    {% if user_entries %}
      <ul class="wf-filtered-list">
        {% for e in user_entries %}
        <li>
          <span class="wf-filtered-word">{{ e.word }}</span>
          <span class="wf-filtered-count">{{ e.count }}×</span>
          <button type="button" class="wf-remove" title="Hapus dari stopword tersimpan"
                  hx-delete="/analysis/wordfreq/stopwords?word={{ e.word | urlencode }}&{{ scope_qs }}&sentiment={{ sentiment }}"
                  hx-target="#wordfreq-card" hx-swap="outerHTML">×</button>
        </li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="wf-empty">Belum ada kata yang kamu simpan.</p>
    {% endif %}
  </section>

  <section>
    <h4>Stopword bawaan (top 50 by hidden count)</h4>
    <p class="wf-explainer">Daftar baca-saja dari Sastrawi, NLTK, dan stopwords_custom.txt.</p>
    <ul class="wf-filtered-list">
      {% for e in base_entries %}
      <li>
        <span class="wf-filtered-word">{{ e.word }}</span>
        <span class="wf-filtered-count">{{ e.count }}×</span>
      </li>
      {% endfor %}
    </ul>
  </section>
</div>
```

Add CSS in the same stylesheet as Task 11:

```css
.wf-filtered-panel { margin-top: 10px; padding: 10px; border: 1px dashed var(--border, #ccc);
                      border-radius: 6px; font-size: 0.85em; }
.wf-filtered-panel h4 { margin: 6px 0; font-size: 1em; }
.wf-filtered-list { list-style: none; padding: 0; margin: 0;
                     display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 4px; }
.wf-filtered-list li { display: flex; gap: 6px; align-items: center; }
.wf-filtered-word { font-family: monospace; }
.wf-filtered-count { opacity: 0.5; font-size: 0.9em; }
.wf-remove { background: none; border: none; cursor: pointer; padding: 0 2px; }
.wf-explainer { opacity: 0.6; margin: 0 0 6px 0; }
.wf-empty { opacity: 0.6; }
```

- [ ] **Step 2: Unskip the Task 9 saved-stopword test**

In `tests/test_routes_wordfreq.py`, remove `@pytest.mark.skip(reason="template added in Task 13")` from `test_filtered_panel_lists_saved_stopwords`.

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_routes_wordfreq.py -v -k filtered`
Expected: PASS.

- [ ] **Step 4: Manual smoke check**

In the running dashboard, click "▸ Lihat kata yang tersembunyi" link → panel expands showing two lists. Add a stopword via the save button on a chip → reload the panel → the word appears in the "Kata yang kamu simpan" section. Click × on it → it disappears.

- [ ] **Step 5: Commit**

```bash
git add app/templates/partials/_wordfreq_filtered.html app/static/ tests/test_routes_wordfreq.py
git commit -m "Add wordfreq filtered/transparency panel template"
```

---

## Phase E — Verification

### Task 14: End-to-end smoke + full test suite

**Files:**
- No new code. Verification only.

- [ ] **Step 1: Run the entire test suite cleanly**

Run: `pytest tests/ -q`
Expected: all tests pass, no skipped tests other than any that were already pre-existingly skipped.

- [ ] **Step 2: Boot the dev server and walk the feature**

Run: `uv run uvicorn app.main:app --reload`

Walk through each behavior:

1. Navigate to dashboard, locate wordfreq card.
2. Confirm the sentiment segmented control is visible; clicking Positif/Netral/Negatif refreshes the cloud.
3. Click any word — modal opens with sample comments.
4. Inside the modal, click "Kecualikan kata ini" — modal closes, chip appears, word gone from cloud.
5. Type a word into "+ tambah pengecualian" → press Enter → chip appears.
6. On a chip, click 💾 → chip vanishes, but the word stays filtered (proves it's now in user_stopwords).
7. Click "▸ Lihat kata yang tersembunyi" → panel opens, the just-saved word appears under "Kata yang kamu simpan".
8. Click × on that entry → word un-saves; if you remove the URL `exclude=…`, the word reappears in the cloud.
9. Switch sentiment to Negatif → click a word → confirm modal shows only negative comments and the B4 caveat appears in the modal sub-header.
10. Confirm the page-level "Export PNG" for wordfreq reflects the current filters (sentiment + chips).

- [ ] **Step 3: Check logs for any warning/error noise**

Run: `tail -200 logs/ig_pulse.log`
Expected: each new route logs a structured INFO line (`wordfreq scope=… sentiment=… excludes=N results=N`, `wordfreq sample word=… …`, `user_stopword saved: …`). No tokens, no comment text. No tracebacks.

- [ ] **Step 4: Verify backward-compat snapshot one more time**

Run: `pytest tests/test_wordfreq_exclude.py::test_default_args_match_snapshot -v`
Expected: PASS — the default-args output still matches the locked-in snapshot.

- [ ] **Step 5: Final commit if any small follow-ups were needed**

```bash
git status
# If any tweaks were made during smoke, commit them with a "Polish wordfreq enhancement" message.
```

- [ ] **Step 6: Mark spec implementation complete**

Update the spec's status header from "approved by user; ready for implementation plan" to "implemented" and commit.

```bash
git add docs/superpowers/specs/2026-05-28-wordfreq-enhancement-design.md
git commit -m "Mark wordfreq enhancement spec as implemented"
```

---

## Notes for the implementer

- **TDD strictness:** every code task starts with a failing test. Do not skip Step 2 ("run to verify fail") — it catches the case where the test file has a syntax error and is silently being skipped.
- **DRY:** the duplicate `_WORD_PARAM_RE` validation lives in three route handlers (Task 7 save, Task 7 delete, Task 8 sample). After all three land, you may extract it to a small helper `_validate_word_param(word) -> str` in `app/routes/analysis.py` and call it from each — but only after all three are working, to avoid coupling task progress.
- **YAGNI:** do not add `created_by` columns, audit logging, or undo/redo on the stopword table. The spec explicitly keeps this single-user MVP.
- **Frequent commits:** each task ends with a commit. Resist the urge to batch.
- **Test fixtures:** if the existing `tests/conftest.py` doesn't provide `authed_client`, `seeded_comments`, `seeded_with_sentiment`, and `db_path`, add minimal ones matching the patterns used in the existing route tests (`tests/test_routes.py`, `tests/test_export.py`). Don't invent novel auth or seeding patterns.
- **Browser verification:** Tasks 11–13 require visual checks. If the dev server can't run in your environment, say so explicitly — don't claim the UI is correct without seeing it.
- **CLAUDE.md rules touched:** B1 (no scope creep), B3 (no silent text drops, transparency panel surfaces the hidden), B4 (sentiment caveat conditional in drill-down modal), B5 (additive migration, never DROP), B6 (HTMX-only), B8 (export reflects filters), B9 (all UI copy in Bahasa Indonesia), B10 (real fixtures preferred, synthetic accepted for unit tests matching existing style), B11 (structured logs, no text, no tokens).
