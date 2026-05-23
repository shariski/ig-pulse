"""IG Pulse command-line interface.

Commands:
    setup          One-time: discover IG_USER_ID, exchange a short-lived token for
                   a long-lived (~60-day) one, smoke-test, and write results to .env.
    refresh-token  Refresh the long-lived token before expiry; update .env in place.
    fetch          [Phase 2] Pull posts/comments into SQLite for a given scope.

Security: the access token is written to .env but NEVER printed/logged (CLAUDE.md B12).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import set_key

from app.config import settings

ENV_PATH = Path(".env")


def _graph_get(path: str, params: dict) -> dict:
    """GET against the versioned Graph API base, raising on HTTP error."""
    url = f"{settings.graph_api_url}/{path.lstrip('/')}"
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _expiry_iso(expires_in: int | str | None) -> str | None:
    """ISO-8601 timestamp `expires_in` seconds from now (UTC), or None."""
    if not expires_in:
        return None
    return (datetime.now(UTC) + timedelta(seconds=int(expires_in))).isoformat()


def cmd_setup(args: argparse.Namespace) -> None:
    short_token = args.short_token
    app_id = args.app_id or settings.fb_app_id
    app_secret = args.app_secret or settings.fb_app_secret
    if not (short_token and app_id and app_secret):
        sys.exit(
            "Need --short-token plus App ID/Secret "
            "(pass --app-id/--app-secret or set FB_APP_ID/FB_APP_SECRET in .env)."
        )

    # Step 6: discover the IG business account via the linked Facebook Page.
    pages = _graph_get("me/accounts", {"access_token": short_token}).get("data", [])
    if not pages:
        sys.exit("No Facebook Pages found for this token. Is a Page linked to your IG?")
    print("Pages found:")
    for p in pages:
        print(f"  - {p.get('name')} (id={p.get('id')})")
    page_id = args.page_id or pages[0]["id"]
    linked = _graph_get(
        page_id, {"fields": "instagram_business_account", "access_token": short_token}
    )
    iba = linked.get("instagram_business_account")
    if not iba:
        sys.exit(f"Page {page_id} has no linked instagram_business_account.")
    ig_user_id = iba["id"]
    print(f"IG_USER_ID = {ig_user_id}")

    # Step 7: exchange short-lived -> long-lived token (~60 days).
    exchange = _graph_get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
    )
    long_token = exchange["access_token"]
    print(f"Long-lived token acquired (expires_in≈{exchange.get('expires_in')}s).")

    # Step 8: smoke test.
    profile = _graph_get(
        ig_user_id,
        {"fields": "username,followers_count,media_count", "access_token": long_token},
    )
    print(
        f"Smoke test OK: @{profile.get('username')} "
        f"followers={profile.get('followers_count')} media={profile.get('media_count')}"
    )

    # Persist to .env. The token value is written but never printed.
    set_key(str(ENV_PATH), "FB_APP_ID", str(app_id))
    set_key(str(ENV_PATH), "FB_APP_SECRET", str(app_secret))
    set_key(str(ENV_PATH), "IG_USER_ID", ig_user_id)
    if profile.get("username"):
        set_key(str(ENV_PATH), "IG_USERNAME", str(profile["username"]))
    set_key(str(ENV_PATH), "IG_ACCESS_TOKEN", long_token)
    expires_at = _expiry_iso(exchange.get("expires_in"))
    if expires_at:
        set_key(str(ENV_PATH), "IG_TOKEN_EXPIRES_AT", expires_at)
    print(f"Wrote IG_USER_ID + IG_ACCESS_TOKEN to {ENV_PATH}. Setup complete.")


def cmd_refresh_token(args: argparse.Namespace) -> None:
    settings.require_ig_credentials()
    # NOTE (Phase 2 verification, see risks.md R2): api-integration.md specifies the
    # `ig_refresh_token` grant, but that is the (dead) Basic Display flow. For Graph API
    # long-lived tokens, refreshing may instead require re-running fb_exchange_token.
    # Verify the real behavior against the live API before relying on this in production.
    data = _graph_get(
        "refresh_access_token",
        {"grant_type": "ig_refresh_token", "access_token": settings.ig_access_token},
    )
    new_token = data["access_token"]
    expires_in = data.get("expires_in")
    set_key(str(ENV_PATH), "IG_ACCESS_TOKEN", new_token)
    expires_at = _expiry_iso(expires_in)
    if expires_at:
        set_key(str(ENV_PATH), "IG_TOKEN_EXPIRES_AT", expires_at)
    days = round(expires_in / 86400) if expires_in else "?"
    print(f"Token refreshed. New expiry ≈ {days} days from now. Updated {ENV_PATH}.")


def cmd_migrate(args: argparse.Namespace) -> None:
    import getpass
    import shutil

    from app import auth, registry

    rconn = registry.connect()
    registry.run_migrations(rconn)
    if rconn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        rconn.close()
        sys.exit("Registry already has users — migration already done.")
    if not settings.ig_access_token or not settings.ig_user_id:
        rconn.close()
        sys.exit("No single-account .env data to migrate (need IG_ACCESS_TOKEN + IG_USER_ID).")

    username = args.username or input("New login username: ")
    password = args.password or getpass.getpass("New login password: ")
    uid = registry.create_user(rconn, username, auth.hash_password(password))
    aid = registry.create_account(rconn, uid, settings.ig_user_id, settings.ig_username,
                                  settings.ig_access_token, settings.ig_token_expires_at)
    acct = registry.get_account(rconn, aid)
    rconn.close()

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    src = settings.database_path
    dst = acct["db_path"]
    if src.exists():
        shutil.copy2(src, dst)
        print(f"Adopted {src} -> {dst}")
    print(f"Created user '{username}' + account @{settings.ig_username} (id={aid}). Done.")


def cmd_fetch(args: argparse.Namespace) -> None:
    if args.scope != "all":
        raise SystemExit(f"scope={args.scope!r} not implemented yet; use --scope all.")
    import asyncio

    from app.fetch import fetch_all

    s = asyncio.run(fetch_all())
    print(
        f"Fetched {s['posts']} posts, {s['comments']} comments in "
        f"{s['api_calls']} API calls (run {s['run_id']})."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="IG Pulse CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="Discover IG_USER_ID + store a long-lived token")
    s.add_argument("--short-token", required=True, help="Short-lived token from Graph API Explorer")
    s.add_argument("--app-id", help="FB App ID (defaults to .env FB_APP_ID)")
    s.add_argument("--app-secret", help="FB App Secret (defaults to .env FB_APP_SECRET)")
    s.add_argument("--page-id", help="FB Page ID (defaults to the first page found)")
    s.set_defaults(func=cmd_setup)

    r = sub.add_parser("refresh-token", help="Refresh the long-lived token and update .env")
    r.set_defaults(func=cmd_refresh_token)

    f = sub.add_parser("fetch", help="[Phase 2] Pull posts/comments into SQLite")
    f.add_argument("--scope", choices=["post", "period", "all"], default="all")
    f.add_argument("--value", help="post id, or ISO range YYYY-MM-DD/YYYY-MM-DD")
    f.set_defaults(func=cmd_fetch)

    m = sub.add_parser("migrate", help="One-time: import the .env single account into the registry")
    m.add_argument("--username")
    m.add_argument("--password")
    m.set_defaults(func=cmd_migrate)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
