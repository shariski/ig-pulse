# Architecture — IG Pulse

This doc captures *how* we build, separately from *what* we build (which is in `product-spec.md`).

## High-level shape

Single Python process, FastAPI app, SQLite file, HTMX frontend. No external services beyond Meta's Graph API and HuggingFace model downloads.

```
ig-pulse/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI entrypoint
│   ├── config.py            # pydantic-settings, reads .env
│   ├── ig_client.py         # Graph API wrapper, rate limit aware
│   ├── db.py                # SQLite connection + helpers
│   ├── migrations/          # schema migration scripts (numbered)
│   ├── models.py            # pydantic models for IG data
│   ├── analysis/
│   │   ├── sentiment.py
│   │   ├── wordfreq.py
│   │   ├── timetrend.py
│   │   └── phrases.py       # n-gram extraction
│   ├── render/
│   │   ├── charts.py        # Plotly figure builders
│   │   ├── wordcloud.py     # PIL/wordcloud PNG generation
│   │   └── export.py        # PNG export for sharing
│   ├── routes/
│   │   ├── dashboard.py
│   │   ├── scope.py
│   │   ├── analysis.py
│   │   └── export.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── partials/        # HTMX swap targets
│   ├── static/
│   └── cli.py               # setup, refresh-token, fetch commands
├── tests/
│   ├── fixtures/            # real IG API responses, sanitized
│   └── test_*.py
├── docs/
├── logs/
├── .env.example
├── pyproject.toml
└── README.md
```

## Tech choices and why

### FastAPI

Server-rendered HTMX needs a backend that's good at returning HTML fragments. FastAPI + Jinja2 covers this. Async support helps for the IG API calls (which are network-bound). Single dependency, well documented.

Rejected: Flask (no async benefits for our IO pattern), Django (overkill for one user, one DB).

### SQLite

Single file, no server, ACID, perfect for single-user analytics workload. We never expect concurrent writers. Read-heavy after initial fetch.

Rejected: Postgres (operational overhead for zero benefit at this scale), DuckDB (better for OLAP but worse for the row-by-row writes during fetch).

### HTMX + Jinja2

Dashboard is mostly "click button → load chart fragment". HTMX handles this without a build step, npm, or a frontend framework. Charts come from Plotly as self-contained HTML.

Rejected: React/Next.js (build pipeline overhead, JSON API boundary unnecessary), Streamlit (UI feels generic, hard to customize export-to-PNG flow).

### Plotly for charts

Server-rendered to HTML fragments. Same figure object can be exported to PNG via `fig.write_image()` (requires `kaleido`). One library covers both interactive and export.

Rejected: Matplotlib (no interactivity), Chart.js (would need a JS layer), Altair (export-to-PNG path is more fragile).

### Sentiment model

**Default candidate:** `tabularisai/multilingual-sentiment-analysis` (DistilBERT-based, fast, supports Indonesian). Backup: `cardiffnlp/twitter-xlm-roberta-base-sentiment`.

Decision deferred to Phase 1 task: load both, run on the same 100 sanitized comments from a real post, eyeball-compare with creator's own labels. Pick the one that matches creator's intuition better.

Why not OpenAI/Anthropic API for sentiment: cost per comment, latency, and no offline re-runs. Local transformer is one-time download then free forever.

### Word frequency stopwords

Stack: Sastrawi Indonesian stopwords + NLTK English stopwords + custom list (emoji, "wkwk", "hehe", "@", "https", etc., maintained in `app/analysis/stopwords_custom.txt`).

Tokenization: simple whitespace + punctuation split. No stemming in MVP (Indonesian stemming is noisy and often degrades word cloud readability — words like "memakan" vs "makanan" carry different meanings the audience would lose).

### N-gram phrases

Bigrams + trigrams, filtered by:
- Min count ≥ 3 occurrences
- Neither token is a stopword
- Not entirely emoji

Top 20 by frequency, shown as a ranked list with bar chart. This is the "narrative dominan" proxy.

## Database schema

