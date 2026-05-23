"""Dashboard shell, scope selection, and manual-refresh routes."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app import auth, registry
from app.config import settings
from app.db import connect
from app.models import Post
from app.templating import templates

router = APIRouter()
logger = logging.getLogger("ig_pulse.routes.dashboard")
_refresh_state = {"running": False}


def build_scope_qs(
    scope_type: str, post_id: str = "", date_from: str = "", date_to: str = ""
) -> str:
    """Build the query string passed to each analysis fragment's hx-get URL."""
    if scope_type == "post" and post_id:
        return urlencode({"scope_type": "post", "scope_value": post_id})
    if scope_type == "period" and date_from and date_to:
        return urlencode({"scope_type": "period", "scope_value": f"{date_from}/{date_to}"})
    return urlencode({"scope_type": "all"})


def _fmt_wib(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(settings.timezone))
        return dt.strftime("%d %b %Y, %H:%M WIB")
    except ValueError:
        return iso


def _days_left(expires_at: str | None) -> int | None:
    """Whole days until the access token expires, or None if unknown (R4 banner)."""
    if not expires_at:
        return None
    try:
        exp = datetime.fromisoformat(expires_at)
    except ValueError:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    return (exp - datetime.now(UTC)).days


def _time_range(mn: str | None, mx: str | None) -> str:
    """Friendly span between the earliest and latest comment for the hero meta."""
    if not mn or not mx:
        return "—"
    try:
        days = (datetime.fromisoformat(mx) - datetime.fromisoformat(mn)).days
    except ValueError:
        return "—"
    if days >= 730:
        return f"{round(days / 365)} thn"
    return f"{max(days, 1)} hari"


@router.get("/", response_class=HTMLResponse)
def index(request: Request, account=auth.current_account):
    conn = connect(account["db_path"])
    posts = [Post.from_row(r) for r in conn.execute("SELECT * FROM posts ORDER BY timestamp DESC")]
    last = conn.execute("SELECT MAX(ended_at) FROM fetch_log").fetchone()[0]
    mn, mx, total = conn.execute(
        "SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM comments"
    ).fetchone()
    conn.close()
    rconn = registry.connect()
    accounts = registry.list_accounts(rconn, account["user_id"])
    rconn.close()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "posts": posts,
            "scope_qs": build_scope_qs("all"),
            "last_refreshed": _fmt_wib(last),
            "token_days_left": _days_left(account["token_expires_at"]),
            "sentiment_model": settings.sentiment_model,
            "ig_username": account["username"],
            "total_comments": f"{total:,}",
            "total_posts": len(posts),
            "time_range": _time_range(mn, mx),
            "accounts": accounts,
            "active_account_id": account["id"],
        },
    )


@router.post("/scope", response_class=HTMLResponse)
def set_scope(
    request: Request,
    scope_type: str = Form("all"),
    post_id: str = Form(""),
    date_from: str = Form(""),
    date_to: str = Form(""),
    account=auth.current_account,
):
    qs = build_scope_qs(scope_type, post_id, date_from, date_to)
    return templates.TemplateResponse(
        request, "partials/grid.html", {"scope_qs": qs, "sentiment_model": settings.sentiment_model}
    )


def _muted(text: str) -> str:
    return f'<span style="color:var(--fg-muted)">{text}</span>'


def _poll_span() -> HTMLResponse:
    """A status span that polls /refresh/status every 2s until the fetch finishes."""
    return HTMLResponse(
        '<span hx-get="/refresh/status" hx-trigger="every 2s" hx-swap="outerHTML" '
        'style="color:var(--fg-muted)">⏳ Memuat komentar terbaru dari Instagram…</span>'
    )


def _do_refresh(db_path: str, token: str, ig_user_id: str) -> None:
    """Background: re-fetch posts/comments, then run sentiment on the new ones."""
    try:
        from app.analysis.sentiment import analyze_comments
        from app.db import connect as _connect
        from app.fetch import fetch_all

        asyncio.run(fetch_all(db_path=db_path, access_token=token, ig_user_id=ig_user_id))
        c = _connect(db_path)
        analyze_comments(c)
        c.close()
    except Exception:
        logger.exception("background refresh failed")
    finally:
        _refresh_state["running"] = False


@router.post("/refresh", response_class=HTMLResponse)
def refresh(account=auth.current_account):
    if not _refresh_state["running"]:
        _refresh_state["running"] = True
        threading.Thread(
            target=_do_refresh,
            args=(account["db_path"], account["access_token"], account["ig_user_id"]),
            daemon=True,
        ).start()
    return _poll_span()


@router.get("/refresh/status", response_class=HTMLResponse)
def refresh_status():
    if _refresh_state["running"]:
        return _poll_span()
    resp = HTMLResponse(_muted("✓ Selesai — memuat ulang…"))
    resp.headers["HX-Refresh"] = "true"  # full reload to show fresh data
    return resp
