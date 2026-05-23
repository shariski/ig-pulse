# Plan — IG Pulse MVP

Flat task list. Check off as you go. Order suggests dependency, but Claude Code can reorder where parallelism is safe.

🔰 = first-time / unfamiliar territory, expect to spend learning time
⚠️ = depends on something unverified, do verification task first

## Phase 0 — Prereqs (do before any coding)

- [ ] Confirm IG account is Creator or Business
- [ ] Confirm IG is linked to a Facebook Page (create one if not)
- [ ] 🔰 Create Meta Developer account at developers.facebook.com
- [ ] 🔰 Create Meta App (type: Business, name: ig-pulse-personal or similar)
- [ ] 🔰 Add "Instagram Graph API" product to the app
- [ ] 🔰 Generate short-lived token via Graph API Explorer with permissions: `instagram_basic`, `instagram_manage_comments`, `pages_show_list`, `pages_read_engagement`
- [ ] Fetch `/me/accounts` → note FB Page ID
- [ ] Fetch `/{page-id}?fields=instagram_business_account` → note IG_USER_ID
- [ ] Exchange short-lived token for long-lived (60-day) token
- [ ] Smoke test: `GET /{IG_USER_ID}?fields=username,followers_count` returns correct data
- [ ] Save `IG_USER_ID`, `IG_ACCESS_TOKEN`, `FB_APP_ID`, `FB_APP_SECRET` somewhere safe (will go into `.env` next)

## Phase 1 — Project scaffold

- [ ] Initialize Python 3.11+ project with `uv` or `poetry`
- [ ] Add dependencies: `fastapi`, `uvicorn`, `httpx`, `pydantic`, `pydantic-settings`, `jinja2`, `python-multipart`
- [ ] Add analysis dependencies: `transformers`, `torch`, `Sastrawi`, `nltk`, `wordcloud`, `pillow`, `plotly`, `kaleido`
- [ ] Add dev dependencies: `pytest`, `pytest-asyncio`, `ruff`, `mypy`
- [ ] Create folder structure as per `docs/architecture.md`
- [ ] Create `.env.example` with all required vars (placeholders only)
- [ ] Create `.env` from `.env.example`, fill with real values
- [ ] Add `.env`, `logs/`, `exports/`, `ig_pulse.db`, `*.pyc`, `__pycache__/` to `.gitignore`
- [ ] Initial git commit

## Phase 2 — IG client (verify API behavior before building anything else)

⚠️ Every task here depends on real API responses. Do not mock.

- [ ] Implement `app/config.py` — pydantic-settings loading from `.env`
- [ ] Implement `app/ig_client.py` skeleton with `httpx.AsyncClient`
- [ ] Implement `get_user_profile()` → smoke test against real account
- [ ] Implement `list_media(limit, after)` with pagination → verify V1 (pagination behavior), save fixture
- [ ] Implement `get_comments(media_id, limit, after)` → verify V2 (comment text encoding), save fixture
- [ ] Implement `get_replies(comment_id, limit, after)` → verify V3 (replies sort + pagination), save fixture
- [ ] Implement rate limit header parsing → verify V5 (header format), save fixture
- [ ] Add exponential backoff on 429
- [ ] Add request logging (endpoint, status, duration, response size)
- [ ] Verify V4 (deleted comment behavior) with a friend's help, document in `ig_client.py` docstring
- [ ] Verify V6 (reply depth) — do replies have replies? Document behavior
- [ ] Implement `app/cli.py` — `setup`, `refresh-token`, `fetch` commands

## Phase 3 — Database

- [ ] Implement `app/db.py` — connection helper, migration runner
- [ ] Write `app/migrations/001_initial.sql` with the 4 tables from `architecture.md`
- [ ] Write `app/models.py` — pydantic models for Post, Comment, CommentAnalysis, FetchLog
- [ ] Implement `upsert_post`, `upsert_comment`, `get_comments_in_scope` helpers
- [ ] Implement fetch orchestrator: takes a scope, populates SQLite, returns count
- [ ] Test fetch on 1 post end-to-end → confirm SQLite has expected rows
- [ ] Test fetch on a small period (e.g. last 7 days) → confirm pagination + caching works
- [ ] Re-run same fetch → confirm only new comments hit API (cache works)

## Phase 4 — Analysis modules

Each analysis is a pure function. Build + test in isolation before wiring to UI.

### Sentiment

