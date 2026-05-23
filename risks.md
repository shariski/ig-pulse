# Risks — IG Pulse

Categorized by what you can do about them. **R** = risk to MVP delivery. **D** = deferred idea.

---

## R1: Sentiment model quality on Indonesian comments — HIGH

Multilingual sentiment models work well on news/review text but degrade on social media slang. Indonesian IG comments use `wkwk`, `mantul`, `gas`, `auto`, mixed-language code-switching, and heavy emoji. The model may classify these wrong consistently — calling sincere positive comments "neutral" or missing sarcasm.

**Why it matters:** This is the first chart the user shows their audience. If the buckets are visibly wrong, the entire dashboard's credibility collapses.

**Mitigation:**
- Phase 4 task: manually label 100 real comments, run both candidate models, pick the winner empirically. Don't ship without this comparison.
- Every sentiment chart carries a caption: model name + version + "klasifikasi otomatis, bukan kebenaran mutlak."
- US-4 sanity-check modal lets the user and the audience click into any bucket and see actual examples.
- If neither candidate is acceptable: fall back to lexicon-based sentiment (InSet for Indonesian) as a temporary measure. Note in dogfooding doc and re-evaluate.

---

## R2: Graph API behavior differs from docs — MEDIUM

Meta docs are accurate at the endpoint level but often vague about edge cases: pagination defaults, error formats, header structure, what happens when a comment is deleted, whether replies have replies. We've listed V1–V6 in `api-integration.md` as things to verify.

**Why it matters:** Building analysis on imagined data shapes wastes time. A wrong assumption about reply structure could mean re-fetching all comments.

**Mitigation:**
- Phase 2 of plan front-loads all six verifications.
- Save raw API responses to `tests/fixtures/` so subsequent code is built against real shapes.
- Do not start Phase 4 (analysis) until V1–V6 are checked off.

---

## R3: Rate limit surprise on first big fetch — MEDIUM

The formula `4800 × impressions/24h` sounds generous, but if the account has had a quiet day, the quota for the next day is small. First-time full-history fetch could hit the limit and fail partway, leaving SQLite in an inconsistent state.

**Why it matters:** A bad first fetch experience can sour the whole project. Recovery is annoying.

**Mitigation:**
- Every successful comment fetch commits to SQLite immediately. A crashed fetch can be resumed; no comments are lost.
- `ig_client.py` logs usage % from headers. If a fetch is about to cross 90%, it sleeps rather than retrying blindly.
- First full-history fetch is staged: pull post list first (cheap), then comments per post in order from newest to oldest, so a stopped fetch still gives the user something useful.
- Document expected behavior in dogfooding: "if this is your first fetch on a large account, run it during a high-traffic day or split into chunks."

---

## R4: Long-lived token expires silently — MEDIUM

The 60-day token expires. If the user forgets to refresh and the dashboard breaks, they may not know why.

**Why it matters:** Killer UX bug. Users will give up before debugging Meta's API.

**Mitigation:**
- Dashboard header shows token expiry date and turns red at < 14 days.
- Every API client method, on receiving a token-expired error, returns a typed error that the dashboard renders as: "Token kadaluwarsa. Jalankan `python -m app.cli refresh-token`."
- `refresh-token` CLI command updates `.env` and prints new expiry.
- Not auto-refreshed in MVP. Auto-refresh is Phase 2.

---

## R5: Comment volume too high for in-memory analysis — LOW

If the user has years of history and tens of thousands of comments, loading all comments into memory for word frequency / n-grams could be slow or OOM on a small machine.

**Why it matters:** Could turn a 30s analysis into a 5-minute one or a crash.

