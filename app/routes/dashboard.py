"""Dashboard shell, scope selection, and manual-refresh routes."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.db import connect
from app.models import Post
from app.templating import templates

router = APIRouter()


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


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = connect()
    posts = [Post.from_row(r) for r in conn.execute("SELECT * FROM posts ORDER BY timestamp DESC")]
    last = conn.execute("SELECT MAX(ended_at) FROM fetch_log").fetchone()[0]
    conn.close()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "posts": posts,
            "scope_qs": build_scope_qs("all"),
            "last_refreshed": _fmt_wib(last),
        },
    )


@router.post("/scope", response_class=HTMLResponse)
def set_scope(
    request: Request,
    scope_type: str = Form("all"),
    post_id: str = Form(""),
    date_from: str = Form(""),
    date_to: str = Form(""),
):
    qs = build_scope_qs(scope_type, post_id, date_from, date_to)
    return templates.TemplateResponse(request, "partials/grid.html", {"scope_qs": qs})


@router.post("/refresh", response_class=HTMLResponse)
def refresh():
    # MVP: a real fetch is slow (many API calls) and blocking — keep it a manual CLI
    # step rather than tying up the request (plan: auto-refresh is Phase 2).
    return HTMLResponse(
        '<span id="refresh-status" style="color: var(--pico-muted-color);">'
        "Untuk memperbarui data, jalankan <code>uv run python -m app.cli fetch</code> "
        "lalu muat ulang halaman.</span>"
    )
