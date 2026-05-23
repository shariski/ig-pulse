"""Shared IG account bootstrap: exchange a short-lived token for a long-lived one and
discover the IG business account (Facebook Login path). Used by in-app add-account
and `cli migrate`. Accepts an injectable httpx.Client for testing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings


class IGSetupError(RuntimeError):
    pass


@dataclass
class AccountInfo:
    ig_user_id: str
    username: str | None
    access_token: str
    token_expires_at: str | None


def discover_account(
    short_token: str,
    app_id: str | None = None,
    app_secret: str | None = None,
    *,
    client: httpx.Client | None = None,
) -> AccountInfo:
    app_id = app_id or settings.fb_app_id
    app_secret = app_secret or settings.fb_app_secret
    own = client is None
    c = client or httpx.Client(base_url=settings.graph_api_url, timeout=30)

    def get(path: str, **params) -> dict:
        r = c.get(f"/{path.lstrip('/')}", params={**params})
        r.raise_for_status()
        return r.json()

    try:
        pages = get("me/accounts", access_token=short_token).get("data", [])
        if not pages:
            raise IGSetupError("Tidak ada Facebook Page untuk token ini. Hubungkan IG ke Page.")
        page_id = pages[0]["id"]
        linked = get(page_id, fields="instagram_business_account", access_token=short_token)
        iba = linked.get("instagram_business_account")
        if not iba:
            raise IGSetupError(f"Page {page_id} tidak punya instagram_business_account.")
        ig_user_id = iba["id"]
        if not app_secret:
            raise IGSetupError("FB_APP_SECRET belum diatur di .env.")
        exch = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                   client_secret=app_secret, fb_exchange_token=short_token)
        long_token = exch["access_token"]
        expires_at = None
        if exch.get("expires_in"):
            expires_at = (
                datetime.now(UTC) + timedelta(seconds=int(exch["expires_in"]))
            ).isoformat()
        profile = get(ig_user_id, fields="username", access_token=long_token)
        return AccountInfo(ig_user_id, profile.get("username"), long_token, expires_at)
    except httpx.HTTPStatusError as e:
        raise IGSetupError(f"Graph API error: {e.response.status_code}") from e
    finally:
        if own:
            c.close()