- [ ] Implement `app/analysis/sentiment.py`
- [ ] Download both candidate models locally (`tabularisai/multilingual-sentiment-analysis` + `cardiffnlp/twitter-xlm-roberta-base-sentiment`)
- [ ] Run both on 100 real comments from a real post
- [ ] Manually label those 100 comments (gold set), compare accuracy
- [ ] Pick the winner, document choice in `docs/decisions.md`
- [ ] Implement batched inference, write results to `comment_analysis` table
- [ ] Handle empty/emoji-only/too-short comments → `unanalyzed` label
- [ ] Make idempotent (re-running on already-analyzed comments is a no-op)

### Word frequency

- [ ] Implement `app/analysis/wordfreq.py`
- [ ] Compose stopwords: Sastrawi ID + NLTK EN + `stopwords_custom.txt`
- [ ] Tokenizer: lowercase, strip URLs/mentions/hashtags, split on whitespace+punct
- [ ] Return top-N word counts as `list[tuple[str, int]]`
- [ ] Test on real fixture, eyeball top 20 — confirm no obvious junk

### Time trend

- [ ] Implement `app/analysis/timetrend.py`
- [ ] Group comments by day in `Asia/Jakarta`
- [ ] Join with `comment_analysis` for sentiment split per day
- [ ] Return `list[dict]` with date, total, pos, neg, neu, unanalyzed
- [ ] Test on real fixture spanning >1 day

### N-gram phrases

- [ ] Implement `app/analysis/phrases.py`
- [ ] Reuse tokenizer from `wordfreq.py`
- [ ] Generate bigrams + trigrams within each comment
- [ ] Filter: count ≥ 3, no stopword tokens, not all-emoji
- [ ] Return top 20
- [ ] Test on real fixture, eyeball — confirm output looks like "things people say"

## Phase 5 — Rendering

- [ ] Implement `app/render/charts.py` — Plotly figures for sentiment pie, time trend line, phrase bar
- [ ] Implement `app/render/wordcloud.py` — PNG via `wordcloud` library
- [ ] All chart functions return either Plotly figure or PIL Image
- [ ] Implement `app/render/export.py` — PNG export at 1080×1080, 1080×1350, 1080×1920 with optional watermark
- [ ] Watermark: creator handle, bottom-right, white text, 60% opacity, drop shadow for readability

## Phase 6 — FastAPI app + dashboard

- [ ] Implement `app/main.py` — FastAPI instance, middleware, startup hook for migrations
- [ ] Implement `app/templates/base.html` — minimal layout, HTMX from CDN, Tailwind from CDN (or Pico.css for less config)
- [ ] Implement `app/templates/dashboard.html` — scope selector + 4 chart slots
- [ ] Implement `app/routes/scope.py` — endpoints to list posts, set scope
- [ ] Implement `app/routes/analysis.py` — endpoints returning HTMX fragments per analysis
- [ ] Implement `app/templates/partials/` — one Jinja2 partial per chart
- [ ] Wire HTMX: scope change → htmx-trigger fetches all 4 analysis fragments
- [ ] Add loading skeletons per fragment
- [ ] Add error state per fragment (failure in one doesn't break others)

## Phase 7 — Sentiment sanity-check modal

- [ ] Implement endpoint `/sentiment/{bucket}/samples` returning 5 random comments from bucket
- [ ] Each sentiment slice in pie chart triggers HTMX call to that endpoint
- [ ] Modal partial renders comments with text, author, post link, "show 5 more" button

## Phase 8 — Export flow

- [ ] Implement `/export` endpoint accepting chart_id + format + watermark toggle
- [ ] Returns PNG file with `Content-Disposition: attachment`
- [ ] Each chart partial has an Export button → opens modal with format picker → triggers download

## Phase 9 — Polish

- [ ] All UI copy in Bahasa Indonesia (review every template)
- [ ] Sentiment captions on every chart: model name + version + "klasifikasi otomatis, bukan kebenaran mutlak"
- [ ] Token expiry banner in dashboard header (warn if < 14 days left)
- [ ] "Last refreshed" indicator next to scope selector
- [ ] Manual refresh button on dashboard
- [ ] Empty state for each fragment with clear next-step copy

## Phase 10 — Validation

- [ ] Dogfood: run on real account, scope = last 30 days, click through every feature
- [ ] Export one chart of each type → verify PNG looks clean at 1080×1080
- [ ] Document any rough edges in `docs/dogfooding.md`
- [ ] Decide based on usage: ship Phase 2 features now, or wait

## Out of MVP (do not start, even if tempted)

- Topic clustering (BERTopic)
- SNA graph / reply chains visualization
- Scheduler / cron
- Public share links
- Multi-account
- DM analysis
