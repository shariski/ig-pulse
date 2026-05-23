"""Plotly figure builders for IG Pulse dashboard (B7, B9)."""

import plotly.graph_objects as go

# Consistent sentiment colours
_COLORS = {
    "positive": "#2ecc71",    # green
    "negative": "#e74c3c",    # red
    "neutral": "#95a5a6",     # gray
    "unanalyzed": "#d5d8dc",  # light gray
}

_ID_LABELS = {
    "positive": "Positif",
    "negative": "Negatif",
    "neutral": "Netral",
    "unanalyzed": "Belum dianalisis",
}

_EMPTY_ANNOTATION = dict(
    text="Belum ada data",
    x=0.5, y=0.5,
    xref="paper", yref="paper",
    showarrow=False,
    font=dict(size=16, color="#888888"),
)


def sentiment_pie(distribution: dict[str, int]) -> go.Figure:
    """Donut chart of sentiment distribution.

    Keys expected among: positive, negative, neutral, unanalyzed.
    Returns an annotated empty figure when distribution is empty or all-zero.
    """
    filtered = {k: v for k, v in distribution.items() if v > 0}

    fig = go.Figure()

    if not filtered:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        fig.update_layout(
            title="Distribusi Sentimen (menurut model)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        return fig

    labels = list(filtered.keys())
    values = list(filtered.values())
    id_labels = [_ID_LABELS.get(k, k) for k in labels]
    colors = [_COLORS.get(k, "#bdc3c7") for k in labels]

    fig.add_trace(go.Pie(
        labels=id_labels,
        values=values,
        hole=0.4,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} komentar<extra></extra>",
    ))

    fig.update_layout(
        title="Distribusi Sentimen (menurut model)",
        showlegend=True,
    )
    return fig


def timetrend_line(rows: list[dict]) -> go.Figure:
    """Line chart of daily comment volume with per-sentiment breakdown.

    Each row must have keys: date, total, pos, neg, neu, unanalyzed.
    x-axis is date; time is WIB (Asia/Jakarta).
    """
    fig = go.Figure()

    if not rows:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        fig.update_layout(
            title="Tren Komentar Harian (WIB)",
            xaxis_title="Tanggal (WIB)",
            yaxis_title="Jumlah Komentar",
        )
        return fig

    dates = [r["date"] for r in rows]

    fig.add_trace(go.Scatter(
        x=dates,
        y=[r["total"] for r in rows],
        mode="lines+markers",
        name="Total",
        line=dict(color="#2c3e50", width=2),
        hovertemplate="%{x}: %{y} komentar<extra>Total</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=[r["pos"] for r in rows],
        mode="lines",
        name="Positif",
        line=dict(color=_COLORS["positive"], dash="dot"),
        hovertemplate="%{x}: %{y}<extra>Positif</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=[r["neg"] for r in rows],
        mode="lines",
        name="Negatif",
        line=dict(color=_COLORS["negative"], dash="dot"),
        hovertemplate="%{x}: %{y}<extra>Negatif</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=[r["neu"] for r in rows],
        mode="lines",
        name="Netral",
        line=dict(color=_COLORS["neutral"], dash="dot"),
        hovertemplate="%{x}: %{y}<extra>Netral</extra>",
    ))

    fig.update_layout(
        title="Tren Komentar Harian (WIB)",
        xaxis_title="Tanggal (WIB)",
        yaxis_title="Jumlah Komentar",
        legend_title="Kategori",
        hovermode="x unified",
    )
    return fig


def phrase_bar(phrases: list[tuple[str, int]]) -> go.Figure:
    """Horizontal bar chart of dominant phrases, highest at top.

    Input is already sorted descending by count.
    """
    fig = go.Figure()

    if not phrases:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        fig.update_layout(
            title="Frasa Dominan",
            xaxis_title="Frekuensi",
            yaxis_title="Frasa",
        )
        return fig

    # Reverse so highest is at top in horizontal bar
    labels = [p[0] for p in reversed(phrases)]
    counts = [p[1] for p in reversed(phrases)]

    fig.add_trace(go.Bar(
        x=counts,
        y=labels,
        orientation="h",
        marker_color="#3498db",
        hovertemplate="%{y}: %{x} kali<extra></extra>",
    ))

    fig.update_layout(
        title="Frasa Dominan",
        xaxis_title="Frekuensi",
        yaxis_title="Frasa",
        margin=dict(l=160),
    )
    return fig


def word_freq_bar(freqs: list[tuple[str, int]], top_n: int = 20) -> go.Figure:
    """Horizontal bar chart of top_n word frequencies, highest at top.

    Input is already sorted descending by count; top_n is applied here.
    """
    fig = go.Figure()

    if not freqs:
        fig.add_annotation(**_EMPTY_ANNOTATION)
        fig.update_layout(
            title="Frekuensi Kata",
            xaxis_title="Frekuensi",
            yaxis_title="Kata",
        )
        return fig

    subset = freqs[:top_n]
    labels = [w[0] for w in reversed(subset)]
    counts = [w[1] for w in reversed(subset)]

    fig.add_trace(go.Bar(
        x=counts,
        y=labels,
        orientation="h",
        marker_color="#9b59b6",
        hovertemplate="%{y}: %{x} kali<extra></extra>",
    ))

    fig.update_layout(
        title="Frekuensi Kata",
        xaxis_title="Frekuensi",
        yaxis_title="Kata",
        margin=dict(l=120),
    )
    return fig


def fig_to_html(fig: go.Figure) -> str:
    """Render a Plotly figure to an embeddable HTML string (B7).

    Uses CDN for plotly.js — no inline bundle, no full HTML page.
    """
    return fig.to_html(include_plotlyjs="cdn", full_html=False)
