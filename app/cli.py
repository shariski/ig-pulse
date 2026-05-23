"""IG Pulse command-line interface (Instagram API with Instagram Login).

Commands:
    setup          One-time: validate a token, read your IG user id, exchange for a
                   long-lived (~60-day) token (best-effort), smoke-test, write .env.
    refresh-token  Refresh the long-lived token before expiry; update .env in place.
    fetch          [Phase 2] Pull posts/comments into SQLite for a given scope.

Host: graph.instagram.com. Token exchange/refresh use the UNVERSIONED base; data
calls use the versioned base. The access token is written to .env but NEVER
printed/logged (CLAUDE.md B12).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx
from dotenv import set_key

from app.config import settings

ENV_PATH = Path(".env")


def _graph_get(path: str, params: dict, base: str | None = None) -> dict:
    """GET against graph.instagram.com, raising on HTTP error.

    base defaults to the versioned data base; pass settings.graph_api_base_url
    (unversioned) for the token-exchange endpoints.
    """
    base = (base or settings.graph_api_url).rstrip("/")
    resp = httpx.get(f"{base}/{path.lstrip('/')}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def cmd_setup(args: argparse.Namespace) -> None:
    short_token = args.short_token
    secret = args.app_secret or settings.app_secret

    # 1. Validate the token + read the IG user id and handle.
    me = _graph_get("me", {"fields": "user_id,username", "access_token": short_token})
    user_id = str(me.get("user_id") or me.get("id") or "")
    username = me.get("username")
    if not user_id:
        sys.exit(f"Could not read user_id from /me (got {me!r}). Is the token valid?")
    print(f"IG user: @{username} (id={user_id})")

    # 2. Best-effort exchange short-lived -> long-lived (~60 days).
    access_token = short_token
    if secret:
        try:
            exchanged = _graph_get(
                "access_token",
                {
                    "grant_type": "ig_exchange_token",
                    "client_secret": secret,
                    "access_token": short_token,
                },
                base=settings.graph_api_base_url,
            )
            access_token = exchanged["access_token"]
            days = round(exchanged.get("expires_in", 0) / 86400) or "?"
            print(f"Exchanged for long-lived token (expires in ~{days} days).")
        except httpx.HTTPStatusError as e:
            print(
                f"WARNING: long-lived exchange failed ({e.response.status_code}). "
                "Storing the token you provided as-is.\n"
                "  Likely the *Instagram* app secret differs from FB_APP_SECRET. Find "
                "it in the Instagram Login use-case settings and set IG_APP_SECRET in "
                ".env, then re-run setup. (If the dashboard token is already long-lived, "
                "you can ignore this.)",
                file=sys.stderr,
            )
    else:
        print(
            "WARNING: no app secret set; storing the provided token without exchange.",
            file=sys.stderr,
        )

    # 3. Smoke test with the token we'll actually store.
    profile = _graph_get(
        "me",
        {"fields": "username,followers_count,media_count", "access_token": access_token},
    )
    print(
        f"Smoke test OK: @{profile.get('username')} "
        f"followers={profile.get('followers_count')} media={profile.get('media_count')}"
    )

    # 4. Persist. Token value written but never printed.
    set_key(str(ENV_PATH), "IG_USER_ID", user_id)
    set_key(str(ENV_PATH), "IG_ACCESS_TOKEN", access_token)
    print(f"Wrote IG_USER_ID + IG_ACCESS_TOKEN to {ENV_PATH}. Setup complete.")


def cmd_refresh_token(args: argparse.Namespace) -> None:
    settings.require_ig_credentials()
    data = _graph_get(
        "refresh_access_token",
        {"grant_type": "ig_refresh_token", "access_token": settings.ig_access_token},
        base=settings.graph_api_base_url,
    )
    new_token = data["access_token"]
    days = round(data.get("expires_in", 0) / 86400) or "?"
    set_key(str(ENV_PATH), "IG_ACCESS_TOKEN", new_token)
    print(f"Token refreshed. New expiry ~{days} days. Updated {ENV_PATH}.")


def cmd_fetch(args: argparse.Namespace) -> None:
    raise SystemExit(
        "`fetch` is implemented in Phase 2 — it needs app/ig_client.py and the fetch "
        "orchestrator (plan.md Phase 2/3). Build those against the real API first."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="IG Pulse CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="Validate token, read user id, store long-lived token")
    s.add_argument("--short-token", required=True, help="Token from the Instagram Login dashboard")
    s.add_argument(
        "--app-secret", help="Instagram app secret (defaults to IG_APP_SECRET/FB_APP_SECRET)"
    )
    s.set_defaults(func=cmd_setup)

    r = sub.add_parser("refresh-token", help="Refresh the long-lived token and update .env")
    r.set_defaults(func=cmd_refresh_token)

    f = sub.add_parser("fetch", help="[Phase 2] Pull posts/comments into SQLite")
    f.add_argument("--scope", choices=["post", "period", "all"], default="all")
    f.add_argument("--value", help="post id, or ISO range YYYY-MM-DD/YYYY-MM-DD")
    f.set_defaults(func=cmd_fetch)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
