"""Instagram Graph API client — async, rate-limit aware, logs every call.

⚠️ SHAPES UNVERIFIED. The field lists and response parsing in the ``get_*``
methods follow architecture.md / api-integration.md, but the REAL response
shapes are confirmed by Phase 2 tasks V1–V6, which save fixtures to
``tests/fixtures/``. Do NOT build analysis on these shapes until verified
(CLAUDE.md B10, risks.md R2).

The data-independent logic here IS unit-tested now (tests/test_ig_client.py):
  - ``parse_business_use_case_usage`` — header parsing
  - ``usage_action`` — usage-percentage → action thresholds
  - the 429 exponential-backoff retry in ``IGClient._get``

Security: the access token is sent as a query param but NEVER logged (B12).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("ig_pulse.ig_client")

# architecture.md: <75% proceed, 75–90% warn, ≥90% sleep 60s before next call.
USAGE_WARN_PCT = 75.0
USAGE_SLEEP_PCT = 90.0
USAGE_SLEEP_SECONDS = 60.0
# architecture.md: 429 → exponential backoff 60s, 120s, 240s, then fail.
DEFAULT_BACKOFF_SCHEDULE: tuple[float, ...] = (60.0, 120.0, 240.0)


@dataclass
class Page:
    """One page of results plus the cursor for the next page (None if last)."""

    data: list[dict]
    after: str | None


def parse_business_use_case_usage(header_value: str | None) -> float | None:
    """Max usage percentage (0–100) from the ``X-Business-Use-Case-Usage``
    header, or ``None`` if the header is absent/unparseable.

    The header is a JSON object keyed by business id; each value is a list of
    dicts carrying ``call_count`` / ``total_cputime`` / ``total_time`` as
    percentages. ⚠️ V5: confirm the exact shape against the real API.
    """
    if not header_value:
        return None
    try:
        payload = json.loads(header_value)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse X-Business-Use-Case-Usage header")
        return None
    pcts: list[float] = []
    for entries in payload.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for key in ("call_count", "total_cputime", "total_time"):
                val = entry.get(key)
                if isinstance(val, (int, float)):
                    pcts.append(float(val))
    return max(pcts) if pcts else None


def usage_action(pct: float | None) -> str:
    """Map a usage percentage to an action: ``proceed`` | ``warn`` | ``sleep``."""
    if pct is None:
        return "proceed"
    if pct >= USAGE_SLEEP_PCT:
        return "sleep"
    if pct >= USAGE_WARN_PCT:
        return "warn"
    return "proceed"


class IGTokenError(RuntimeError):
    """Raised when the API reports the access token is invalid/expired (R4)."""


class IGClient:
    """Thin async wrapper over the Graph API. Use as an async context manager."""

    def __init__(
        self,
        access_token: str | None = None,
        *,
        base_url: str | None = None,
        backoff_schedule: tuple[float, ...] = DEFAULT_BACKOFF_SCHEDULE,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = access_token or settings.ig_access_token
        self._base_url = (base_url or settings.graph_api_url).rstrip("/")
        self._backoff_schedule = backoff_schedule
        self._client = client or httpx.AsyncClient(timeout=30)
        self.api_calls_made = 0

    async def __aenter__(self) -> IGClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        if not self._token:
            settings.require_ig_credentials()
        params = {**(params or {}), "access_token": self._token}
        url = f"{self._base_url}/{path.lstrip('/')}"

        for attempt in range(len(self._backoff_schedule) + 1):
            started = time.monotonic()
            resp = await self._client.get(url, params=params)
            duration_ms = (time.monotonic() - started) * 1000
            self.api_calls_made += 1
            # B11: log endpoint, status, duration, size — never the token.
            logger.info(
                "GET %s -> %s (%.0fms, %dB)", path, resp.status_code, duration_ms, len(resp.content)
            )

            if resp.status_code == 429:
                if attempt < len(self._backoff_schedule):
                    delay = self._backoff_schedule[attempt]
                    logger.warning(
                        "429 rate limited; backing off %ss (attempt %d)", delay, attempt + 1
                    )
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()  # attempts exhausted

            if resp.status_code == 400 and self._looks_like_token_error(resp):
                raise IGTokenError(
                    "Instagram token invalid/expired. Run `python -m app.cli refresh-token`."
                )
            resp.raise_for_status()

            await self._honor_usage(resp)
            return resp

        raise RuntimeError("unreachable: retry loop exhausted without returning")

    async def _honor_usage(self, resp: httpx.Response) -> None:
        """Throttle the NEXT call based on the usage header (architecture.md)."""
        action = usage_action(
            parse_business_use_case_usage(resp.headers.get("X-Business-Use-Case-Usage"))
        )
        if action == "warn":
            logger.warning("Graph API usage in 75-90%% band; approaching limit.")
        elif action == "sleep":
            logger.warning("Graph API usage >=90%%; sleeping %ss.", USAGE_SLEEP_SECONDS)
            await asyncio.sleep(USAGE_SLEEP_SECONDS)

    @staticmethod
    def _looks_like_token_error(resp: httpx.Response) -> bool:
        try:
            err = resp.json().get("error", {})
        except Exception:
            return False
        # OAuthException / code 190 = expired/invalid token. ⚠️ verify in Phase 2.
        return err.get("type") == "OAuthException" or err.get("code") == 190

    @staticmethod
    def _page(payload: dict) -> Page:
        after = payload.get("paging", {}).get("cursors", {}).get("after")
        return Page(data=payload.get("data", []), after=after)

    # --- API methods. ⚠️ Response shapes UNVERIFIED until V1–V6. ---

    async def get_user_profile(
        self, fields: str = "username,followers_count,media_count"
    ) -> dict:
        resp = await self._get(settings.ig_user_id or "me", {"fields": fields})
        return resp.json()

    async def list_media(
        self,
        limit: int = 25,
        after: str | None = None,
        fields: str = (
            "id,caption,media_type,permalink,timestamp,"
            "like_count,comments_count,thumbnail_url"
        ),
    ) -> Page:
        """V1: verify pagination defaults / max limit / cursor behavior."""
        params: dict = {"fields": fields, "limit": limit}
        if after:
            params["after"] = after
        resp = await self._get(f"{settings.ig_user_id}/media", params)
        return self._page(resp.json())

    async def get_comments(
        self,
        media_id: str,
        limit: int = 50,
        after: str | None = None,
        fields: str = "id,text,username,timestamp,like_count,parent_id",
    ) -> Page:
        """V2: verify comment text encoding (emoji/mentions). V4: deleted behavior."""
        params: dict = {"fields": fields, "limit": limit}
        if after:
            params["after"] = after
        resp = await self._get(f"{media_id}/comments", params)
        return self._page(resp.json())

    async def get_replies(
        self,
        comment_id: str,
        limit: int = 50,
        after: str | None = None,
        fields: str = "id,text,username,timestamp,like_count",
    ) -> Page:
        """V3: verify replies sort + pagination. V6: do replies have replies?"""
        params: dict = {"fields": fields, "limit": limit}
        if after:
            params["after"] = after
        resp = await self._get(f"{comment_id}/replies", params)
        return self._page(resp.json())
