# IG Pulse — Design System

Reference for Claude Code when implementing the dashboard UI. This document is the single source of truth for visual design. If something is not in this doc, use judgment guided by the principles at the top.

This system has been validated through wireframes for: hero, sentiment card, word frequency card, time trend card, sentiment-sample modal. Use those wireframes as living examples — this doc is the abstract rules behind them.

---

## Design principles

These come first, before any token. When in doubt, read these.

1. **Readability over decoration.** Body text never below 14px. Body weight never below 500. Test in dark mode — that's where weight problems show up.

2. **The card is the unit.** Every analysis lives in a card. Cards are screenshot-friendly in isolation (no surrounding chrome needed for context). When designing anything new, ask: "Can this card stand alone as a 1080×1080 PNG?"

3. **Editorial, not corporate.** Cards have number labels (`01 / 04`), section titles use serif italic accents, metadata uses uppercase monospace. Avoid generic dashboard tropes (gradient hero numbers, sparkline-everywhere, emoji status indicators).

4. **Sentiment is opinion.** Every model output must visually acknowledge uncertainty. Caption with model name, italic disclaimer, clickable sample affordance. Never present model output with the same confidence weight as raw counts.

5. **Dark mode is default.** Light mode supported, but visual decisions optimize for dark first.

---

## Typography

### Font stack

```css
--font-display: 'Lora', Georgia, 'Times New Roman', serif;
--font-body: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
```

### Google Fonts import

```html
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,500..700;1,500..700&family=Plus+Jakarta+Sans:ital,wght@0,500..800;1,500..800&family=JetBrains+Mono:wght@500..700&display=swap" rel="stylesheet">
```

### Type scale

| Token | Size | Line height | Weight | Use |
|---|---|---|---|---|
| `--text-hero` | 72px | 0.95 | Lora 700 | Hero title (one per page) |
| `--text-display-xl` | 56px | 0.9 | Lora 700 | Big stat numbers |
| `--text-display-lg` | 40px | 1.0 | Lora 700 | Card titles |
| `--text-display-md` | 32px | 1.0 | Lora 600 | Stat labels in cards |
| `--text-display-sm` | 24px | 1.1 | Lora 600 | Modal titles |
| `--text-body-lg` | 16px | 1.5 | PJS 500 | Card prose, important body |
| `--text-body` | 14px | 1.5 | PJS 500 | Standard body, list items |
| `--text-body-sm` | 13px | 1.5 | PJS 500 | Secondary body |
| `--text-caption` | 12px | 1.4 | PJS 500 | Footer captions |
| `--text-meta` | 11px | 1.3 | Mono 600, 0.15em tracking, UPPERCASE | Labels, eyebrows, metadata |
| `--text-meta-sm` | 10px | 1.3 | Mono 600, 0.18em tracking, UPPERCASE | Sub-labels, badges |

### Type rules

- **Italic accents only on serif.** Italic body text is forbidden. Italic is reserved for word-level emphasis in display serif (e.g., "what they *actually said*").
- **Mono is ONLY for metadata.** Never use mono for body text, never for numbers in charts (use Lora). Mono is for: labels, timestamps, model names, counts in footers, code/handles like `@yourhandle`.
- **Numbers in stats use Lora.** Big numbers (counts, percentages) are display serif, not mono. This is intentional — gives them editorial weight.
- **Letter spacing:** Display sizes tighten (`-0.03em` to `-0.04em`). Body stays at 0. Mono uppercase opens to `0.15em` minimum.
- **Negative space matters more than weight at large sizes.** Don't reach for `font-weight: 900` on 72px text — use 700 with tighter letter-spacing instead.

---

## Color tokens

Two themes. Both are defined as CSS custom properties on `[data-theme]` selectors.

### Dark mode (default)

```css
:root[data-theme="dark"] {
  /* Surfaces */
  --bg: #0f0e0c;              /* Page background */
  --bg-elev: #1a1815;         /* Raised surfaces (sidebar foot, hover) */
  --bg-card: #faf7f2;         /* Card background — inverted (cream) */
  --bg-card-text: #1a1815;    /* Text on card */

  /* Text on dark surfaces */
  --fg: #faf7f2;              /* Primary text */
  --fg-muted: #a8a39a;        /* Secondary text */
  --fg-subtle: #6b6760;       /* Tertiary text, captions */

  /* Borders & dividers */
  --border: #2a2722;          /* Standard border */
  --border-strong: #3a3630;   /* Hover state, emphasized */

  /* Accent */
  --accent: #ff5b35;          /* Burnt orange — used sparingly */
  --accent-text: #faf7f2;     /* Text on accent */

  /* Semantic — for sentiment & status */
  --pos: #5cb85c;             /* Positive sentiment */
  --neg: #ff5b35;             /* Negative sentiment (same hue as accent) */
  --neu: #a8a39a;             /* Neutral sentiment */
  --warn: #f0ad4e;            /* Warning (token expiring) */
}
```

