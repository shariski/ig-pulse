# IG Pulse

**Personal Instagram comment analytics — Drone Emprit-style, for your own account.**

IG Pulse pulls comments from your own Instagram Creator/Business account via the official Meta Graph API, runs analysis on them, and renders an interactive web dashboard. The dashboard is meant to be shown back to the audience: "ini lho percakapan di kolom komentarku, ini tone-nya, ini topiknya, ini frasa yang sering muncul."

Built for a single creator analyzing their own account. Not a SaaS, not multi-tenant, not for analyzing other people's accounts.

## What the MVP does

For a user-selected scope (one post / a time period / all-time), pull comments from the connected IG account and render:

1. **Sentiment breakdown** — positive / negative / neutral, with examples per bucket
2. **Word frequency + word cloud** — what words/emoji dominate the conversation
3. **Time trend** — comment volume and sentiment over time, per post or per day
4. **Dominant phrases** — bigrams and trigrams that recur (cheap "narrative" proxy on top of word freq)

That's MVP. Everything else is Phase 2.

## What it deliberately does not do in MVP

- **No Social Network Analysis (SNA).** Who-replies-to-whom graph and commenter cluster detection are deferred to Phase 2. They need a different data structure (graph), different libs (`networkx`, `pyvis`), and their own visualization tuning. They are not in MVP because we don't yet know whether the audience cares about them more than the four above.
- **No topic clustering with BERTopic.** Multilingual ID/EN comment clustering is hard to tune well on the first try. N-gram dominant phrases (in MVP) cover ~70% of the "what are people talking about" question at ~10% of the effort. Topic clustering ships in Phase 2 if dominant-phrase output proves insufficient.
- **No scheduler.** MVP is single-run, manually triggered. Scheduled background pulls land in Phase 2 if usage shows we re-run weekly anyway.
- **No multi-account support.** Single creator, single connected IG account, single SQLite file.
- **No DM analysis.** Graph API does not expose DMs in bulk for analysis.
- **No cross-platform.** Instagram only. No Twitter/X, no TikTok, no YouTube.
- **No public deployment.** Runs locally (or on a personal VPS). The dashboard is rendered as HTML, then exported as PNG/PDF when shared back to the audience.

These are scope decisions, not "coming later."

## Phase 2 (deferred, not promised)

- Topic clustering (BERTopic + multilingual embeddings)
- SNA: commenter activity graph, reply chains, community detection
- Scheduler for recurring pulls
- Public-share mode (read-only dashboard link)

Phase 2 is gated on Phase 1 actually getting used and the audience giving feedback on which gaps matter most.

## Stack

Working defaults, finalized during Phase 1 setup:

- **Backend:** Python 3.11+ (FastAPI), single process
- **Frontend:** HTMX + Jinja2 templates (server-rendered, no SPA)
- **Storage:** SQLite, single file (`ig_pulse.db`)
- **IG access:** Meta Instagram Graph API, long-lived access token, development mode (own account only — no app review required)
- **Sentiment model:** multilingual transformer (working default: `tabularisai/multilingual-sentiment-analysis` or `cardiffnlp/twitter-xlm-roberta-base-sentiment`, pick during Phase 1)
- **Charts:** Plotly (server-rendered to HTML fragments)
- **Word cloud:** `wordcloud` library, rendered to PNG
- **Hosting:** local dev machine for MVP; personal VPS optional

The full reasoning behind these choices lives in `docs/architecture.md`.

## Prerequisites before Day 1 of coding

1. **Instagram account is Creator or Business** (already confirmed yes)
2. **Facebook Page exists and is linked to the IG account** (create one if not; free; can be empty)
3. **Meta Developer account** at developers.facebook.com (free; ~15 min signup)
4. **Meta App created** — type "Business", with "Instagram Graph API" product added
5. **Long-lived access token generated** for the connected IG account (60-day expiry, refreshable)

Setup walkthrough is in `docs/api-integration.md`.

## Status

Pre-build. See [`docs/plan.md`](docs/plan.md) for the task list and [`docs/risks.md`](docs/risks.md) for known unknowns.

## License

Personal project. No license granted.
