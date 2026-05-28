"""HTMX analysis fragments (editorial cards) + the sentiment sample modal.

On-screen charts are hand-built HTML/SVG (theme-reactive), not Plotly. Each
fragment fails independently (B6): an error renders an inline retry, never breaks
the page. All reads from SQLite (B5); no API calls.
"""

from __future__ import annotations

import logging
import random
import re
from collections import Counter
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app import auth
from app.analysis import phrases as phrases_mod
from app.analysis import timetrend, wordfreq
from app.analysis.tokenize import tokenize
from app.analysis.user_stopwords import (
    add_user_stopword,
    list_user_stopwords,
    remove_user_stopword,
)
from app.config import settings
from app.db import connect, get_comments_in_scope
from app.models import Post
from app.render import svg
from app.templating import templates

router = APIRouter()
logger = logging.getLogger("ig_pulse.routes.analysis")

_ID_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
              "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
_BUCKETS = {
    "positive": ("positif", "pos"),
    "negative": ("negatif", "neg"),
    "neutral": ("netral", "neu"),
    "unanalyzed": ("belum dianalisis", "neu"),
}

# Whitelist: word characters + the emoji ranges tokenize() recognises.
_WORD_PARAM_RE = re.compile(
    r"^["
    r"\w"
    r"⌀-⏿"
    r"☀-➿"
    r"⬀-⯿"
    r"\U0001F300-\U0001FAFF"
    r"\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FAFF"
    r"]+$"
)


def _validate_word_param(word: str) -> str | HTMLResponse:
    """Normalise + whitelist-validate. Returns the cleaned word or a 400 HTMLResponse."""
    normalised = word.strip().lower()[:50]
    if not normalised or not _WORD_PARAM_RE.match(normalised):
        return HTMLResponse(
            "<div class='error'>Kata tidak valid.</div>", status_code=400,
        )
    return normalised


def _scope_qs(scope_type: str, scope_value: str | None, exclude_self: bool = False) -> str:
    qs = f"scope_type={scope_type}" + (f"&scope_value={scope_value}" if scope_value else "")
    return qs + ("&exclude_self=1" if exclude_self else "")


def drop_self(comments: list, exclude_self: bool, self_handle: str | None) -> list:
    """Optionally drop the account owner's own comments/replies (self-interactions),
    so the creator's own activity doesn't skew the audience stats. Opt-in toggle."""
    if not (exclude_self and self_handle):
        return comments
    sh = self_handle.lower()
    return [c for c in comments if (c.author_handle or "").lower() != sh]


def scope_data(
    db_path: str,
    scope_type: str,
    scope_value: str | None,
    *,
    exclude_self: bool = False,
    self_handle: str | None = None,
):
    """Load comments for a scope + a {comment_id: sentiment_label} map.

    When ``exclude_self`` is set, the owner's own comments (author == ``self_handle``)
    are filtered out so they don't count toward any stat.
    """
    conn = connect(db_path)
    try:
        comments = drop_self(
            get_comments_in_scope(conn, scope_type, scope_value), exclude_self, self_handle
        )
        analyses = {
            r["comment_id"]: r["sentiment_label"]
            for r in conn.execute("SELECT comment_id, sentiment_label FROM comment_analysis")
        }
        return comments, analyses
    finally:
        conn.close()