### Light mode

```css
:root[data-theme="light"] {
  /* Surfaces */
  --bg: #faf7f2;
  --bg-elev: #f0ece4;
  --bg-card: #1a1815;          /* Inverted — dark card on light bg */
  --bg-card-text: #faf7f2;

  /* Text */
  --fg: #1a1815;
  --fg-muted: #6b6760;
  --fg-subtle: #a8a39a;

  /* Borders */
  --border: #e2ddd3;
  --border-strong: #c8c0b0;

  /* Accent */
  --accent: #ff5b35;
  --accent-text: #faf7f2;

  /* Semantic */
  --pos: #2e8b2e;
  --neg: #d94524;
  --neu: #6b6760;
  --warn: #d97706;
}
```

### Color rules

- **Cards invert.** In dark mode, cards have cream backgrounds. In light mode, cards have dark backgrounds. This is the signature visual decision — keep it.
- **Accent is one hue only.** Burnt orange (`#ff5b35`). Used on: serif italic emphasis in titles, scope picker active state, CTA button, negative sentiment, hover on chart slices. Never introduce a second accent color.
- **Semantic colors are not decoration.** `--pos`/`--neg`/`--neu` only on actual sentiment data. Don't use `--pos` for success messages — use `--fg` or the card-action neutral style.
- **Opacity, not new colors.** When you need a fainter version of text-on-card, use `rgba(0,0,0,0.08)` for borders or `opacity: 0.6` for muted text. Don't introduce mid-tone tokens.

---

## Spacing

8px base scale.

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
--space-20: 80px;
```

### Spacing rules

- **Inside cards:** padding `var(--space-12)` (48px) on desktop, `var(--space-6)` (24px) on mobile.
- **Between cards:** `var(--space-8)` (32px) margin-bottom.
- **Between sidebar sections:** `var(--space-9)` (36px) — use 32px.
- **Inline list items:** gap `var(--space-3)` (12px) for tight lists, `var(--space-5)` (20px) for breathing.
- **Main content padding:** `var(--space-16)` (64px) top, `var(--space-20)` (80px) bottom.
- **Sidebar padding:** `var(--space-8)` (32px) all sides.

---

## Radius & borders

```css
--radius-sm: 4px;
--radius-md: 6px;
--radius-lg: 8px;
--radius-xl: 12px;
```

### Radius rules

- **Cards: 0px (sharp corners).** This is editorial — no rounded cards. This is the signature visual decision — keep it.
- **Buttons, inputs, badges:** `var(--radius-sm)` (4px). Subtle, not pillowy.
- **Modals:** `var(--radius-md)` (6px). Slightly softer than cards.
- **Charts/word cloud containers within cards:** 0px (inherit card sharpness).
- **Border width is always 1px.** No thick borders. Borders use `var(--border)`; emphasize with `var(--border-strong)` on hover, never with width.

---

## Shadows

Used minimally. We're not skeuomorphic.

```css
--shadow-modal: 0 24px 48px rgba(0, 0, 0, 0.4);
--shadow-modal-light: 0 24px 48px rgba(0, 0, 0, 0.15);
```

- **Cards have no shadow.** Use border-only.
- **Only modals get shadow.** Use `--shadow-modal` in dark, `--shadow-modal-light` in light.
- **Hover states never add shadow.** Use border color change or background.

---

## Component patterns

### Card

The fundamental unit. Every analysis card follows this structure.

```html
<article class="card">
  <header class="card-header">
    <div>
      <div class="card-num">01 / 04</div>
      <h2 class="card-title">Sentiment <em>breakdown</em></h2>
      <div class="card-sub">As classified by the model</div>
    </div>
  </header>

  <div class="card-body">
    <!-- analysis-specific content -->
  </div>

  <footer class="card-footer">
    <div>Classified by <code>model-name</code> · not absolute truth</div>
    <div class="card-actions">
      <button class="card-action">⤓ Export PNG</button>
      <button class="card-action">5 random samples</button>
    </div>
  </footer>
