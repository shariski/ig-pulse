# IG Pulse — Design Handover

For Claude Code. This folder contains everything needed to implement the UI redesign of IG Pulse.

## Files

| File | What it is | When to use it |
|---|---|---|
| `design-system.md` | **Read this first.** Tokens, components, principles, patterns. | Before any UI work. Reference throughout. |
| `reference-sentiment-wordfreq.html` | Hero + sentiment card + word frequency card | Implementing dashboard layout, sentiment card, word freq card |
| `reference-timetrend.html` | Time trend card (card 03/04) | Implementing time trend analysis |
| `reference-modal.html` | Sentiment samples modal pattern | Implementing any modal (sentiment samples, export options, etc.) |

## What's NOT in the wireframes (use design-system.md + judgment)

- N-gram phrases card (04/04) — use the sentiment card stat-row pattern but with bigrams as items
- Empty / loading / error states — universal patterns specified in `design-system.md` § "States"
- Export-to-PNG modal — use modal pattern from `reference-modal.html` with a form layout
- Mobile responsive behavior — breakpoint behavior in `design-system.md` § "Responsive behavior"
- Token-expiry banner in sidebar — use badge pattern from `design-system.md` § "Badge / pill"

## Implementation order

1. **Set up tokens.** Create `app/static/css/tokens.css` with all CSS variables from `design-system.md`. Import in base template.
2. **Set up typography.** Add Google Fonts link to base template. Add base body styles.
3. **Set up theme toggle.** Persist preference in localStorage. Apply `data-theme` to `<html>`.
4. **Build sidebar component.** Use `reference-sentiment-wordfreq.html` as reference.
5. **Build card component (Jinja2 partial).** Match the pattern in `design-system.md` § "Card".
6. **Implement each analysis card.** Sentiment first (most reference material), then word freq, then time trend, then n-gram.
7. **Implement modal component (Jinja2 partial + HTMX).** Sentiment samples first.
8. **Add states.** Empty, loading, error per card.
9. **Add export flow.** Modal + server-side PNG generation.

## Stack constraints (from CLAUDE.md)

- FastAPI + Jinja2 server-side rendering
- HTMX for swaps (no JS framework, no build step)
- Tailwind from CDN is OK if needed, but prefer raw CSS with tokens — matches the editorial aesthetic better
- All UI copy in Bahasa Indonesia (wireframes show English for design clarity; translate during implementation)

## What to ask before doing

- **Anything that introduces a new design token, font, animation, or component pattern not in `design-system.md`.** Surface it, don't add silently.
- **Anything that affects shareability** (export flow, watermark, image sizing) — these are first-class per CLAUDE.md B8.
- **Anything that touches the sentiment classifier presentation** — high-risk per CLAUDE.md B4. Visual must acknowledge uncertainty.

## Indonesian-language note

Wireframes use English headings ("What people *actually said*", "When they *talked*") for design review clarity. In implementation, translate to Bahasa Indonesia per CLAUDE.md B9. Suggested translations:

- "What people actually said" → "Apa yang sebenarnya mereka katakan"
- "When they talked" → "Kapan mereka bicara"
- "How they felt" → "Bagaimana perasaan mereka"
- "Words that came up" → "Kata yang paling sering muncul"
- Stat labels: "Comments" → "Komentar", "Posts" → "Postingan", "Time range" → "Periode"

The italic *accent word* pattern (one italicized word per title) should be preserved — Lora's italic is its character feature.

## Out-of-scope reminders (do not implement, even if it seems easy)

Per `CLAUDE.md` § B1:
- SNA / graph visualization
- BERTopic / topic clustering
- Scheduler / cron / recurring pulls
- Multi-account support
- Public share links

If the user asks for any of these during implementation, surface and confirm scope change first.
