"""Server-side SVG generators for the editorial dashboard cards.

On-screen charts are hand-built SVG (not Plotly) so they recolor instantly with
the theme — strokes/fills reference CSS custom properties (var(--pos), etc.).
Pure functions returning SVG markup; numbers only, no user content (XSS-safe).
"""

from __future__ import annotations

import math

_R = 40.0
_C = 2 * math.pi * _R  # donut circumference (~251.33)

# distribution key -> (css color var, draw order)
_SENT = [
    ("neutral", "var(--neu)"),
    ("positive", "var(--pos)"),
    ("negative", "var(--neg)"),
    ("unanalyzed", "var(--fg-subtle)"),
]


def sentiment_donut_svg(dist: dict[str, int], size: int = 280) -> str:
    """Donut chart of the sentiment distribution. Empty dist -> ''."""
    total = sum(dist.values())
    if total == 0:
        return ""
    circles: list[str] = []
    offset = 0.0
    for key, color in _SENT:
        count = dist.get(key, 0)
        if count <= 0:
            continue
        arc = count / total * _C
        circles.append(
            f'<circle cx="50" cy="50" r="40" fill="none" style="stroke:{color}" '
            f'stroke-width="14" stroke-dasharray="{arc:.2f} {_C:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 50 50)"/>'
        )
        offset += arc
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" '
        f'role="img" aria-label="Donat sentimen">' + "".join(circles) + "</svg>"
    )


_TREND_LAYERS = [
    ("pos", "var(--pos)", 0.7),
    ("neu", "var(--neu)", 0.55),
    ("neg", "var(--neg)", 0.7),
    ("unanalyzed", "var(--fg-subtle)", 0.35),
]


def timetrend_area_svg(rows: list[dict], width: int = 800, height: int = 280) -> str:
    """Stacked area (pos/neu/neg/unanalyzed) + total line over days. Empty -> ''."""
    n = len(rows)
    if n == 0:
        return ""
    totals = [r["total"] for r in rows]
    max_total = max(totals) or 1
    top, bottom = 28.0, float(height)
    usable = bottom - top
    left, right = 40.0, float(width - 16)
    span = (right - left) or 1.0

    def px(i: int) -> float:
        return left if n == 1 else left + i * (span / (n - 1))

    def py(v: float) -> float:
        return bottom - (v / max_total) * usable

    parts: list[str] = []
    # gridlines + y labels at 1/3, 2/3, full
    for frac in (1 / 3, 2 / 3, 1.0):
        gy = py(max_total * frac)
        parts.append(
            f'<line x1="{left:.0f}" y1="{gy:.1f}" x2="{right:.0f}" y2="{gy:.1f}" '
            f'style="stroke:var(--on-card-line)" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="4" y="{gy - 3:.1f}" font-family="JetBrains Mono" font-size="9" '
            f'fill="currentColor" opacity="0.5" font-weight="600">{round(max_total * frac)}</text>'
        )
    # stacked areas
    cum = [0.0] * n
    for key, color, op in _TREND_LAYERS:
        new_cum = [cum[i] + rows[i].get(key, 0) for i in range(n)]
        if sum(rows[i].get(key, 0) for i in range(n)) > 0 and n >= 2:
            top_pts = " ".join(f"{px(i):.1f},{py(new_cum[i]):.1f}" for i in range(n))
            bot_pts = " ".join(f"{px(i):.1f},{py(cum[i]):.1f}" for i in range(n - 1, -1, -1))
            parts.append(
                f'<polygon points="{top_pts} {bot_pts}" style="fill:{color}" fill-opacity="{op}"/>'
            )
        cum = new_cum
    # total line
    if n >= 2:
        line_pts = " ".join(f"{px(i):.1f},{py(totals[i]):.1f}" for i in range(n))
        parts.append(
            f'<polyline points="{line_pts}" fill="none" style="stroke:var(--bg-card-text)" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        )
    return (
        f'<svg class="chart-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'role="img" aria-label="Volume komentar dari waktu ke waktu">' + "".join(parts) + "</svg>"
    )