</article>
```

**Card rules:**
- Always cream background in dark mode (inverted).
- Always padding `var(--space-12)` (48px).
- `card-num` is `var(--text-meta-sm)` mono. Format: `XX / YY` (e.g. `01 / 04`).
- `card-title` is `var(--text-display-lg)` with italic accent on one word.
- `card-sub` is `var(--text-meta-sm)`, optional.
- Always has a `card-footer` with at minimum a metadata line and an export button.
- Footer separator: 1px solid `rgba(0,0,0,0.08)` (in dark mode card; flip for light).

### Button hierarchy

Three levels only.

```html
<!-- Primary CTA. One per page. Used for "Run Analysis" in sidebar. -->
<button class="cta">Run Analysis →</button>

<!-- Secondary. Outline style. Used for refresh, navigate. -->
<button class="refresh-btn">↻ Refresh</button>

<!-- Tertiary. Inside cards. Used for export, modal triggers. -->
<button class="card-action">⤓ Export PNG</button>
```

**Button rules:**
- Never more than one `.cta` visible at once.
- All button text is `var(--text-meta)` uppercase mono — even CTAs.
- All buttons have arrow/icon glyphs (`→`, `↻`, `⤓`) — not lucide icons. Keep it editorial-typographic.
- Hover: `transform: translateY(-1px)` for CTA, color change for secondary/tertiary. No background change for tertiary unless explicitly designed.

### Sidebar

Fixed-width 320px on desktop. Collapses to top sheet on mobile (breakpoint 768px).

```html
<aside class="sidebar">
  <div class="brand">
    <div>
      <div class="brand-mark">Pulse<span class="dot">.</span></div>
      <div class="brand-sub">IG Comment Analytics</div>
    </div>
  </div>

  <div class="scope-group">
    <div class="section-label">Scope</div>
    <div class="scope-options">
      <!-- radio-style scope options -->
    </div>
  </div>

  <button class="cta">Run Analysis →</button>

  <div class="sidebar-foot">
    <!-- account info, token status -->
  </div>
</aside>
```

**Sidebar rules:**
- Always sticky top.
- Always shows: brand, scope picker, CTA, account info.
- Theme toggle is fixed bottom-right of viewport, not in sidebar.
- Section labels (`section-label`) use accent line + uppercase mono.

### Modal

Used for: sentiment samples, export options, expanded views.

```html
<div class="modal-overlay" data-modal>
  <div class="modal">
    <header class="modal-header">
      <h3 class="modal-title">Positive comments <em>(5 random)</em></h3>
      <button class="modal-close" aria-label="Close">×</button>
    </header>
    <div class="modal-body">
      <!-- content -->
    </div>
    <footer class="modal-footer">
      <button class="card-action">Show 5 more</button>
    </footer>
  </div>
</div>
```

**Modal rules:**
- Overlay: `rgba(0, 0, 0, 0.6)` with `backdrop-filter: blur(4px)` if supported.
- Modal max-width: 640px on desktop, 100% with 16px margin on mobile.
- Modal background: same as card (cream in dark, dark in light).
- Close on overlay click + Esc key.
- Open animation: opacity fade + scale 0.96 → 1.0 over 180ms ease-out.
- Body scrolls if content exceeds 70vh.

### Badge / pill

For status indicators (token expiry, sentiment label inline, etc.)

```html
<span class="badge badge-warn">47 days left</span>
<span class="badge badge-pos">positive</span>
```

- Padding `2px 8px`, radius `var(--radius-sm)`, `var(--text-meta-sm)`.
- Background: 12% opacity of semantic color. Text: full semantic color.
- Example: `background: rgba(92, 184, 92, 0.12); color: var(--pos);` for positive.

### Chart container (Plotly)

```html
<div class="chart-wrap">
  <!-- Plotly injects HTML+JS here -->
