"""IG account management: list, switch, add (paste-token)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import auth, registry
from app.db import connect as data_connect
from app.db import run_migrations as data_migrations
from app.fetch_jobs import start_fetch
from app.ig_setup import IGSetupError, discover_account
from app.templating import templates

router = APIRouter()
logger = logging.getLogger("ig_pulse.routes.accounts")


@router.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request, user=auth.current_user):
    conn = registry.connect()
    try:
        accounts = registry.list_accounts(conn, user["id"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "accounts.html",
        {"accounts": accounts, "active": request.session.get("account_id")},
    )


@router.post("/accounts/switch")
def switch(request: Request, account_id: int = Form(...), user=auth.current_user):
    conn = registry.connect()
    try:
        acct = registry.get_account(conn, account_id)
    finally:
        conn.close()
    if acct is None or acct["user_id"] != user["id"]:
        return RedirectResponse("/accounts", status_code=302)  # ownership guard
    request.session["account_id"] = account_id
    return RedirectResponse("/", status_code=302)


@router.post("/accounts/add", response_class=HTMLResponse)
def add_account(request: Request, short_token: str = Form(...), user=auth.current_user):
    conn = registry.connect()
    try:
        try:
            info = discover_account(short_token.strip())
        except IGSetupError as e:
            accounts = registry.list_accounts(conn, user["id"])
            return templates.TemplateResponse(
                request, "accounts.html",
                {
                    "accounts": accounts,
                    "active": request.session.get("account_id"),
                    "error": str(e),
                },
            )
        aid = registry.create_account(conn, user["id"], info.ig_user_id, info.username,
                                      info.access_token, info.token_expires_at)
        acct = registry.get_account(conn, aid)
    finally:
        conn.close()
    dconn = data_connect(acct["db_path"])
    data_migrations(dconn)
    dconn.close()
    start_fetch(acct["db_path"], info.access_token, info.ig_user_id)
    request.session["account_id"] = aid
    return RedirectResponse("/", status_code=302)
