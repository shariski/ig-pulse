# Phase 0 — One-time Instagram setup (Instagram API with Instagram Login)

This is the **human prerequisite** for everything else. No code agent can do these
steps — they involve clicking through Meta's developer console and authorizing access.

We use the **Instagram API with Instagram Login** path (host `graph.instagram.com`),
because that's how the "Pulse" app is configured. The scopes we need are
`instagram_business_basic` (profile + media) and `instagram_manage_comments` (comments).
We do NOT need DMs or a Facebook Page traversal.

When you finish, `.env` will have `IG_USER_ID` + `IG_ACCESS_TOKEN` filled
(the CLI writes them). `FB_APP_ID` / `FB_APP_SECRET` come from the app dashboard.

---

## Checklist

### 1. Account + app (done)
- [x] Instagram account is **Creator or Business**
- [x] Meta Developer account created
- [x] App created ("Pulse")
- [x] `FB_APP_ID` + `FB_APP_SECRET` in `.env` (App settings → Basic)

### 2. Instagram Login use case
- [ ] App dashboard → **Kasus penggunaan (Use cases)** → the Instagram use case
- [ ] Confirm permissions include `instagram_business_basic` + `instagram_manage_comments`

### 3. Authorize your account (fixes "Peran developer tidak memadai")
The token generator only works for accounts with a role on the app in dev mode.
- [ ] App dashboard → **Peran aplikasi (App roles)** → add your Instagram account as a
      **tester** (if prompted)
- [ ] Accept the invite inside Instagram: Settings → **Apps and websites** (or
      "Website permissions") → **Tester invites** → Accept

### 4. Generate a token
- [ ] In the Instagram use case → **Generate access tokens** → **Add account** →
      log in with your Instagram account → authorize
- [ ] Copy the generated token

### 5. Hand it to the CLI
```bash
uv run python -m app.cli setup --short-token "PASTE_TOKEN"
```
This validates the token, reads your `IG_USER_ID`, exchanges for a long-lived
(~60-day) token (best-effort), smoke-tests, and writes `.env`.

> **If you see "long-lived exchange failed"**: the *Instagram* app secret differs
> from your Facebook app secret. Find the Instagram app secret in the Instagram
> Login use-case settings, add `IG_APP_SECRET=...` to `.env`, and re-run setup.
> (If the dashboard already gave you a long-lived token, you can ignore the warning.)

---

## Done when
- [ ] `setup` prints `Smoke test OK: @yourhandle ...`
- [ ] `uv run python -c "from app.config import settings; settings.require_ig_credentials(); print('creds OK')"` prints `creds OK`

## After Phase 0
Refresh is **manual** in MVP. Before the ~60-day expiry:
```bash
uv run python -m app.cli refresh-token
```
Calendar reminder ~day 50. Next coding step is **Phase 2** — verify V1–V6 against
the real API and save fixtures to `tests/fixtures/`, which unblocks the parallel
analysis + render waves.