</div>
```

- Background transparent — let card background show through.
- Plotly font config: family Lora, color matches card text color.
- Plotly grid lines: `rgba(0,0,0,0.06)` in dark mode card, flip for light.
- Disable Plotly mode bar (`displayModeBar: false`) — distracting on screenshots.

### Word cloud (PNG)

Generated server-side by Python `wordcloud` library, embedded as `<img>`.

```html
<img class="wordcloud" src="/api/wordcloud/{scope_id}.png" alt="Word cloud">
```

- Width: 100% of card column.
- `wordcloud` library config: background transparent, font path to Lora .ttf, color function returns shades of `--bg-card-text`.

---

## States (universal across all cards)

Every analysis card cycles through these states. Implement them consistently.

### Empty (no scope selected)

Card is collapsed to header + this body:

```
[card-num]
[card-title]
─────────────
Pick a scope to start analyzing.
```

Body: `var(--text-body)`, color `var(--fg-muted)` (or card-text equivalent), centered, padding 64px vertical.

### Loading (fetching/analyzing)

Skeleton: card-header is real, card-body is replaced with:
- 3 pulsing rectangles of varying widths (60%, 80%, 40%)
- Each `height: 16px`, `border-radius: var(--radius-sm)`, background `rgba(0,0,0,0.06)` in dark mode card
- Animation: `pulse 1.6s ease-in-out infinite` (opacity 0.4 → 1.0 → 0.4)

### Ready (data rendered)

Default state. As shown in wireframes.

### Error (fetch or analysis failed)

```
[card-num]
[card-title]
─────────────
Couldn't load this analysis.
[ Try again ]
```

Body centered, `var(--text-body)` for message, retry button is `.card-action`. Each card's error state is independent — don't break the page.

---

## Responsive behavior

Two breakpoints, no more.

- **< 768px (mobile):**
  - Sidebar collapses to bottom sheet OR top accordion (let Claude Code pick — bottom sheet is more native-feeling).
  - Main padding reduces to `var(--space-4)` (16px).
  - Card padding reduces to `var(--space-6)` (24px).
  - Hero title scales to `--text-display-xl` (56px).
  - Card-body grids collapse to single column.
  - Type scale ratchets down one step (e.g. hero from 72→56, card-title from 40→32).

- **>= 768px (desktop):**
  - Full sidebar visible.
  - Two-column card bodies allowed.

No tablet breakpoint. Mobile and desktop are the only two states we design for. Tablets get desktop layout.

---

## Animation & motion

Minimal. Editorial publications don't bounce.

- **Theme transition:** `transition: background 0.3s ease, color 0.3s ease;` on `html, body`.
- **Hover transitions:** 150ms ease.
- **Button micro-interaction:** `transform: translateY(-1px)` on CTA hover.
- **Modal open:** 180ms ease-out (opacity + scale).
- **Skeleton pulse:** 1600ms ease-in-out infinite.
- **HTMX swap fade:** 150ms ease. Set via `htmx-swapping` and `htmx-settling` classes.

**Never animate:** chart data on initial load, sentiment percentages, hover-rotate, parallax, scroll-triggered reveals. Restraint.

---

## Iconography

- **Glyphs preferred over icon library.** Use Unicode arrows (`→ ← ↑ ↓ ↗ ↘ ↻`), bullets (`· • ◆ ●`), download (`⤓`), close (`×`).
- **If lucide-react is already in the project**, use it sparingly: only for: refresh, close, search. All other "icons" stay as Unicode glyphs in the typography.
- **No emoji as UI element.** Emoji belong in comment data, not in chrome.

---

## What this design system does NOT cover

These are intentionally outside the scope of this doc — make decisions as they come up:

- Mobile sidebar pattern (bottom sheet vs. top accordion) — pick one when you implement
- Tooltips (avoid where possible; use captions in body)
- Form inputs beyond scope picker (deferred to when first needed)
- Toast notifications (use inline messaging in card-error state instead)
- Drag-and-drop (not in MVP)
- Pagination (not in MVP — all-or-sample)

---

## How to use this with Claude Code

When implementing a new view:

1. **Start from `design-system.md` (this file)** — open it, identify which tokens/components apply.
2. **Reference the wireframe** if one exists (`reference-sentiment-wordfreq.html`, `reference-timetrend.html`, `reference-modal.html`).
3. **For analyses not yet wireframed** (n-gram phrases, etc.), apply the card pattern + use the analogous wireframe (e.g. n-gram looks like sentiment's stat-row pattern with bigrams as items).
4. **For states not yet wireframed** (empty, loading, error), apply the universal patterns above.
5. **If you must deviate**, document why in a comment and ask before merging.

Do not introduce new tokens, new component patterns, new fonts, or new animations without consulting this doc first. Doing so violates Karpathy Part A "Simplicity First" and Part B B1 "Scope discipline."
