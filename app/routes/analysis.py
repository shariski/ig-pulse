"""HTMX analysis fragments: one chart per card, plus the sentiment sample modal.

Each fragment is self-contained and fails independently (B6): an error in one
card renders an inline error message, never breaks the others. All read from
SQLite (source of truth, B5); no API calls here.
"""

from __future__ import annotations

import base64
import io
import logging
import random
from collections import Counter

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.analysis import phrases, timetrend, wordfreq
from app.db import connect, get_comments_in_scope
from app.models import Post
from app.render import charts
from app.render import wordcloud as wc_render
from app.templating import templates

router = APIRouter()
logger = logging.getLogger("ig_pulse.routes.analysis")


def scope_data(scope_type: str, scope_value: str | None):
    """Load comments for a scope + a {comment_id: sentiment_label} map."""
    conn = connect()
    try:
        comments = get_comments_in_scope(conn, scope_type, scope_value)
        analyses = {
            r["comment_id"]: r["sentiment_label"]
            for r in conn.execute("SELECT comment_id, sentiment_label FROM comment_analysis")
        }
        return comments, analyses
    finally:
        conn.close()


def plotly_html(fig) -> str:
    # Plotly is loaded once globally in base.html, so fragments embed without it.
    return fig.to_html(include_plotlyjs=False, full_html=False)


def _empty(msg: str) -> HTMLResponse:
    return HTMLResponse(
        f'<p style="text-align:center;color:var(--pico-muted-color);padding:2rem;">{msg}</p>'
    )


def _error(msg: str) -> HTMLResponse:
    return HTMLResponse(
        f'<p role="alert" style="color:var(--pico-del-color);padding:1rem;">⚠️ {msg}</p>'
    )


@router.get("/analysis/sentiment", response_class=HTMLResponse)
def sentiment_fragment(scope_type: str = "all", scope_value: str | None = None):
    try:
        comments, analyses = scope_data(scope_type, scope_value)
        if not comments:
            return _empty("Belum ada komentar pada cakupan ini.")
        dist = Counter(analyses.get(c.id, "unanalyzed") for c in comments)
        return HTMLResponse(plotly_html(charts.sentiment_pie(dict(dist))))
    except Exception:
        logger.exception("sentiment fragment failed")
        return _error("Gagal memuat sentimen.")


@router.get("/analysis/wordfreq", response_class=HTMLResponse)
def wordfreq_fragment(scope_type: str = "all", scope_value: str | None = None):
    try:
        comments, _ = scope_data(scope_type, scope_value)
        if not comments:
            return _empty("Belum ada komentar pada cakupan ini.")
        freqs = wordfreq.word_frequencies(comments, 100)
        if not freqs:
            return _empty("Tidak ada kata tersisa setelah penyaringan stopword.")
        img = wc_render.render_wordcloud(freqs)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        bar = plotly_html(charts.word_freq_bar(freqs, 20))
        return HTMLResponse(
            f'<img src="{data_uri}" alt="Word cloud" '
            'style="width:100%;height:auto;border-radius:8px;margin-bottom:1rem;" />' + bar
        )
    except Exception:
        logger.exception("wordfreq fragment failed")
        return _error("Gagal memuat frekuensi kata.")


@router.get("/analysis/timetrend", response_class=HTMLResponse)
def timetrend_fragment(scope_type: str = "all", scope_value: str | None = None):
    try:
        comments, analyses = scope_data(scope_type, scope_value)
        if not comments:
            return _empty("Belum ada komentar pada cakupan ini.")
        rows = timetrend.daily_trend(comments, analyses)
        return HTMLResponse(plotly_html(charts.timetrend_line(rows)))
    except Exception:
        logger.exception("timetrend fragment failed")
        return _error("Gagal memuat tren waktu.")


@router.get("/analysis/phrases", response_class=HTMLResponse)
def phrases_fragment(scope_type: str = "all", scope_value: str | None = None):
    try:
        comments, _ = scope_data(scope_type, scope_value)
        if not comments:
            return _empty("Belum ada komentar pada cakupan ini.")
        ph = phrases.top_phrases(comments)
        if not ph:
            return _empty("Belum ada frasa yang muncul ≥ 3 kali pada cakupan ini.")
        return HTMLResponse(plotly_html(charts.phrase_bar(ph)))
    except Exception:
        logger.exception("phrases fragment failed")
        return _error("Gagal memuat frasa dominan.")


@router.get("/analysis/sentiment/sample", response_class=HTMLResponse)
def sentiment_sample(
    request: Request,
    bucket: str = "positive",
    n: int = 5,
    scope_type: str = "all",
    scope_value: str | None = None,
):
    conn = connect()
    try:
        comments = get_comments_in_scope(conn, scope_type, scope_value)
        analyses = {
            r["comment_id"]: r["sentiment_label"]
            for r in conn.execute("SELECT comment_id, sentiment_label FROM comment_analysis")
        }
        posts = {p.id: p for p in (Post.from_row(r) for r in conn.execute("SELECT * FROM posts"))}
    finally:
        conn.close()

    matching = [c for c in comments if analyses.get(c.id, "unanalyzed") == bucket]
    sample = random.sample(matching, min(n, len(matching)))
    return templates.TemplateResponse(
        request,
        "partials/_sample_modal.html",
        {
            "bucket": bucket,
            "comments": sample,
            "posts": posts,
            "total": len(matching),
            "scope_qs": f"scope_type={scope_type}"
            + (f"&scope_value={scope_value}" if scope_value else ""),
        },
    )
