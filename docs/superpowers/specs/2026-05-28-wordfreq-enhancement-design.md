# Word Frequency Enhancement — Design Spec

**Date:** 2026-05-28
**Author:** brainstormed with Claude (explanatory mode)
**Scope:** MVP enhancement to the existing word frequency feature in IG Pulse
**Status:** implemented (feat/wordfreq-enhancement)

---

## 1. Problem

The current word frequency feature (`app/analysis/wordfreq.py`) is purely quantitative:
it counts non-stopword tokens across a scope of comments and returns the top N. The user
cannot:

- Exclude noisy words from a specific view without permanently editing the checked-in stopword file
- Filter the input to a specific sentiment bucket (e.g. "what are people complaining about?")
- Read the actual comments behind a word to understand *why* it's frequent — only the count

This spec defines a richer feature that adds **input filters**, **per-view exclusions with
optional persistence**, and a **qualitative drill-down** — without adding new ML dependencies
or expanding scope beyond MVP discipline (B1).

## 2. Decisions made during brainstorming

- **Counting strategy:** **Hybrid** — keep the existing token-based counter, design a clean
  seam so a "nouns only" mode can be added later via Sastrawi without rewriting. No POS
  tagging now.
- **Exclusion UX:** **Per-view chips + save-to-permanent button + "show what's filtered"
  transparency toggle.** Chips are URL state (shareable, debuggable, back-button-friendly).
  Permanent saves go into a new `user_stopwords` SQLite table that overlays the existing
  `stopwords_custom.txt`.
- **Input filter:** **Sentiment bucket only** (`all | positive | neutral | negative`). No
  per-post selector, no language filter, no min-length filter. The page-level scope still
  applies on top.
- **Drill-down:** **Sample modal** — click a word, see N random comments containing it.
  Direct analogue of the existing sentiment `_sample_modal.html`. No sentiment-breakdown
  badge, no co-occurrence, no LLM summary.
- **Click semantics:** click a word = drill-down (informative, safe). Excluding requires
  an explicit action (input box, or button inside the drill-down modal).
- **Export:** the `/export/wordfreq` endpoint accepts the same filter/exclusion params so
  the exported PNG matches what the user is viewing (B8). The PNG footer includes a small
  caption stating the current filter state.

## 3. Architecture

```
app/
├── analysis/
│   ├── wordfreq.py            # MODIFIED: + exclude_words param; + comments_with_word()
│   ├── stopwords.py           # MODIFIED: get_stopwords() merges file + DB overlay
│   ├── stopwords_custom.txt   # unchanged baseline
│   └── user_stopwords.py      # NEW: SQLite CRUD for the user overlay (~30 lines)
├── db.py                       # MODIFIED: + user_stopwords table reference
├── migrations/
│   └── 002_user_stopwords.sql # NEW: CREATE TABLE user_stopwords
├── routes/
│   └── analysis.py            # MODIFIED: /analysis/wordfreq accepts query params
│                              # NEW: /analysis/wordfreq/sample
│                              #      POST /analysis/wordfreq/stopwords
│                              #      DELETE /analysis/wordfreq/stopwords
│                              #      /analysis/wordfreq/filtered
└── templates/partials/
    ├── frag_wordfreq.html     # MODIFIED: + sentiment filter, chips, exclude input
    ├── _wordfreq_sample.html  # NEW: drill-down modal
    └── _wordfreq_filtered.html# NEW: "what's being filtered" panel
```

### Key boundaries

- `tokenize()` stays pure and untouched.
- `word_frequencies(comments, top_n, exclude_words=None)` adds one optional parameter.
  Default-args call is byte-identical to today (backward-compat regression test enforces this).
- A new `comments_with_word(comments, word, n=5, seed=None) -> list[Comment]` helper sits
  beside `word_frequencies` in the same module. Token-equality match (not substring), same
  lowercase + tokenize pipeline as the count, so semantics are consistent.
- `app/analysis/user_stopwords.py` exposes `list_user_stopwords()`, `add_user_stopword(word)`
  (idempotent), and `remove_user_stopword(word)`. All normalize to lowercase + strip.