```sql
-- posts: one row per IG post
CREATE TABLE posts (
    id              TEXT PRIMARY KEY,         -- IG media ID
    caption         TEXT,
    media_type      TEXT,                     -- IMAGE | VIDEO | CAROUSEL_ALBUM | REELS
    permalink       TEXT NOT NULL,
    timestamp       TEXT NOT NULL,            -- ISO 8601, UTC
    like_count      INTEGER,
    comment_count   INTEGER,
    thumbnail_url   TEXT,
    fetched_at      TEXT NOT NULL             -- when we cached this row
);

-- comments: one row per IG comment, including replies
CREATE TABLE comments (
    id                  TEXT PRIMARY KEY,     -- IG comment ID
    post_id             TEXT NOT NULL,
    parent_comment_id   TEXT,                 -- NULL for top-level, else parent ID
    author_handle       TEXT,                 -- username, may be NULL if user deleted
    text                TEXT NOT NULL,        -- raw comment text
    timestamp           TEXT NOT NULL,        -- ISO 8601, UTC
    like_count          INTEGER,
    fetched_at          TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE INDEX idx_comments_post ON comments(post_id);
CREATE INDEX idx_comments_parent ON comments(parent_comment_id);
CREATE INDEX idx_comments_timestamp ON comments(timestamp);

-- comment_analysis: derived sentiment + future analysis outputs
CREATE TABLE comment_analysis (
    comment_id          TEXT PRIMARY KEY,
    sentiment_label     TEXT NOT NULL,        -- positive | negative | neutral | unanalyzed
    sentiment_score     REAL,                 -- model confidence 0-1
    model_name          TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    analyzed_at         TEXT NOT NULL,
    FOREIGN KEY (comment_id) REFERENCES comments(id)
);

-- fetch_log: observability for every fetch run
CREATE TABLE fetch_log (
    run_id              TEXT PRIMARY KEY,     -- uuid
    scope_type          TEXT NOT NULL,        -- post | period | all
    scope_value         TEXT,                 -- post_id, ISO range, or NULL
    started_at          TEXT NOT NULL,
    ended_at            TEXT,
    api_calls_made      INTEGER DEFAULT 0,
    comments_fetched    INTEGER DEFAULT 0,
    error               TEXT
);
```

Migrations live in `app/migrations/` as numbered SQL files (`001_initial.sql`, `002_*.sql`, ...). A simple runner in `app/db.py` applies migrations on startup and tracks applied versions in a `_migrations` table.

## Graph API integration

### Endpoints used in MVP

- `GET /{ig-user-id}/media` — list user's posts (paginated)
- `GET /{media-id}` — post metadata (caption, like_count, comment_count, timestamp, permalink)
- `GET /{media-id}/comments` — top-level comments for a post (paginated)
- `GET /{comment-id}/replies` — replies to a comment (paginated)

Reply fetch is per-comment and can blow up call count. MVP behavior: fetch replies only for top-level comments with `comment_count > 0`. Document this in fetch log.

### Permissions needed

- `instagram_basic`
- `instagram_manage_comments` (read access to comments)
- `pages_show_list` + `pages_read_engagement` (to traverse Page → IG)

All available in development mode without app review (single own account only).

### Token lifecycle

1. Generate short-lived user token via Graph API Explorer (~1 hour).
2. Exchange for long-lived token (60 days) via `GET /oauth/access_token` with `grant_type=fb_exchange_token`.
3. Refresh before expiry via `GET /refresh_access_token` (CLI command).

Manual for MVP. Calendar reminder is the user's job.

### Rate limit handling

`ig_client.py` reads `X-Business-Use-Case-Usage` header after every call, parses the usage percentage, and:
- < 75% → proceed normally
- 75–90% → log warning
- ≥ 90% → sleep 60s before next call
- 429 response → exponential backoff (60s, 120s, 240s, then fail)

Every API call increments a counter in the current `fetch_log` row.

## Analysis pipeline

Each of the four MVP analyses is a pure function over a list of comment rows:

```python
def analyze(comments: list[Comment]) -> AnalysisResult: ...
```

Pipeline is sequential, not parallel (single-user, small data, simpler to reason about). Total runtime budget: < 30s for 1000 comments on a laptop.

### Sentiment

- Batch size 32, run on CPU (or MPS on Mac).
- For comments where text is empty/emoji-only/under 3 chars: label `unanalyzed`, skip model call.
- Write to `comment_analysis` after each batch (resumable on crash).

### Word frequency

- Lowercase, strip URLs/mentions, tokenize on whitespace+punct.
- Remove stopwords (combined ID+EN+custom).
- Count occurrences across all comments in scope.
- Top 100 for word cloud; top 50 as ranked list.

### Time trend

- Group comments by day (WIB timezone).
- For each day: total count + sentiment split (from `comment_analysis`).
- Output: list of `(date, total, pos, neg, neu, unanalyzed)`.

### N-gram phrases

- Same tokenization as word frequency.
- Generate bigrams + trigrams within each comment (not across comments).
- Filter as described in Tech choices.
- Top 20 by frequency.

## Export-to-PNG

- Plotly: `fig.write_image(path, width=W, height=H, scale=2)` via `kaleido`.
- Word cloud: already a PNG, just resize via PIL.
- Watermark: PIL overlay with creator handle, bottom-right, semi-transparent.
- Output saved to `exports/` with timestamp-based filename, then served via FastAPI as download.

## What we explicitly don't build

- ORM (raw SQL is fine at this scale)
- Migrations framework (sqlite + numbered SQL files is enough)
- API client library beyond `httpx`
- Caching layer beyond SQLite itself
- Background job queue
- Auth (single-user, runs locally)
