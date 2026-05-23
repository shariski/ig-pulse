# IG Pulse — Multi-account (Phase 2) — Design Spec

**Date:** 2026-05-23
**Status:** Approved (brainstorming) → ready for implementation plan
**Scope note:** Multi-account is explicitly *out of MVP* in README.md, CLAUDE.md B1,
and the design handover. The user has **explicitly approved promoting it to a Phase-2
build** (satisfies B1 "confirm scope change first").

## Goal

Let multiple people (e.g. two siblings) each analyze their own Instagram account in
one running IG Pulse instance, with login-separated, fully isolated data.

## Non-goals (YAGNI)

Password reset, email verification, roles/permissions, sharing an IG account between
users, OAuth-redirect login (we use paste-token), login rate-limiting, public/hosted
deployment. SNA/BERTopic/scheduler remain out of scope.

## Key decisions (all user-approved)

1. **Auth:** full user accounts (username + password). Hashing: **argon2** via
   `argon2-cffi` `PasswordHasher` (OWASP #1; memory-hard). New dependency.
2. **Setup:** self-service — in-app registration + login + in-app "add Instagram
   account" (paste a short-lived token; the app does the long-lived exchange).
3. **Data model:** **one SQLite file per IG account** + a small `registry.db`. Chosen
   because every data function is already connection-parameterized, so the
   analysis/fetch/render layer is nearly untouched and isolation is physical.
4. **Sessions:** Starlette `SessionMiddleware` (signed cookie); `SESSION_SECRET`
   auto-generated into `.env` on first run.

## Architecture — two-tier storage

- **`registry.db`** (new, at project root, gitignored):
  - `users(id, username UNIQUE, password_hash, created_at)`
  - `ig_accounts(id, user_id→users, ig_user_id, username, access_token,
    token_expires_at, db_path, created_at, UNIQUE(user_id, ig_user_id))`
- **`data/acct_<id>.db`** per IG account: the *current* schema
  (`posts`, `comments`, `comment_analysis`, `fetch_log`) — **unchanged**, reusing
  `app/migrations/001_initial.sql` via the existing `run_migrations`.

Tokens (per-account) move from `.env` into `registry.db`. `FB_APP_ID`/`FB_APP_SECRET`
stay in `.env` (one shared "Pulse" Meta app; each person's IG is a tester on it).

## New modules

- `app/registry.py` — registry DB connect + migrations; helpers: `create_user`,
  `get_user_by_name`, `create_account`, `list_accounts(user_id)`, `get_account(id)`,
  `update_account_token(id, token, expires_at)`. Owns `data/` dir creation.
- `app/auth.py` — `hash_password`/`verify_password` (argon2 `PasswordHasher`),
  FastAPI dependencies `current_user` (→ redirect `/login` if no session) and
  `current_account` (loads session's `account_id` **and re-checks
  `account.user_id == current_user.id`** — the cross-account guard).
- `app/routes/auth_routes.py` — `GET/POST /register`, `GET/POST /login`, `POST /logout`.
- `app/routes/accounts.py` — `GET /accounts` (list + switch + add form),
  `POST /accounts/switch`, `POST /accounts/add` (paste-token → exchange → create
  account + db + first fetch), `POST /accounts/{id}/refresh-token`.
- Templates (editorial design system): `login.html`, `register.html`, `accounts.html`.

## Changed modules

- `app/main.py` — add `SessionMiddleware`; include auth + accounts routers; create
  `data/` + `registry.db` (run registry migrations) on startup.
- `app/config.py` — add `session_secret` (auto-generate→.env if missing),
  `register_code` (optional, default empty = open registration), `registry_path`,
  `data_dir`. Keep `fb_app_id`/`fb_app_secret`.
- `app/routes/dashboard.py` — `/`, `/scope`, `/refresh`, `/refresh/status` now depend
  on `current_account`; open `connect(account.db_path)`; hero/sidebar show the active
  account; refresh uses the account's token + db. Sidebar gains active-account label +
  "switch account" + "logout".
- `app/routes/analysis.py` + `export.py` — fragments/exports depend on
  `current_account`; `scope_data` opens the active account's db.
- `app/fetch.py` — `fetch_all(db_path=None, access_token=None, ...)` (thread the
  account's db + token; `IGClient(access_token=…)` already supported).
- `app/cli.py` — add `migrate` (one-time: prompt username/password → create user →
  import the `.env` account → adopt existing `ig_pulse.db` as `data/acct_1.db`).
  Existing `setup`/`refresh-token`/`fetch` stay functional as legacy single-account
  helpers (default `.env`/db); the multi-account path is fully in-app. No per-account
  CLI flags added (YAGNI).

## Self-service flows

- **Register** (`/register`): username + password (+ `REGISTER_CODE` if configured).
  Creates a user; redirects to `/login`.
- **Login** (`/login`): verify argon2 hash → set `session["user_id"]`.
- **Add IG account** (`/accounts/add`): user pastes a short-lived token from Graph
  API Explorer; server runs `/me/accounts` → Page → `instagram_business_account` →
  `fb_exchange_token` (using shared `FB_APP_SECRET`), creates the `ig_accounts` row +
  `data/acct_<id>.db` (+ migrations), sets it active, and kicks off the first fetch in
  the background for that account (`fetch_all(db_path, access_token)` +
  `analyze_comments(conn)` against the new account's db).
- **Switch** (`/accounts/switch`): set `session["account_id"]` (ownership re-checked).
- **Logout** (`/logout`): clear session.

## Migration (one-time, explicit)

`uv run python -m app.cli migrate` → prompts username/password → creates the first
user → reads `.env` (token, ig_user_id, username, expiry) into an `ig_accounts` row →
moves/adopts existing `ig_pulse.db` as `data/acct_1.db`. Idempotent guard if already
migrated.

## Security considerations

- **Cross-account guard:** `current_account` MUST verify `account.user_id ==
  session.user_id` on every request — never trust a session `account_id` alone.
  Dedicated tests.
- **Token storage:** plaintext in `registry.db` (gitignored, local-only) — same trust
  level as the current `.env`. Documented as a deliberate deviation from CLAUDE.md B12
  in `docs/decisions.md`.
- **Session secret:** stable, stored in `.env` (auto-generated once). Never logged.
- **Registration gate:** optional `REGISTER_CODE` (default off = open on LAN, which is
  acceptable for a home network; set it to require a shared code).
- **Passwords/tokens never logged** (B11/B12).

## Testing

- **registry:** user create + uniqueness; account create/list/get; ownership.
- **auth:** argon2 hash↔verify round-trip; wrong password fails; `current_user`/
  `current_account` dependency behavior incl. the cross-account block.
- **routes:** register→login→add-account→scoped dashboard; unauthenticated → redirect;
  user A cannot open user B's account (switch with foreign id → blocked).
- **regression:** analysis/render/svg tests unchanged (per-account-db design);
  `test_routes.py` updated for the login gate (tests log in first).

## Deviations recorded in docs/decisions.md

- B1: multi-account promoted from out-of-scope (user-approved).
- B12: per-account tokens stored in `registry.db` rather than `.env` (inherent to
  multi-account; same local trust level).