- `get_stopwords()` keeps the file-loaded base cached and queries the DB overlay on every
  call (the overlay table is small; this avoids cache-invalidation bugs when the user
  edits via UI).

## 4. Data flow (URL state)

All wordfreq state lives in the URL:

```
/analysis/wordfreq?<scope_qs>&sentiment=all|positive|neutral|negative&exclude=word1&exclude=word2
```

Five interaction flows:

1. **Add chip** → HTMX `hx-get` to the same URL with a new `&exclude=` appended → whole
   `#wordfreq-card` swaps.
2. **Remove chip** → same URL minus that `exclude=` → swap.
3. **Change sentiment** → same URL with new `&sentiment=` value → swap.
4. **Save chip to permanent** → `hx-post /analysis/wordfreq/stopwords?word=<w>` →
   inserts into `user_stopwords`, response is the refreshed fragment.
5. **Click word** → `hx-get /analysis/wordfreq/sample?word=<w>&n=5&<scope_qs>&sentiment=<bucket>`
   → returns `_wordfreq_sample.html` swapped into `#modal-root`.

**Invariant:** the drill-down modal respects the **same sentiment filter** the user is viewing.
If they're looking at negative-bucket words and click "ribet", the modal shows random
*negative* comments containing "ribet" — not all comments. The qualitative evidence must
match the quantitative chart.

## 5. Data model

New migration `app/migrations/002_user_stopwords.sql`:

