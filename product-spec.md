# Product Spec — IG Pulse

## Who is this for

One person: a creator with an Instagram Creator/Business account who wants to understand and visualize the conversation happening in the comments under their posts, then share that understanding back with their audience.

This is not a product for agencies, not for analyzing other people's accounts, not for monitoring competitors. Single creator, own account.

## The problem in one paragraph

Once a post crosses ~50 comments, manually reading and summarizing the conversation becomes impractical. The creator wants the kind of read-out Drone Emprit gives for Twitter — sentiment, dominant words, tone, time trend — but for their own Instagram account, and rendered as a dashboard they can show back to their audience as "ini lho percakapan kita di kolom komentar."

## What success looks like for the user

After running IG Pulse on a scope (one post / last 30 days / all-time):

1. They can immediately see the sentiment split of the conversation, and click into examples to verify the model isn't lying.
2. They can see what words and phrases dominate, in a form (word cloud + ranked list) that's screenshot-friendly.
3. They can see how the conversation evolved over time — when it spiked, when it cooled, when sentiment flipped.
4. They can export any chart as a 1080×1080 or 1080×1350 PNG suitable for re-posting.

If all four work for one real post with real comments, MVP is done.

## User stories

### US-1: Connect my Instagram account once
**As** the creator,
**I want** to authenticate my IG account once and have the app remember the access token,
**So that** I don't re-enter credentials every run.

Acceptance:
- Setup is a one-time CLI command (`python -m app.cli setup`) that walks through token generation.
- Token is stored in `.env`.
- The app validates the token on startup and tells me how many days until it expires.

### US-2: Pull comments for a scope
**As** the creator,
**I want** to pick a scope (single post URL, date range, or all-time) and have the app fetch all comments,
**So that** I have data to analyze.

Acceptance:
- Scope is selected in the dashboard UI, not via CLI flag.
- First fetch shows a progress indicator (X of Y posts processed).
- Re-fetching the same scope reads from SQLite cache; only new comments are pulled from the API.
- The UI shows "last refreshed: 5 minutes ago" and a manual refresh button.

### US-3: See the four MVP analyses for that scope
**As** the creator,
**I want** to see sentiment breakdown, word cloud, time trend, and dominant phrases for the selected scope,
**So that** I understand the conversation at a glance.

Acceptance:
- All four analyses render on one page, in a fixed order (sentiment → word cloud → time trend → phrases).
- Each analysis loads independently via HTMX (slow ones don't block fast ones).
- Each shows a loading skeleton while computing.
- If an analysis fails, that section shows an error and a retry button; the rest of the page still works.

### US-4: Sanity-check the sentiment classifier
**As** the creator,
**I want** to click on each sentiment bucket and see 5 random comments from it,
**So that** I can decide whether to trust the classifier before showing the chart to my audience.

Acceptance:
- Each sentiment bucket (positive, negative, neutral, unanalyzed) is clickable.
- Click opens a modal with 5 random comments from that bucket, plus a "show 5 more" button.
- Each shown comment displays text + author handle + post link.

### US-5: Export any chart as a shareable image
**As** the creator,
**I want** to export a chart as a PNG sized for Instagram,
**So that** I can post it back to my audience.

Acceptance:
- Each chart has an "Export" button.
- Button opens a modal with format options: 1080×1080 (square feed), 1080×1350 (portrait feed), 1080×1920 (story).
- Optional: include creator handle as watermark (toggle, default on).
- Click "Download" → server generates PNG and triggers browser download.

### US-6: See which post drove the conversation
**As** the creator,
**I want** the time trend chart to show comment volume per day with markers for posts,
**So that** I can see which post caused the spike.

Acceptance:
- Time trend chart is a line chart of comment count per day.
- Hovering a day shows: count, sentiment split, top 3 contributing posts.
- Vertical markers on the x-axis for each post's publish date, with thumbnails on hover.

## Non-goals (MVP)

- Auto-refresh / scheduled pulls
- DM analysis
- Story comments / reactions (Stories ephemeral data is restricted in Graph API anyway)
- Multi-account
- Public share link (the dashboard is local-only; sharing happens via exported PNGs)
- Comment moderation tools (delete, hide, reply from dashboard)
- Reply-aware threading visualization (deferred — see Phase 2)

## Data model (high-level)

Four tables in SQLite. Detailed schema in `docs/architecture.md`.

- **posts** — IG post metadata: id, caption, media_type, permalink, timestamp, like_count, comment_count
- **comments** — IG comment data: id, post_id, parent_comment_id (for replies), author_handle, text, timestamp, like_count
- **comment_analysis** — derived: comment_id, sentiment_label, sentiment_score, model_name, model_version, analyzed_at
- **fetch_log** — observability: run_id, scope_type, scope_value, started_at, ended_at, api_calls_made, comments_fetched, error

## Data flow

```
[User picks scope in UI]
        ↓
[Backend resolves scope → list of post IDs]
        ↓
[For each post: check SQLite cache]
        ↓
[Missing posts/comments → Graph API call → write to SQLite]
        ↓
[Run analysis pipeline on SQLite data:]
   ├─ Sentiment classifier → comment_analysis table
   ├─ Word frequency → in-memory result
   ├─ Time trend → in-memory result
   └─ N-gram dominant phrases → in-memory result
        ↓
[Render Plotly charts + word cloud PNG]
        ↓
[Serve HTMX fragments to dashboard]
```

## UI states (per analysis section)

Each of the four MVP analyses goes through these states:

1. **Empty** — no scope selected yet. Shows: "Pilih scope dulu untuk mulai analisis."
2. **Fetching** — pulling comments from API. Shows: progress bar, "X of Y posts loaded."
3. **Analyzing** — comments fetched, model running. Shows: skeleton loader.
4. **Ready** — chart/cloud/list rendered. Shows: visualization + export button + caption with model info.
5. **Error** — fetch or analysis failed. Shows: error message + retry button. Other sections unaffected.

## Out of scope for the spec itself

The detailed analysis methodology (which sentiment model, which stopword list, n-gram threshold, etc.) lives in `docs/architecture.md`. This spec is about *what* the user sees and does; architecture is about *how*.