def _id_date(iso_date: str) -> str:
    """'2025-05-17' -> '17 Mei 2025'."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        return f"{d.day} {_ID_MONTHS[d.month]} {d.year}"
    except ValueError:
        return iso_date


def _id_datetime(ts: str) -> str:
    """IG timestamp -> '17 Mei 2025 · 14:23' in WIB."""
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        try:
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return ts
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(ZoneInfo(settings.timezone))
    return f"{dt.day} {_ID_MONTHS[dt.month]} {dt.year} · {dt:%H:%M}"


def _empty(msg: str) -> HTMLResponse:
    return HTMLResponse(f'<div class="state-empty">{msg}</div>')


def _error(retry_url: str, msg: str = "Gagal memuat analisis ini.") -> HTMLResponse:
    return HTMLResponse(
        f'<div class="state-error"><div>⚠️ {msg}</div>'
        f'<button class="card-action" hx-get="{retry_url}" '
        f'hx-target="closest .card-body" hx-swap="innerHTML">Coba lagi</button></div>'
    )


@router.get("/analysis/sentiment", response_class=HTMLResponse)
def sentiment_fragment(
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    account=auth.current_account,
):
    try:
        comments, analyses = scope_data(
            account["db_path"], scope_type, scope_value,
            exclude_self=exclude_self, self_handle=account["username"],
        )
        if not comments:
            return _empty("Belum ada komentar pada cakupan ini.")
        total = len(comments)
        dist = Counter(analyses.get(c.id, "unanalyzed") for c in comments)
        stats = [
            {"cls": cls, "bucket": b, "label": lbl, "count": dist.get(b, 0),
             "pct": round(dist.get(b, 0) / total * 100)}
            for b, lbl, cls in [("positive", "Positif", "positive"),
                                ("neutral", "Netral", "neutral"),
                                ("negative", "Negatif", "negative")]
        ]
        return templates.TemplateResponse(request, "partials/frag_sentiment.html", {
            "stats": stats,
            "donut_svg": svg.sentiment_donut_svg(dict(dist)),
            "classified": total - dist.get("unanalyzed", 0),
            "scope_qs": _scope_qs(scope_type, scope_value, exclude_self),
        })
    except Exception:
        logger.exception("sentiment fragment failed")
        return _error(str(request.url))


@router.get("/analysis/wordfreq", response_class=HTMLResponse)
def wordfreq_fragment(
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    try:
        comments, analyses = scope_data(
            account["db_path"], scope_type, scope_value,
            exclude_self=exclude_self, self_handle=account["username"],
        )
        # Sentiment filter (B4: still using the sentiment model — caveat
        # surfaces in the modal header at render time).
        if sentiment in ("positive", "neutral", "negative"):
            comments = [c for c in comments if analyses.get(c.id) == sentiment]
        elif sentiment != "all":
            # Unknown bucket value -> ignore, treat as "all". Don't 400; HTMX
            # users can land here via a stale URL.
            sentiment = "all"

        if not comments:
            return _empty("Tidak ada komentar pada cakupan ini.")

        exclude_words = {w.strip().lower()[:50] for w in exclude if w and w.strip()}
        freqs = wordfreq.word_frequencies(comments, 100, exclude_words=exclude_words or None)
        if not freqs:
            return _empty(
                "Semua kata teratas dikecualikan. Hapus chip di atas untuk melihat hasil."
                if exclude_words else
                "Tidak ada kata tersisa setelah penyaringan stopword."
            )

        cloud_words = []
        for i, (word, _count) in enumerate(freqs[:16]):
            cls = "s1" if i == 0 else "s2" if i < 4 else "s3" if i < 8 else "s4" if i < 12 else "s5"
            cloud_words.append({"word": word, "cls": cls})
        top_items = [{"rank": i + 1, "word": w, "count": c} for i, (w, c) in enumerate(freqs[:10])]

        logger.info(
            "wordfreq scope=%s/%s sentiment=%s excludes=%d results=%d",
            scope_type, scope_value, sentiment, len(exclude_words), len(freqs),
        )

        scope_qs = _scope_qs(scope_type, scope_value, exclude_self)
        return templates.TemplateResponse(request, "partials/frag_wordfreq.html", {
            "cloud_words": cloud_words,
            "top_items": top_items,
            "sentiment": sentiment,
            "excluded": sorted(exclude_words),
            "scope_qs": scope_qs,
        })
    except Exception:
        logger.exception("wordfreq fragment failed")
        return _error(str(request.url))


@router.post("/analysis/wordfreq/stopwords", response_class=HTMLResponse)
def save_user_stopword(
    request: Request,
    word: str,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    """Add *word* to the per-user stopword overlay, then re-render the wordfreq
    fragment so the saved word disappears from the cloud immediately."""
    result = _validate_word_param(word)
    if isinstance(result, HTMLResponse):
        return result
    normalised = result

    conn = connect(account["db_path"])
    try:
        add_user_stopword(conn, normalised)
    finally:
        conn.close()

    logger.info("user_stopword saved: %s", normalised)
    return wordfreq_fragment(
        request,
        scope_type=scope_type, scope_value=scope_value,
        exclude_self=exclude_self, sentiment=sentiment,
        exclude=exclude, account=account,
    )


@router.delete("/analysis/wordfreq/stopwords", response_class=HTMLResponse)
def remove_user_stopword_route(
    request: Request,
    word: str,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    """Remove *word* from the per-user stopword overlay."""
    result = _validate_word_param(word)
    if isinstance(result, HTMLResponse):
        return result
    normalised = result

    conn = connect(account["db_path"])
    try:
        remove_user_stopword(conn, normalised)
    finally:
        conn.close()

    logger.info("user_stopword removed: %s", normalised)
    return wordfreq_fragment(
        request,
        scope_type=scope_type, scope_value=scope_value,
        exclude_self=exclude_self, sentiment=sentiment,
        exclude=exclude, account=account,
    )


@router.get("/analysis/wordfreq/filtered", response_class=HTMLResponse)
def wordfreq_filtered(
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    """Transparency panel: list of words currently being filtered.

    Two groups: user-saved (with × buttons) and built-in (read-only).
    Each entry shows what its count *would have been* on the current scope,
    so the user can sanity-check that nothing important is being hidden (B3).
    """
    from app.analysis.stopwords import get_base_stopwords

    conn = connect(account["db_path"])
    try:
        user_words = list_user_stopwords(conn)
    finally:
        conn.close()
    base_words = sorted(get_base_stopwords())

    # Build hidden-counts for both groups against the current scope.
    comments, analyses = scope_data(
        account["db_path"], scope_type, scope_value,
        exclude_self=exclude_self, self_handle=account["username"],
    )
    if sentiment in ("positive", "neutral", "negative"):
        comments = [c for c in comments if analyses.get(c.id) == sentiment]

    counts: Counter = Counter()
    for c in comments:
        counts.update(tokenize(c.text))

    user_entries = [{"word": w, "count": counts.get(w, 0)} for w in user_words]
    # Cap the built-in list to the 50 highest hidden counts to keep the
    # panel readable.
    base_entries = sorted(
        ({"word": w, "count": counts.get(w, 0)} for w in base_words if counts.get(w, 0) > 0),
        key=lambda e: -e["count"],
    )[:50]

    scope_qs = _scope_qs(scope_type, scope_value, exclude_self)
    return templates.TemplateResponse(request, "partials/_wordfreq_filtered.html", {
        "user_entries": user_entries,
        "base_entries": base_entries,
        "sentiment": sentiment,
        "excluded": sorted({w.strip().lower()[:50] for w in exclude if w and w.strip()}),
        "scope_qs": scope_qs,
    })


@router.get("/analysis/timetrend", response_class=HTMLResponse)
def timetrend_fragment(
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    account=auth.current_account,
):
    try:
        comments, analyses = scope_data(
            account["db_path"], scope_type, scope_value,
            exclude_self=exclude_self, self_handle=account["username"],
        )
        if not comments:
            return _empty("Belum ada komentar pada cakupan ini.")
        rows = timetrend.daily_trend(comments, analyses)
        total = sum(r["total"] for r in rows)
        days = len(rows)
        peak = max(rows, key=lambda r: r["total"])
        n = len(rows)
        idxs = sorted({0, n // 5, 2 * n // 5, 3 * n // 5, 4 * n // 5, n - 1}) if n > 1 else [0]
        xaxis = [_id_date(rows[i]["date"]) for i in idxs]
        summary = {
            "total": total, "days": days,
            "peak_label": _id_date(peak["date"]), "peak_count": peak["total"],
            "avg": round(total / days) if days else 0,
        }
        insights = {
            "biggest_day": _id_date(peak["date"]),
            "biggest_note": f"menyumbang {round(peak['total'] / total * 100)}% komentar",
            "biggest_meta": f"{peak['total']} komentar",
            "span": f"{_id_date(rows[0]['date'])} – {_id_date(rows[-1]['date'])}",
            "span_meta": f"{days} hari dengan komentar",
        }
        return templates.TemplateResponse(request, "partials/frag_timetrend.html", {
            "summary": summary, "chart_svg": svg.timetrend_area_svg(rows),
            "xaxis": xaxis, "insights": insights,
        })
    except Exception:
        logger.exception("timetrend fragment failed")
        return _error(str(request.url))


@router.get("/analysis/phrases", response_class=HTMLResponse)
def phrases_fragment(
    request: Request,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    account=auth.current_account,
):
    try:
        comments, _ = scope_data(
            account["db_path"], scope_type, scope_value,
            exclude_self=exclude_self, self_handle=account["username"],
        )
        if not comments:
            return _empty("Belum ada komentar pada cakupan ini.")
        ph = phrases_mod.top_phrases(comments)
        if not ph:
            return _empty("Belum ada frasa yang muncul ≥ 3 kali pada cakupan ini.")
        return templates.TemplateResponse(request, "partials/frag_phrases.html", {
            "phrases": [{"phrase": p, "count": c} for p, c in ph],
        })
    except Exception:
        logger.exception("phrases fragment failed")
        return _error(str(request.url))


@router.get("/analysis/wordfreq/sample", response_class=HTMLResponse)
def wordfreq_sample(
    request: Request,
    word: str,
    n: int = 5,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    sentiment: str = "all",
    exclude: list[str] = Query(default=[]),
    account=auth.current_account,
):
    """Drill-down: return a modal listing up to *n* random comments containing
    *word*, respecting the current scope and sentiment filter.

    Mirrors the sentiment sample modal pattern (B4-style "see the evidence").
    """
    result = _validate_word_param(word)
    if isinstance(result, HTMLResponse):
        return result
    normalised = result

    comments, analyses = scope_data(
        account["db_path"], scope_type, scope_value,
        exclude_self=exclude_self, self_handle=account["username"],
    )
    if sentiment in ("positive", "neutral", "negative"):
        comments = [c for c in comments if analyses.get(c.id) == sentiment]

    samples = wordfreq.comments_with_word(comments, normalised, n=n)
    total = sum(1 for c in comments if normalised in set(tokenize(c.text)))

    # Look up post titles for the "Dari: …" link in each card.
    post_titles: dict[str, dict[str, str]] = {}
    conn = connect(account["db_path"])
    try:
        for row in conn.execute("SELECT id, caption, permalink FROM posts"):
            post_titles[row["id"]] = {
                "title": (row["caption"] or "Tanpa caption")[:60],
                "link": row["permalink"],
            }
    finally:
        conn.close()

    view_samples = [
        {
            "handle": c.author_handle or "anon",
            "when": _id_datetime(c.timestamp),
            "text": c.text,
            "post_title": post_titles.get(c.post_id, {}).get("title", "Post"),
            "post_link": post_titles.get(c.post_id, {}).get("link"),
        }
        for c in samples
    ]

    scope_qs = _scope_qs(scope_type, scope_value, exclude_self)
    logger.info(
        "wordfreq sample word=%s sentiment=%s matches=%d returned=%d",
        normalised, sentiment, total, len(view_samples),
    )
    return templates.TemplateResponse(request, "partials/_wordfreq_sample.html", {
        "word": normalised,
        "samples": view_samples,
        "total": total,
        "n": n,
        "sentiment": sentiment,
        "scope_qs": scope_qs,
        "exclude": sorted({w.strip().lower()[:50] for w in exclude if w and w.strip()}),
    })


@router.get("/analysis/sentiment/sample", response_class=HTMLResponse)
def sentiment_sample(
    request: Request,
    bucket: str = "positive",
    n: int = 5,
    scope_type: str = "all",
    scope_value: str | None = None,
    exclude_self: bool = False,
    account=auth.current_account,
):
    conn = connect(account["db_path"])
    try:
        comments = drop_self(
            get_comments_in_scope(conn, scope_type, scope_value),
            exclude_self, account["username"],
        )
        analysis_rows = {
            r["comment_id"]: (r["sentiment_label"], r["sentiment_score"])
            for r in conn.execute(
                "SELECT comment_id, sentiment_label, sentiment_score FROM comment_analysis"
            )
        }
        posts = {p.id: p for p in (Post.from_row(r) for r in conn.execute("SELECT * FROM posts"))}
    finally:
        conn.close()

    matching = [c for c in comments if analysis_rows.get(c.id, ("unanalyzed", None))[0] == bucket]
    chosen = random.sample(matching, min(n, len(matching)))
    samples = []
    for c in chosen:
        post = posts.get(c.post_id)
        samples.append({
            "handle": c.author_handle or "anonim",
            "text": c.text,
            "when": _id_datetime(c.timestamp),
            "post_title": ((post.caption or "(tanpa caption)")[:32] if post else "post"),
            "post_link": post.permalink if post else None,
            "score": analysis_rows.get(c.id, (None, None))[1],
        })
    label, dot = _BUCKETS.get(bucket, (bucket, "neu"))
    return templates.TemplateResponse(request, "partials/_sample_modal.html", {
        "bucket": bucket, "bucket_label": label, "dot_class": dot,
        "samples": samples, "total": len(matching), "n": n,
        "scope_qs": _scope_qs(scope_type, scope_value),
    })