```sql
CREATE TABLE IF NOT EXISTS user_stopwords (
    word        TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- `word` is the natural key (lowercase, matches `tokenize()` output).
- No FK to comments — stopwords aren't owned by comments.
- INSERT OR IGNORE for the add path so duplicate saves are silent no-ops.
- B5 compliance: this is a new additive migration. No DROP, no ALTER on existing tables.

**No FTS index needed.** The drill-down (`comments_with_word`) scans the already-loaded
in-memory comment list and tokenizes — same pipeline as the count. Single-creator MVP
data volume is small enough that this is fast (low thousands of comments per scope).

## 6. UI layout (frag_wordfreq.html)

```
┌─ Frekuensi Kata ─────────────────────────────────────────┐
│ [ Semua | 😊 Positif | 😐 Netral | 😡 Negatif ]          │ ← sentiment filter
│                                                           │
│ Dikecualikan: [iya ×💾] [mantap ×💾]  + tambah: [_____]  │ ← chips + input
│ ▸ 14 kata tersembunyi (klik untuk lihat)                 │ ← collapsed "what's filtered"
│                                                           │
│ ┌──────────────────────┬───────────────────┐             │
│ │  cloud-words area    │  top-list          │             │
│ │  (clickable words)   │  (clickable rows)  │             │
│ └──────────────────────┴───────────────────┘             │
└───────────────────────────────────────────────────────────┘
```

- **Click on word/top-list-row → drill-down modal.** Single click. No hover trickery.
- **Exclude** is done via the text input (Enter to add) or via the **"Kecualikan kata ini"**
  button inside the drill-down modal (user reads first, then decides).
- **Chip 💾 button** promotes the chip to permanent `user_stopwords`. The chip then disappears
  because the word is now in the global filter set.
- **"Show what's filtered" panel** is a collapsible HTMX-loaded partial listing hidden words
  grouped by source: *Kata yang kamu simpan* (with × to remove) and *Stopword bawaan* (read-only).
  Each entry shows what its count *would have been* — transparency over silent dropping (B3).

All copy is in Bahasa Indonesia (B9).

## 7. Edge cases (defensive behavior)

| Case | Behavior |
|---|---|
| No chips, no sentiment filter | Fragment renders normally; backward-compatible with current behavior. |
| All top words excluded | Empty cloud + inline message: *"Semua kata teratas dikecualikan. Hapus chip di atas untuk melihat hasil."* |
| Sentiment bucket has 0 comments | *"Tidak ada komentar negatif pada cakupan ini."* |
| Exclude a word that's also in file stopwords | INSERT OR IGNORE; chip vanishes on refresh because the word wasn't in the cloud anyway. |
| Exclude with whitespace/mixed case | Normalize: `word.strip().lower()`. Empty → 400. |
| Exclude longer than 50 chars | Truncate to 50 and accept. Cheap URL-abuse defense. |
| Click word, sentiment changes mid-flight | Browser races; user can re-click. Acceptable. |
| Click an emoji in the cloud | Same drill-down works. `comments_with_word("😂", ...)` finds emoji-only comments (B3). |
| Drill-down finds 0 matches | *"Tidak ada komentar yang mengandung kata ini pada filter saat ini."* |
| Stale `exclude=` after removing saved stopword | Chip reappears via URL state. Expected: per-view exclude is independent of saved set. |
| SQL injection / XSS | Parameterized SQLite. Jinja2 autoescape on. `word` whitelisted to tokenizer-alphabet regex; non-matching → 400. |
| Modal screenshot shared in isolation | Modal header always shows filter state. B4 model-disclaimer caveat is rendered **only when `sentiment != all`** (no caveat needed when no sentiment model was consulted). |

**Logging (B11):** every new route logs scope, sentiment, exclude count, result count,
duration. No comment text, no tokens (per the post-incident rule in
`fetch-concurrency-guard` memory).

## 8. Testing approach

Real-data fixtures from `tests/fixtures/` only (B10). No synthetic comment generation.

**Unit — analysis**
- `test_word_frequencies_backward_compat` — default args identical to today (gold snapshot at `tests/snapshots/wordfreq_top100.json`). **Must pass first.**
- `test_word_frequencies_excludes_words`
- `test_word_frequencies_exclude_overrides_count`
- `test_word_frequencies_exclude_case_insensitive`
- `test_comments_with_word_token_equality`
- `test_comments_with_word_emoji` (B3 evidence)
- `test_comments_with_word_deterministic_with_seed`
- `test_comments_with_word_no_match`

**Unit — stopwords overlay**
- `test_user_stopwords_add_idempotent`
- `test_user_stopwords_remove`
- `test_get_stopwords_merges_overlay`
- `test_get_stopwords_overlay_lowercased`

**Integration — routes (FastAPI TestClient)**
- `test_wordfreq_fragment_with_exclude`
- `test_wordfreq_fragment_with_sentiment`
- `test_wordfreq_sample_modal`
- `test_wordfreq_sample_inherits_sentiment_filter`
- `test_wordfreq_save_stopword`
- `test_wordfreq_remove_saved_stopword`
- `test_wordfreq_word_param_rejects_invalid`

**Integration — export (B8)**
- `test_export_wordfreq_respects_filters`

Each test file has a one-line docstring naming the CLAUDE.md rule it enforces.

## 9. What is explicitly out of scope

- POS tagging / noun-only mode (designed-for, not built)
- Named entity recognition
- Co-occurrence / word relationship graphs
- LLM-generated summaries of why a word is present
- Sentiment breakdown badge inside the drill-down modal
- Per-post or per-language filters
- Multi-user stopword lists (the table is designed single-user but extensible)
- Auto-suggestions for words to exclude

These can be revisited after MVP usage data shows real demand.

## 10. Open questions

None at this time. All forks resolved during brainstorming.

## 11. CLAUDE.md rules touched

- **B1** scope discipline — Phase 2 items kept explicitly out.
- **B3** messy text — emoji clicks, no silent dropping, transparency panel.
- **B4** sentiment honesty — drill-down modal carries the model disclaimer.
- **B5** SQLite source of truth — new additive migration, no DROP.
- **B6** HTMX over JS — all interactions are `hx-get`/`hx-post` swaps.
- **B7** Plotly server-rendered — wordcloud rendering unchanged.
- **B8** export must reflect filters — `/export/wordfreq` accepts same params + footer caption.
- **B9** Indonesian copy — all UI labels in Bahasa Indonesia.
- **B10** real data fixtures — all tests use `tests/fixtures/`.
- **B11** logging — no text, no tokens, structured per-route logs.