**Mitigation:**
- Pipeline reads from SQLite, not from memory dump.
- Stream-based aggregation for word frequency and n-grams (don't build a huge intermediate list).
- Document upper bound: tested up to N comments where N is what dogfooding produces.
- If real data exceeds the comfortable ceiling, add a "max comments" parameter to scope (sample-and-warn) before optimizing.

---

## R6: Emoji-heavy comments inflate word cloud junk — LOW

Word clouds love high-frequency tokens. Emoji are usually the most frequent token. Without filtering, the word cloud will be 80% 🔥😍❤️.

**Why it matters:** Word cloud is the most screenshot-friendly chart. Junk output is shareable too — in a bad way.

**Mitigation:**
- Custom stopwords include the most common emoji.
- Optional: separate emoji-only frequency chart in Phase 2 (could actually be interesting).
- Document the stopword decision in `architecture.md`.

---

## R7: User over-shares sensitive comments via export — LOW

The export PNG includes comment text. If a comment contains personal info (phone, address, slur, etc.), the creator might unintentionally re-broadcast it.

**Why it matters:** Privacy and reputational risk, even though the comment was originally public.

**Mitigation:**
- Sanity-check modal shows author handle, so the creator can recognize specific people before exporting.
- Word cloud and sentiment pie don't show comment text by default — only aggregates.
- Time trend hover shows counts, not text.
- Add a note in dogfooding: "review comments before exporting samples."
- Not building automatic PII detection in MVP. Out of scope.

---

## R8: HuggingFace model download fails or model is removed — LOW

The candidate models live on HuggingFace and could be removed or restricted at any time.

**Why it matters:** Fresh install on a new machine could fail.

**Mitigation:**
- Pin model version in `config.py` (not just `:latest`).
- Document fallback model in `architecture.md`.
- Once a model is downloaded locally, it works forever — no runtime dependency on HuggingFace.
- Note in README setup: model download happens on first run, requires internet.

---

## R9: Plotly export-to-PNG requires `kaleido`, which is finicky — LOW

`fig.write_image()` needs the `kaleido` package, which has historically had install issues on some platforms (especially M-series Macs).

**Why it matters:** Export flow is a core feature. Broken export = broken value prop.

**Mitigation:**
- Pin a known-good `kaleido` version.
- Add a smoke test in Phase 5: render one chart, export to PNG, confirm file exists and is non-zero bytes.
- Fallback documented: if `kaleido` is broken on user's machine, use Playwright + a screenshot of the rendered HTML chart. More setup but reliable.

---

# Deferred ideas (D-section)

Things mentioned, considered, intentionally not built in MVP. Listed here so they're not lost.

## D1: Topic clustering (BERTopic)

Multilingual sentence embeddings + HDBSCAN clustering, with auto-labeled topics. Replaces or complements n-gram phrases. Deferred because tuning cluster count and label quality is its own project and n-grams cover the use case at 10% of the effort.

## D2: SNA / commenter graph

Who-comments-on-whose-posts, who-replies-to-whom, community detection via Louvain or Leiden. Visualization via `pyvis`. Deferred — different data structure, different libs, value vs effort unclear until MVP audience feedback.

## D3: Reply chain visualization

Tree view of comment threads, with sentiment per node. Could be embedded in time trend hover. Deferred — depth-1 replies are already fetched (so data exists), just no UI for it.

## D4: Scheduler

APScheduler + recurring pulls (daily, weekly). Deferred until usage shows we re-run manually every week anyway.

## D5: Auto token refresh

Cron-like task that refreshes the 60-day token at day 50. Trivial code but needs reliable scheduling. Deferred to land with D4 (scheduler).

## D6: Cross-post comparison

Side-by-side dashboard of two scopes (e.g., post A vs post B, or last week vs this week). Deferred — wait for user to ask, since the use case isn't proven.

## D7: Negative-comment alerting

Telegram/email ping when a single post crosses some negative-sentiment threshold. Deferred — overlaps with social listening tools, may not be a fit for this product's posture.

## D8: Emoji-only analysis chart

Standalone chart of "what emoji are people using". Could be fun and visually distinctive. Deferred — collect emoji counts during word freq (cheap), but render in Phase 2.

## D9: Comparison with creator's own past tone

Train a "self-baseline" of how comments usually look, surface anomalies (this week 2x more negative than usual). Interesting but needs history + a baseline algorithm. Deferred indefinitely.

## D10: Public share link

Read-only dashboard URL the creator could share. Deferred — current sharing model is PNG export, which is sufficient and avoids hosting/auth concerns.
