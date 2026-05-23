# CLAUDE.md

Behavioral guidelines for Claude Code when working on **IG Pulse**.

This file merges two layers:

- **Part A** — universal LLM coding principles (from Andrej Karpathy's observations, via multica-ai/andrej-karpathy-skills)
- **Part B** — project-specific rules for IG Pulse (personal Instagram comment analytics)

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks (typos, obvious one-liners), use judgment — not every change needs the full rigor.

---

# PART A — Universal Principles

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# PART B — IG Pulse-specific Rules

## B1. Scope discipline

This is an **MVP-first** project with explicit Phase 2 boundary. Before adding any feature:

- Check `README.md` "What it deliberately does not do in MVP" section.
- If the feature is on that list, **do not implement it** even if it seems easy. Surface the request to the user and confirm scope change.
- If the feature is on the Phase 2 list, same rule. Confirm before promoting it to MVP.

Specifically out of MVP scope (will get repeatedly asked for, must say no):
- SNA / graph visualization
- BERTopic / topic clustering
- Scheduler / cron / recurring pulls
- Multi-account support
- Public share links

## B2. Graph API hygiene

**Never** call the Graph API in a tight loop or from inside a request handler. All API calls go through `app/ig_client.py` which:

- Reads/writes the access token from a single source (`.env`)
- Caches every successful fetch into SQLite immediately (so re-runs are idempotent)
- Respects rate limit headers and backs off on 429
- Logs request count per run (so we can see if we're approaching limits)

If a piece of code needs IG data, it queries SQLite first; only on cache miss does it call the API.

**Never log the access token.** Never commit `.env`. `.env.example` is committed with placeholder values.

## B3. Comment text is messy — handle defensively

Real IG comment data will contain:
- Emoji-only comments (no text content)
- Comments in mixed Bahasa Indonesia + English + Javanese/Sundanese slang
- Spam comments (repeated emoji strings, bot-like follow-for-follow)
- Comments with @mentions, hashtags, URLs
- Comments that are just a single emoji or a single laugh ("wkwk", "😂")

Every text-processing function must explicitly state what it does with these. No silent dropping. If the sentiment model can't handle emoji-only, the comment goes into a separate "unanalyzed" bucket that the dashboard surfaces — not deleted, not pretended-to-be-neutral.

## B4. Sentiment is opinion, not fact

The dashboard will show sentiment breakdowns. **Never** present these as ground truth.

- UI copy uses "model thinks this is positive" or "classified as positive", not "this is positive"
- Each sentiment chart includes a small caption: model name + version + accuracy disclaimer
- The dashboard always provides a "show me 5 random comments from this bucket" affordance so the user can sanity-check the classifier

This is non-negotiable. The audience will see this dashboard. Misrepresenting model output as objective truth is a credibility risk.

## B5. SQLite is source of truth, API is source of fresh data

- All analysis reads from SQLite.
- API is called only to fill cache.
- Re-running an analysis on already-fetched data must work fully offline (no API calls).
- This means: schema migrations matter. When changing the comments table schema, write a migration script in `app/migrations/` — never `DROP TABLE`.

## B6. HTMX over JavaScript

Dashboard interactivity is server-rendered HTML fragments swapped via HTMX. Default to:

- `hx-get` for fetching new chart fragments
- `hx-target` + `hx-swap` for partial updates
- Jinja2 partials in `app/templates/partials/` for swappable units

Do **not** introduce a JavaScript build step, npm, or a frontend framework. If something genuinely needs JS, use a small `<script>` block inline in the relevant template, no bundler.

## B7. Charts: Plotly server-rendered, not client-side

Charts are generated server-side as HTML+inline-JS via Plotly's `fig.to_html(include_plotlyjs='cdn', full_html=False)` and injected into Jinja2 partials. Reasons:

- No client build pipeline.
- Charts work in static export (PNG/PDF) for sharing back to audience.
- Same Plotly figure can be exported as PNG via `fig.write_image()` for the share-to-audience flow.

Word cloud is rendered as PNG by the `wordcloud` library (not a chart, an image).

## B8. The "share back to audience" flow is a first-class feature

Every analysis view must have an **Export** button that produces a clean PNG suitable for posting back to Instagram Stories or feed. This means:

- No browser chrome, no nav bar in the exported image
- Watermark (creator handle) optional but supported
- Square (1080×1080) and portrait (1080×1350) presets
- Generated server-side; download triggered by HTMX

If an analysis is not exportable as an image, it doesn't belong in MVP.

## B9. Indonesian-language defaults

- All UI copy in Bahasa Indonesia by default. English is fine in code, comments, commit messages.
- Stopword list for word frequency uses an Indonesian list (Sastrawi or similar) + English stopwords + custom additions (emoji, "wkwk", "hehe", etc.).
- Sentiment model must be multilingual or Indonesian-tuned. English-only models are not acceptable.
- Date/time displayed in WIB (Asia/Jakarta) regardless of server timezone.

## B10. Test the IG client against real data early

The single biggest risk in this project is the Graph API behaving differently than docs suggest (token scope, comment pagination, reply structure). Before building any analysis:

1. Get the IG client working end-to-end against the real account.
2. Pull comments from one real post and save the raw JSON to `tests/fixtures/`.
3. Build all subsequent analysis against that fixture.

Do not build analytics on imagined data shapes. Validate the shape first.

## B11. Logging and observability

- Use `logging` stdlib, not `print`.
- Every API call logs: endpoint, status, duration, response size.
- Every analysis run logs: scope (which posts/period), comment count, duration per step.
- Logs go to `logs/ig_pulse.log` with daily rotation.
- No external observability (no Sentry, no Datadog). This is local-first.

## B12. Secrets and config

- All secrets in `.env`, loaded via `pydantic-settings`.
- `.env.example` is committed; `.env` is gitignored.
- Required env vars at minimum:
  - `IG_ACCESS_TOKEN` (long-lived)
  - `IG_USER_ID` (numeric IG business account ID)
  - `FB_APP_ID`, `FB_APP_SECRET` (for token refresh)
- Token refresh is a manual command (`python -m app.cli refresh-token`), not auto-scheduled in MVP.
