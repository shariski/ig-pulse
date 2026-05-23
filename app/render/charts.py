"""Plotly figure builders for the export PNGs (B7, B9).

Styled to the editorial design system so downloaded images echo the on-screen
cream cards: cream paper, dark serif text, semantic palette. (On-screen charts
are SVG in app/render/svg.py; these Plotly figures are only used for export.)
"""

import plotly.graph_objects as go

# Design palette (matches docs/design/design-system.md). Exports always use the
# dark-mode card look: cream surface, dark ink.
_BG = "#faf7f2"
_TEXT = "#1a1815"
_GRID = "rgba(0,0,0,0.08)"
_ACCENT = "#ff5b35"
_FONT = "Lora, Georgia, 'Times New Roman', serif"
_MONO = "JetBrains Mono, monospace"

_COLORS = {
    "positive": "#5cb85c",
    "negative": "#ff5b35",
    "neutral": "#a8a39a",
    "unanalyzed": "#6b6760",
}
_FILL = {
    "positive": "rgba(92, 184, 92, 0.65)",
    "negative": "rgba(255, 91, 53, 0.65)",
    "neutral": "rgba(168, 163, 154, 0.55)",
}

_ID_LABELS = {
    "positive": "Positif",
    "negative": "Negatif",
    "neutral": "Netral",
    "unanalyzed": "Belum dianalisis",
}

_EMPTY_ANNOTATION = dict(
    text="Belum ada data",
    x=0.5, y=0.5, xref="paper", yref="paper",
    showarrow=False, font=dict(family=_FONT, size=18, color="#6b6760"),
)


def _theme(fig: go.Figure, title: str, axes: bool = True) -> go.Figure:
    """Apply the editorial layout (cream surface, serif ink) to any figure."""
    fig.update_layout(
        title=dict(
            text=title, font=dict(family=_FONT, size=24, color=_TEXT), x=0.015, xanchor="left"
        ),
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(family=_FONT, color=_TEXT, size=15),
        margin=dict(l=50, r=30, t=72, b=48),
        legend=dict(font=dict(family=_MONO, size=11), bgcolor="rgba(0,0,0,0)"),
    )
    if axes:
        common = dict(gridcolor=_GRID, linecolor=_GRID, zeroline=False,
                      tickfont=dict(family=_MONO, size=11),
                      title_font=dict(family=_MONO, size=11))
        fig.update_xaxes(**common)
        fig.update_yaxes(**common)
    return fig


def sentiment_pie(distribution: dict[str, int]) -> go.Figure:
    """Donut chart of the sentiment distribution. Empty/all-zero -> annotated."""
    filtered = {k: v for k, v in distribution.items() if v > 0}
    fig = go.Figure()
    if not filtered:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        return _theme(fig, "Distribusi Sentimen (menurut model)", axes=False)

    labels = list(filtered.keys())
    fig.add_trace(go.Pie(
        labels=[_ID_LABELS.get(k, k) for k in labels],
        values=list(filtered.values()),
        hole=0.45,
        marker=dict(colors=[_COLORS.get(k, "#bdc3c7") for k in labels],
                    line=dict(color=_BG, width=3)),
        textinfo="label+percent",
        textfont=dict(family=_FONT, size=15, color=_TEXT),
        hovertemplate="%{label}: %{value} komentar<extra></extra>",
    ))
    fig.update_layout(showlegend=True)
    return _theme(fig, "Distribusi Sentimen (menurut model)", axes=False)


def timetrend_line(rows: list[dict]) -> go.Figure:
    """Total line over a stacked pos/neu/neg area, daily, WIB."""
    fig = go.Figure()
    if not rows:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        fig.update_layout(xaxis_title="Tanggal (WIB)", yaxis_title="Jumlah Komentar")
        return _theme(fig, "Tren Komentar Harian (WIB)")

    dates = [r["date"] for r in rows]
    # trace 0 = total line (dark); traces 1-3 = stacked sentiment areas.
    fig.add_trace(go.Scatter(
        x=dates, y=[r["total"] for r in rows], mode="lines", name="Total",
        line=dict(color=_TEXT, width=2),
        hovertemplate="%{x}: %{y} komentar<extra>Total</extra>",
    ))
    for key, ck, name in [("pos", "positive", "Positif"),
                          ("neg", "negative", "Negatif"),
                          ("neu", "neutral", "Netral")]:
        fig.add_trace(go.Scatter(
            x=dates, y=[r.get(key, 0) for r in rows], mode="lines", name=name,
            stackgroup="sentiment", line=dict(width=0.5, color=_COLORS[ck]),
            fillcolor=_FILL[ck],
            hovertemplate="%{x}: %{y}<extra>" + name + "</extra>",
        ))

    fig.update_layout(xaxis_title="Tanggal (WIB)", yaxis_title="Jumlah Komentar",
                      legend_title="Kategori", hovermode="x unified")
    return _theme(fig, "Tren Komentar Harian (WIB)")


def phrase_bar(phrases: list[tuple[str, int]]) -> go.Figure:
    """Horizontal bar of dominant phrases (accent), highest at top."""
    fig = go.Figure()
    if not phrases:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        fig.update_layout(xaxis_title="Frekuensi", yaxis_title="Frasa")
        return _theme(fig, "Frasa Dominan")

    fig.add_trace(go.Bar(
        x=[p[1] for p in reversed(phrases)],
        y=[p[0] for p in reversed(phrases)],
        orientation="h", marker_color=_ACCENT,
        hovertemplate="%{y}: %{x} kali<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Frekuensi", yaxis_title="Frasa", margin=dict(l=170))
    return _theme(fig, "Frasa Dominan")


def word_freq_bar(freqs: list[tuple[str, int]], top_n: int = 20) -> go.Figure:
    """Horizontal bar of top_n words (dark ink), highest at top."""
    fig = go.Figure()
    if not freqs:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        fig.update_layout(xaxis_title="Frekuensi", yaxis_title="Kata")
        return _theme(fig, "Frekuensi Kata")

    subset = freqs[:top_n]
    fig.add_trace(go.Bar(
        x=[w[1] for w in reversed(subset)],
        y=[w[0] for w in reversed(subset)],
        orientation="h", marker_color=_TEXT,
        hovertemplate="%{y}: %{x} kali<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Frekuensi", yaxis_title="Kata", margin=dict(l=130))
    return _theme(fig, "Frekuensi Kata")


def fig_to_html(fig: go.Figure) -> str:
    """Embeddable HTML string (B7); mode bar disabled per design-system."""
    return fig.to_html(include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False})
