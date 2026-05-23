# Multi-account (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let multiple users each register, log in, connect their own Instagram account(s), and see login-isolated analytics in one running IG Pulse instance.

**Architecture:** Two-tier storage — a `registry.db` (users + ig_accounts + per-account tokens) plus one `data/acct_<id>.db` per IG account (the existing schema, unchanged). Starlette sessions gate every page; routes resolve the session's active account, verify ownership, then run the existing connection-parameterized pipeline against that account's DB with that account's token.

**Tech Stack:** FastAPI, Starlette `SessionMiddleware`, Jinja2/HTMX, SQLite (stdlib `sqlite3`), `argon2-cffi` (password hashing), `httpx` (token exchange).

Spec: `docs/superpowers/specs/2026-05-23-multi-account-design.md`.

---

## File structure

**Create:**
- `app/auth.py` — password hashing (argon2) + session-backed `current_user` / `current_account` dependencies.
- `app/registry.py` — registry DB (connect, migrations) + user/account CRUD.
- `app/registry_migrations/001_registry.sql` — `users` + `ig_accounts` schema.
- `app/ig_setup.py` — shared IG-account bootstrap (token exchange + account discovery), used by both the in-app add-account flow and `cli migrate`.
- `app/routes/auth_routes.py` — `/register`, `/login`, `/logout`.
- `app/routes/accounts.py` — `/accounts`, `/accounts/switch`, `/accounts/add`, `/accounts/{id}/refresh-token`.
- `app/templates/login.html`, `app/templates/register.html`, `app/templates/accounts.html`.
- Tests: `tests/test_auth.py`, `tests/test_registry.py`, `tests/test_ig_setup.py`, `tests/test_auth_routes.py`, `tests/test_accounts_routes.py`.

**Modify:**
- `app/config.py` — add `session_secret`, `register_code`, `registry_path`, `data_dir`.
- `app/main.py` — `SessionMiddleware`; include new routers; registry migrations + `data/` on startup.
- `app/routes/dashboard.py`, `app/routes/analysis.py`, `app/routes/export.py` — depend on `current_account`; open the account's DB; refresh uses the account's token.
- `app/fetch.py` — `fetch_all(db_path=None, access_token=None, with_replies=True)`.
- `app/cli.py` — add `migrate`.
- `tests/test_routes.py` — log in before asserting (login gate).
- `pyproject.toml` — add `argon2-cffi`.
- `.gitignore` — add `registry.db`, `data/`.
- `docs/decisions.md` — record B1 + B12 deviations.

---

## Task 1: Dependencies, config, gitignore

**Files:**
- Modify: `pyproject.toml`, `app/config.py`, `.gitignore`

- [ ] **Step 1: Add argon2-cffi to core deps**

In `pyproject.toml` `[project].dependencies`, add `"argon2-cffi",` (auth is core, not the `ml` extra).

- [ ] **Step 2: Sync**

Run: `uv sync --extra ml`  (the `--extra ml` is REQUIRED — a plain `uv sync` uninstalls
torch/wordcloud/kaleido and breaks the chart/export tests.)
Expected: installs `argon2-cffi` (+ `argon2-cffi-bindings`), ml extras retained.

- [ ] **Step 3: Extend config**

In `app/config.py`, inside `Settings`, add fields (near the filesystem layout block):

```python
    registry_path: Path = Path("./registry.db")
    data_dir: Path = Path("./data")
    session_secret: str | None = None      # auto-generated into .env on first run
    register_code: str | None = None       # if set, registration requires this code
```

- [ ] **Step 4: Add a session-secret bootstrapper**

In `app/config.py`, after `settings = Settings()`, add:

```python
def ensure_session_secret() -> str:
    """Return a stable session secret, generating + persisting one to .env if absent."""
    import secrets

    from dotenv import set_key

    if settings.session_secret:
        return settings.session_secret
    secret = secrets.token_urlsafe(48)
    set_key(".env", "SESSION_SECRET", secret)
    settings.session_secret = secret
    return secret
```

- [ ] **Step 5: gitignore registry + data**

In `.gitignore`, under "Secrets & local data", add:

```
registry.db
registry.db-journal
data/
```

- [ ] **Step 6: Verify config imports**

Run: `uv run python -c "from app.config import settings; print(settings.registry_path, settings.data_dir)"`
Expected: `registry.db data` (paths print, no error).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock app/config.py .gitignore
git commit -m "Multi-account task 1: argon2 dep + registry/session config"
```

---

## Task 2: Password hashing (argon2)

**Files:**
- Create: `app/auth.py` (hashing only for now)
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

`tests/test_auth.py`:

```python
"""Tests for password hashing + (later) auth dependencies."""

from app.auth import hash_password, verify_password


def test_hash_is_not_plaintext_and_verifies():
    h = hash_password("correct horse")
    assert h != "correct horse"
    assert h.startswith("$argon2")
    assert verify_password(h, "correct horse") is True


def test_verify_rejects_wrong_password():
    h = hash_password("s3cret-pass")
    assert verify_password(h, "wrong") is False


def test_hashes_are_salted_unique():
    assert hash_password("same") != hash_password("same")
```

- [ ] **Step 2: Run, expect fail**

Run: `uv run pytest tests/test_auth.py -q`
Expected: FAIL (`ModuleNotFoundError: app.auth`).

- [ ] **Step 3: Implement hashing**

`app/auth.py`:

```python
"""Authentication: argon2 password hashing + session-backed dependencies."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

_ph = PasswordHasher()  # argon2id defaults (OWASP-reasonable)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
```

- [ ] **Step 4: Run, expect pass**

Run: `uv run pytest tests/test_auth.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/auth.py tests/test_auth.py
git commit -m "Multi-account task 2: argon2 password hashing"
```

---

## Task 3: Registry DB (users + accounts)

**Files:**
- Create: `app/registry_migrations/001_registry.sql`, `app/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Schema file**

`app/registry_migrations/001_registry.sql`:

```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ig_accounts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    ig_user_id       TEXT NOT NULL,
    username         TEXT,
    access_token     TEXT NOT NULL,
    token_expires_at TEXT,
    db_path          TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (user_id, ig_user_id)
);
```

- [ ] **Step 2: Write failing tests**

`tests/test_registry.py`:

```python
from __future__ import annotations

import pytest

from app import registry


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    c = registry.connect()
    registry.run_migrations(c)
    yield c
    c.close()


def test_create_and_get_user(conn):
    uid = registry.create_user(conn, "alice", "hash123")
    u = registry.get_user_by_name(conn, "alice")
    assert u["id"] == uid and u["password_hash"] == "hash123"


def test_username_unique(conn):
    registry.create_user(conn, "bob", "h")
    with pytest.raises(Exception):
        registry.create_user(conn, "bob", "h2")


def test_create_list_get_account(conn):
    uid = registry.create_user(conn, "carol", "h")
    aid = registry.create_account(conn, uid, ig_user_id="111", username="carol_ig",
                                  access_token="tok", token_expires_at=None)
    accounts = registry.list_accounts(conn, uid)
    assert len(accounts) == 1 and accounts[0]["id"] == aid
    acct = registry.get_account(conn, aid)
    assert acct["ig_user_id"] == "111"
    assert acct["db_path"].endswith(f"acct_{aid}.db")


def test_update_account_token(conn):
    uid = registry.create_user(conn, "dave", "h")
    aid = registry.create_account(conn, uid, "1", "dave_ig", "old", None)
    registry.update_account_token(conn, aid, "new", "2026-07-01T00:00:00Z")
    acct = registry.get_account(conn, aid)
    assert acct["access_token"] == "new"
    assert acct["token_expires_at"] == "2026-07-01T00:00:00Z"
```

- [ ] **Step 3: Run, expect fail**

Run: `uv run pytest tests/test_registry.py -q`
Expected: FAIL (`ModuleNotFoundError: app.registry`).

- [ ] **Step 4: Implement registry**

`app/registry.py`:

```python
"""Registry DB: login users + their IG accounts (with per-account tokens + db paths)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings

_MIGRATIONS = Path(__file__).parent / "registry_migrations"


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or settings.registry_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (version TEXT PRIMARY KEY, applied_at TEXT)"
    )
    applied = {r[0] for r in conn.execute("SELECT version FROM _migrations")}
    for sql_file in sorted(_MIGRATIONS.glob("*.sql")):
        if sql_file.name in applied:
            continue
        conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO _migrations (version, applied_at) VALUES (?, ?)",
            (sql_file.name, datetime.now(UTC).isoformat()),
        )
    conn.commit()


def create_user(conn: sqlite3.Connection, username: str, password_hash: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_user_by_name(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_account(
    conn: sqlite3.Connection,
    user_id: int,
    ig_user_id: str,
    username: str | None,
    access_token: str,
    token_expires_at: str | None,
) -> int:
    cur = conn.execute(
        """INSERT INTO ig_accounts
           (user_id, ig_user_id, username, access_token, token_expires_at, db_path, created_at)
           VALUES (?, ?, ?, ?, ?, '', ?)""",
        (user_id, ig_user_id, username, access_token, token_expires_at,
         datetime.now(UTC).isoformat()),
    )
    aid = int(cur.lastrowid)
    db_path = str(settings.data_dir / f"acct_{aid}.db")
    conn.execute("UPDATE ig_accounts SET db_path = ? WHERE id = ?", (db_path, aid))
    conn.commit()
    return aid


def list_accounts(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ig_accounts WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()


def get_account(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM ig_accounts WHERE id = ?", (account_id,)).fetchone()


def update_account_token(
    conn: sqlite3.Connection, account_id: int, access_token: str, token_expires_at: str | None
) -> None:
    conn.execute(
        "UPDATE ig_accounts SET access_token = ?, token_expires_at = ? WHERE id = ?",
        (access_token, token_expires_at, account_id),
    )
    conn.commit()
```

- [ ] **Step 5: Run, expect pass**

Run: `uv run pytest tests/test_registry.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add app/registry.py app/registry_migrations tests/test_registry.py
git commit -m "Multi-account task 3: registry DB (users + ig_accounts)"
```

---

## Task 4: Shared IG account bootstrap (token exchange)

Extract the Facebook-Login token exchange + account discovery from `cli.py` into a
reusable function used by both in-app add-account and `cli migrate`.

**Files:**
- Create: `app/ig_setup.py`
- Test: `tests/test_ig_setup.py`

- [ ] **Step 1: Write failing test (httpx MockTransport — no real API)**

`tests/test_ig_setup.py`:

```python
from __future__ import annotations

import httpx
import pytest

from app.ig_setup import IGSetupError, discover_account


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://graph.facebook.com/v21.0")


def test_discover_account_happy_path():
    def handler(request: httpx.Request) -> httpx.Response:
        p = str(request.url)
        if "me/accounts" in p:
            return httpx.Response(200, json={"data": [{"id": "PAGE1", "name": "P"}]})
        if "PAGE1" in p and "instagram_business_account" in p:
            return httpx.Response(200, json={"instagram_business_account": {"id": "IG99"}})
        if "oauth/access_token" in p:
            return httpx.Response(200, json={"access_token": "LONG", "expires_in": 5184000})
        if p.rstrip("/").endswith("/IG99"):
            return httpx.Response(200, json={"username": "handle99"})
        return httpx.Response(404, json={"error": {"message": "no"}})

    info = discover_account("SHORT", app_secret="sek", client=_client(handler))
    assert info.ig_user_id == "IG99"
    assert info.username == "handle99"
    assert info.access_token == "LONG"
    assert info.token_expires_at is not None


def test_discover_account_no_pages():
    def handler(request):
        return httpx.Response(200, json={"data": []})
    with pytest.raises(IGSetupError):
        discover_account("SHORT", app_secret="sek", client=_client(handler))
```

- [ ] **Step 2: Run, expect fail**

Run: `uv run pytest tests/test_ig_setup.py -q`
Expected: FAIL (`ModuleNotFoundError: app.ig_setup`).

- [ ] **Step 3: Implement**

`app/ig_setup.py`:

```python
"""Shared IG account bootstrap: exchange a short-lived token for a long-lived one and
discover the IG business account (Facebook Login path). Used by in-app add-account
and `cli migrate`. Pure-ish: accepts an injectable httpx.Client for testing."""

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
            expires_at = (datetime.now(UTC) + timedelta(seconds=int(exch["expires_in"]))).isoformat()
        profile = get(ig_user_id, fields="username", access_token=long_token)
        return AccountInfo(ig_user_id, profile.get("username"), long_token, expires_at)
    except httpx.HTTPStatusError as e:
        raise IGSetupError(f"Graph API error: {e.response.status_code}") from e
    finally:
        if own:
            c.close()
```

- [ ] **Step 4: Run, expect pass**

Run: `uv run pytest tests/test_ig_setup.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/ig_setup.py tests/test_ig_setup.py
git commit -m "Multi-account task 4: shared IG account bootstrap (token exchange)"
```

---

## Task 5: Sessions + auth dependencies

**Files:**
- Modify: `app/auth.py` (add dependencies), `app/main.py` (SessionMiddleware + registry startup)
- Test: `tests/test_auth.py` (extend)

- [ ] **Step 1: Add dependency tests**

Append to `tests/test_auth.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app import auth, registry


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    c = registry.connect(); registry.run_migrations(c)
    uid = registry.create_user(c, "alice", auth.hash_password("pw"))
    aid = registry.create_account(c, uid, "1", "alice_ig", "tok", None)
    other = registry.create_user(c, "bob", auth.hash_password("pw"))
    other_aid = registry.create_account(c, other, "2", "bob_ig", "tok2", None)
    c.close()

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")

    @app.get("/whoami")
    def whoami(user=auth.current_user):
        return PlainTextResponse(user["username"])

    @app.get("/acct")
    def acct(account=auth.current_account):
        return PlainTextResponse(str(account["id"]))

    @app.post("/setsession")
    def setsession(request: __import__("fastapi").Request, uid: int, aid: int):
        request.session["user_id"] = uid
        request.session["account_id"] = aid
        return PlainTextResponse("ok")

    return TestClient(app), uid, aid, other_aid


def test_current_user_redirects_when_anonymous(app_client):
    client, *_ = app_client
    r = client.get("/whoami", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/login"


def test_current_account_blocks_foreign_account(app_client):
    client, uid, aid, other_aid = app_client
    client.post(f"/setsession?uid={uid}&aid={other_aid}")  # alice claims bob's account
    r = client.get("/acct", follow_redirects=False)
    assert r.status_code in (302, 307)  # ownership re-check fails -> redirect, not 200


def test_current_account_allows_own_account(app_client):
    client, uid, aid, other_aid = app_client
    client.post(f"/setsession?uid={uid}&aid={aid}")
    assert client.get("/acct").text == str(aid)
```

- [ ] **Step 2: Run, expect fail**

Run: `uv run pytest tests/test_auth.py -q`
Expected: FAIL (`current_user` / `current_account` undefined).

- [ ] **Step 3: Implement dependencies in `app/auth.py`**

Append to `app/auth.py`:

```python
from fastapi import Depends, Request

from app import registry


class _Redirect(Exception):
    def __init__(self, to: str):
        self.to = to


def _require_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        raise _Redirect("/login")
    conn = registry.connect()
    try:
        user = registry.get_user(conn, uid)
    finally:
        conn.close()
    if user is None:
        raise _Redirect("/login")
    return user


def _require_account(request: Request, user=Depends(_require_user)):
    aid = request.session.get("account_id")
    if not aid:
        raise _Redirect("/accounts")
    conn = registry.connect()
    try:
        account = registry.get_account(conn, aid)
    finally:
        conn.close()
    # Cross-account guard: the account must belong to the logged-in user.
    if account is None or account["user_id"] != user["id"]:
        raise _Redirect("/accounts")
    return account


current_user = Depends(_require_user)
current_account = Depends(_require_account)
```

- [ ] **Step 4: Register an exception handler so `_Redirect` becomes a 302**

In `app/main.py`, after `app = FastAPI(...)`, add:

```python
from starlette.middleware.sessions import SessionMiddleware

from app.auth import _Redirect
from app.config import ensure_session_secret
from app import registry as _registry

app.add_middleware(SessionMiddleware, secret_key=ensure_session_secret())


@app.exception_handler(_Redirect)
async def _redirect_handler(request, exc: _Redirect):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(exc.to, status_code=302)
```

And in the `lifespan` startup, after the per-account migration block, initialize the registry:

```python
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    rconn = _registry.connect()
    _registry.run_migrations(rconn)
    rconn.close()
```

- [ ] **Step 5: Run, expect pass**

Run: `uv run pytest tests/test_auth.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add app/auth.py app/main.py tests/test_auth.py
git commit -m "Multi-account task 5: sessions + current_user/current_account guards"
```

---

## Task 6: Auth routes + templates

**Files:**
- Create: `app/routes/auth_routes.py`, `app/templates/register.html`, `app/templates/login.html`
- Modify: `app/main.py` (include router)
- Test: `tests/test_auth_routes.py`

- [ ] **Step 1: Write failing tests**

`tests/test_auth_routes.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import registry


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(registry.settings, "register_code", None)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_register_then_login(client):
    r = client.post("/register", data={"username": "alice", "password": "password1",
                                       "confirm": "password1"}, follow_redirects=False)
    assert r.status_code == 302  # auto-login -> /accounts
    # session is set; hitting /accounts should be 200 (no redirect to /login)
    assert client.get("/accounts").status_code == 200


def test_register_password_mismatch(client):
    r = client.post("/register", data={"username": "x", "password": "aaaaaaaa",
                                       "confirm": "bbbbbbbb"})
    assert r.status_code == 200
    assert "sandi" in r.text.lower()  # inline error mentions password


def test_login_wrong_password(client):
    client.post("/register", data={"username": "joe", "password": "password1",
                                   "confirm": "password1"})
    client.get("/logout")
    r = client.post("/login", data={"username": "joe", "password": "nope"})
    assert r.status_code == 200
    assert "salah" in r.text.lower()  # error
```

- [ ] **Step 2: Run, expect fail**

Run: `uv run pytest tests/test_auth_routes.py -q`
Expected: FAIL (routes/templates missing).

- [ ] **Step 3: Templates**

`app/templates/register.html` (extends base, centered card):

```html
{% extends "base.html" %}
{% block title %}Daftar — IG Pulse{% endblock %}
{% block content %}
<div class="auth-wrap">
  <article class="card auth-card">
    <div class="brand-mark" style="font-family:var(--font-display);font-size:32px;font-weight:700;letter-spacing:-0.04em;">Pulse<span style="color:var(--accent)">.</span></div>
    <div class="card-sub" style="margin-bottom:24px;">Analitik Komentar IG</div>
    <h1 class="card-title" style="margin-bottom:24px;">Buat <em>akun</em> baru.</h1>
    {% if error %}<div class="auth-error">{{ error }}</div>{% endif %}
    <form method="post" action="/register">
      <label class="auth-label">Nama pengguna</label>
      <input class="auth-input" name="username" value="{{ username or '' }}" required autofocus />
      <label class="auth-label">Kata sandi</label>
      <input class="auth-input" type="password" name="password" required />
      <label class="auth-label">Ulangi kata sandi</label>
      <input class="auth-input" type="password" name="confirm" required />
      {% if needs_code %}
      <label class="auth-label">Kode undangan</label>
      <input class="auth-input" name="code" required />
      {% endif %}
      <button class="cta" type="submit" style="margin-top:20px;">Daftar →</button>
    </form>
    <div class="auth-foot">Sudah punya akun? <a href="/login">Masuk →</a></div>
  </article>
</div>
{% endblock %}
```

`app/templates/login.html` (same structure; title `Selamat <em>datang</em> kembali.`, fields username + password, button `Masuk →`, foot `Belum punya akun? <a href="/register">Daftar →</a>`).

Add to `app/static/css/app.css`:

```css
.auth-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }
.auth-card { width: 100%; max-width: 420px; }
.auth-label { display: block; font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.15em; opacity: 0.6; margin: 14px 0 6px; }
.auth-input { width: 100%; padding: 10px 12px; border: 1px solid var(--on-card-line); border-radius: var(--radius-sm); background: var(--on-card-fill); color: inherit; font-family: var(--font-body); font-size: 15px; }
.auth-error { background: rgba(255,91,53,0.14); color: var(--neg); padding: 10px 12px; border-radius: var(--radius-sm); font-size: 13px; margin-bottom: 8px; }
.auth-foot { margin-top: 20px; font-size: 13px; opacity: 0.7; }
.auth-foot a { color: var(--accent); }
```

- [ ] **Step 4: Routes**

`app/routes/auth_routes.py`:

```python
"""Registration, login, logout."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import auth, registry
from app.config import settings
from app.templating import templates

router = APIRouter()


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(
        request, "register.html", {"needs_code": bool(settings.register_code)}
    )


@router.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...),
             confirm: str = Form(...), code: str = Form("")):
    ctx = {"needs_code": bool(settings.register_code), "username": username}
    if settings.register_code and code != settings.register_code:
        ctx["error"] = "Kode undangan salah."
    elif password != confirm:
        ctx["error"] = "Kata sandi tidak cocok."
    elif len(password) < 8:
        ctx["error"] = "Kata sandi minimal 8 karakter."
    if "error" in ctx:
        return templates.TemplateResponse(request, "register.html", ctx)

    conn = registry.connect()
    try:
        if registry.get_user_by_name(conn, username):
            ctx["error"] = "Nama pengguna sudah dipakai."
            return templates.TemplateResponse(request, "register.html", ctx)
        uid = registry.create_user(conn, username, auth.hash_password(password))
    finally:
        conn.close()
    request.session["user_id"] = uid
    return RedirectResponse("/accounts", status_code=302)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = registry.connect()
    try:
        user = registry.get_user_by_name(conn, username)
    finally:
        conn.close()
    if user is None or not auth.verify_password(user["password_hash"], password):
        return templates.TemplateResponse(
            request, "login.html", {"error": "Nama pengguna atau kata sandi salah.", "username": username}
        )
    request.session["user_id"] = user["id"]
    return RedirectResponse("/accounts", status_code=302)


@router.post("/logout")
@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
```

In `app/main.py`, include it: `from app.routes import auth_routes` then `app.include_router(auth_routes.router)`.

- [ ] **Step 5: Run, expect pass**

Run: `uv run pytest tests/test_auth_routes.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routes/auth_routes.py app/templates/register.html app/templates/login.html app/static/css/app.css app/main.py tests/test_auth_routes.py
git commit -m "Multi-account task 6: register/login/logout + templates"
```

---

## Task 7: Accounts routes + page (list / switch / add)

**Files:**
- Create: `app/routes/accounts.py`, `app/templates/accounts.html`
- Modify: `app/main.py`
- Test: `tests/test_accounts_routes.py`

- [ ] **Step 1: Write failing tests**

`tests/test_accounts_routes.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, registry


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    from app.main import app
    with TestClient(app) as c:
        c.post("/register", data={"username": "al", "password": "password1", "confirm": "password1"})
        yield c


def test_accounts_page_lists_empty(client):
    r = client.get("/accounts")
    assert r.status_code == 200
    assert "Tambah akun Instagram" in r.text


def test_switch_to_foreign_account_blocked(client, monkeypatch):
    # create a second user's account directly in registry
    conn = registry.connect(); other = registry.create_user(conn, "ev", "h")
    foreign = registry.create_account(conn, other, "9", "ev_ig", "t", None); conn.close()
    r = client.post("/accounts/switch", data={"account_id": foreign}, follow_redirects=False)
    # ownership enforced: redirected back to /accounts without setting session
    assert r.status_code == 302
    assert client.get("/", follow_redirects=False).headers["location"] == "/accounts"


def test_add_account_calls_discover(client, monkeypatch):
    from app import ig_setup

    def fake_discover(short_token, **kw):
        return ig_setup.AccountInfo("IG1", "myhandle", "LONGTOK", "2026-07-01T00:00:00Z")

    monkeypatch.setattr("app.routes.accounts.discover_account", fake_discover)
    monkeypatch.setattr("app.routes.accounts._kickoff_fetch", lambda *a, **k: None)
    r = client.post("/accounts/add", data={"short_token": "SHORT"}, follow_redirects=False)
    assert r.status_code == 302  # created + set active -> redirect to /
    # the account now exists + db file created
    conn = registry.connect()
    accts = registry.list_accounts(conn, registry.get_user_by_name(conn, "al")["id"])
    conn.close()
    assert len(accts) == 1 and accts[0]["username"] == "myhandle"
```

- [ ] **Step 2: Run, expect fail**

Run: `uv run pytest tests/test_accounts_routes.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Template**

`app/templates/accounts.html` (extends base): a centered column listing the user's accounts (each a `.card` with `@username`, token-expiry badge, "Gunakan" switch button via `hx-post`/form, and "Buka dasbor"), plus an **"Tambah akun Instagram"** card with a `<form method="post" action="/accounts/add">` containing a `<textarea name="short_token">` (paste short-lived token), a help line linking to `docs/phase0-setup.md`, and a `Hubungkan →` `.cta`. Include a `logout` link. Reuse `.card`, `.cta`, `.badge`, `.auth-*` classes. Show `error` if present.

- [ ] **Step 4: Routes**

`app/routes/accounts.py`:

```python
"""IG account management: list, switch, add (paste-token), refresh-token."""

from __future__ import annotations

import asyncio
import logging
import threading

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import auth, registry
from app.db import connect as data_connect
from app.db import run_migrations as data_migrations
from app.ig_setup import IGSetupError, discover_account
from app.templating import templates

router = APIRouter()
logger = logging.getLogger("ig_pulse.routes.accounts")


def _kickoff_fetch(db_path: str, token: str) -> None:
    def run():
        try:
            from app.analysis.sentiment import analyze_comments
            from app.db import connect
            from app.fetch import fetch_all
            asyncio.run(fetch_all(db_path=db_path, access_token=token))
            c = connect(db_path); analyze_comments(c); c.close()
        except Exception:
            logger.exception("first fetch failed for %s", db_path)
    threading.Thread(target=run, daemon=True).start()


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
                {"accounts": accounts, "active": request.session.get("account_id"), "error": str(e)},
            )
        aid = registry.create_account(conn, user["id"], info.ig_user_id, info.username,
                                      info.access_token, info.token_expires_at)
        acct = registry.get_account(conn, aid)
    finally:
        conn.close()
    dconn = data_connect(acct["db_path"]); data_migrations(dconn); dconn.close()
    _kickoff_fetch(acct["db_path"], info.access_token)
    request.session["account_id"] = aid
    return RedirectResponse("/", status_code=302)
```

In `app/main.py`: `from app.routes import accounts` + `app.include_router(accounts.router)`.

- [ ] **Step 5: Run, expect pass**

Run: `uv run pytest tests/test_accounts_routes.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routes/accounts.py app/templates/accounts.html app/main.py tests/test_accounts_routes.py
git commit -m "Multi-account task 7: account list/switch/add (paste-token)"
```

---

## Task 8: Per-account routing in dashboard / analysis / export

**Files:**
- Modify: `app/fetch.py`, `app/routes/dashboard.py`, `app/routes/analysis.py`, `app/routes/export.py`

- [ ] **Step 1: Make `fetch_all` accept db_path + token**

In `app/fetch.py`, change `fetch_all` signature + connection + client:

```python
async def fetch_all(
    conn: sqlite3.Connection | None = None,
    *,
    db_path: str | None = None,
    access_token: str | None = None,
    with_replies: bool = True,
) -> dict:
    own = conn is None
    db = conn if conn is not None else connect(db_path)
    if own:
        run_migrations(db)
    try:
        return await _run_fetch(db, with_replies, access_token)
    finally:
        if own:
            db.close()
```

In `_run_fetch(conn, with_replies, access_token)`, change `async with IGClient() as ig:` to `async with IGClient(access_token=access_token) as ig:`. (IGClient already falls back to settings when `access_token` is None — preserves single-account/legacy behavior.)

- [ ] **Step 2: Scope dashboard routes to the active account**

In `app/routes/dashboard.py`:
- Add `from app import auth, registry`.
- `index`, `set_scope`, `refresh`, `refresh_status` gain a parameter `account=auth.current_account`.
- In `index`/`set_scope`/analysis data access, replace `connect()` with `connect(account["db_path"])`.
- Hero/sidebar: pass `ig_username=account["username"]`, `token_days_left=_days_left(account["token_expires_at"])`, and `accounts` (for the switcher) loaded via `registry.list_accounts`.
- `_do_refresh` becomes account-aware: capture `db_path` + `token` before starting the thread and call `fetch_all(db_path=db_path, access_token=token)` + `analyze_comments(connect(db_path))`. Keep the `_refresh_state` lock.

- [ ] **Step 3: Scope analysis + export to the active account**

In `app/routes/analysis.py` and `app/routes/export.py`:
- Add `account=auth.current_account` to every route.
- Change `scope_data(scope_type, scope_value)` to `scope_data(db_path, scope_type, scope_value)` and open `connect(db_path)`; pass `account["db_path"]` from each route.
- In `export.py`, the download route opens the account DB the same way.

- [ ] **Step 4: Run full suite**

Run: `uv run pytest -q`
Expected: existing analysis/render/svg tests still PASS; `test_routes.py` will FAIL until Task 10 (it doesn't log in yet). That's expected; proceed.

- [ ] **Step 5: Commit**

```bash
git add app/fetch.py app/routes/dashboard.py app/routes/analysis.py app/routes/export.py
git commit -m "Multi-account task 8: route data scoped to the active account"
```

---

## Task 9: `cli migrate`

**Files:**
- Modify: `app/cli.py`

- [ ] **Step 1: Add the migrate command**

In `app/cli.py`, add:

```python
def cmd_migrate(args: argparse.Namespace) -> None:
    import getpass
    import shutil

    from app import auth, registry
    from app.config import settings

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
```

Add subparser in `build_parser`:

```python
    m = sub.add_parser("migrate", help="One-time: import the .env single account into the registry")
    m.add_argument("--username")
    m.add_argument("--password")
    m.set_defaults(func=cmd_migrate)
```

- [ ] **Step 2: Verify the command parses**

Run: `uv run python -m app.cli migrate --help`
Expected: shows `--username` / `--password` options.

- [ ] **Step 3: Commit**

```bash
git add app/cli.py
git commit -m "Multi-account task 9: cli migrate (import .env account into registry)"
```

---

## Task 10: Update existing route tests + docs + full verify

**Files:**
- Modify: `tests/test_routes.py`, `docs/decisions.md`

- [ ] **Step 1: Make `test_routes.py` log in + add an account**

Update the `client` fixture in `tests/test_routes.py` to: point `registry_path`/`data_dir` at tmp, build the app, register a user, create an account via `registry` with `db_path` = a migrated temp data DB, set the session (`/accounts/switch`). Then existing assertions run against the active account. Concretely, replace the fixture body with:

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "legacy.db")
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    from app.main import app
    with TestClient(app) as c:
        c.post("/register", data={"username": "u", "password": "password1", "confirm": "password1"})
        rconn = registry.connect()
        uid = registry.get_user_by_name(rconn, "u")["id"]
        aid = registry.create_account(rconn, uid, "1", "u_ig", "tok", None)
        acct = registry.get_account(rconn, aid); rconn.close()
        from app.db import connect as dconn, run_migrations
        d = dconn(acct["db_path"]); run_migrations(d); d.close()
        c.post("/accounts/switch", data={"account_id": aid})
        yield c
```

Add imports `from app import registry`. Existing tests (dashboard 200, fragments 200, scope, export 404) then pass against the empty per-account DB.

- [ ] **Step 2: Record deviations**

Append to `docs/decisions.md`:

```markdown
## Multi-account (Phase 2) — 2026-05-23

- B1 scope: multi-account promoted from out-of-MVP, user-approved.
- B12 deviation: per-account IG tokens are stored in registry.db (plaintext,
  gitignored, local-only) — same trust level as the prior single .env token.
  FB_APP_ID/SECRET remain in .env (one shared Meta app; each IG is a tester).
- Auth: argon2 (argon2-cffi). Sessions via Starlette SessionMiddleware.
```

- [ ] **Step 3: Full suite + lint**

Run: `uv run pytest -q && uv run ruff check`
Expected: all PASS, ruff clean.

- [ ] **Step 4: Manual smoke (real)**

```bash
uv run python -m app.cli migrate --username you --password <pw>   # imports your .env account
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```
Open `http://192.168.1.13:8001` → redirected to `/login` → log in → `/accounts` shows your migrated account → open dashboard (your data) → register a 2nd user in another browser/profile → add their account → confirm isolation.

- [ ] **Step 5: Commit**

```bash
git add tests/test_routes.py docs/decisions.md
git commit -m "Multi-account task 10: login-gated route tests + decisions doc"
```

---

## Notes for the implementer

- **Cross-account guard is the security crux** (Task 5 `_require_account`, Task 7 switch): always re-check `account.user_id == session.user_id`. Tests in Tasks 5 & 7 cover it — do not weaken them.
- **Legacy compatibility:** `IGClient(access_token=None)` and `fetch_all()` with no args still fall back to `.env` — keeps the old CLI `fetch` working pre-migration.
- **Order matters:** Tasks 1–7 keep the full suite green; Task 8 intentionally breaks `test_routes.py` until Task 10 fixes the fixture. Don't "fix" it earlier.
