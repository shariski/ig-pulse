# Phase 0 — One-time Meta / Instagram setup (manual, ~30–60 min)

This is the **human prerequisite** for everything else. No code agent can do these
steps for you — they involve clicking through Meta's web UIs and authorizing access.
Source of truth: `api-integration.md`. This file is the checklist; that file has the
detailed reasoning.

When you finish, you will have four values in `.env` (copy from `.env.example`):
`FB_APP_ID`, `FB_APP_SECRET`, `IG_USER_ID`, `IG_ACCESS_TOKEN`.

> Tip: the `python -m app.cli setup` command automates steps **6–8** for you once you
> have a short-lived token + App ID + App Secret. You still do steps 1–5 by hand.

---

## Checklist

### 1. Confirm IG account type + Facebook Page link
- [ ] IG app → Settings → Account → confirm **Creator** or **Business**
- [ ] IG app → Settings → Business/Creator tools → **Connect a Facebook Page**
      (create a free, empty Page at facebook.com/pages/create if you don't have one)
- [ ] Verify on the FB Page → Settings → Linked Accounts → your IG is listed

### 2. Create a Meta Developer account
- [ ] developers.facebook.com → "Get Started" → log in with the account that admins the Page
- [ ] Accept developer terms

### 3. Create an app
- [ ] developers.facebook.com/apps → "Create App"
- [ ] Use case: **Other** → type: **Business**
- [ ] Name: e.g. `ig-pulse-personal`

### 4. Add the Instagram Graph API product
- [ ] App dashboard → "Add Product" → **Instagram Graph API** → Set Up

### 5. Generate a SHORT-LIVED token (Graph API Explorer)
- [ ] developers.facebook.com/tools/explorer
- [ ] Top-right: select your app
- [ ] "Generate Access Token", requesting these permissions:
      - [ ] `instagram_basic`
      - [ ] `instagram_manage_comments`
      - [ ] `pages_show_list`
      - [ ] `pages_read_engagement`
      - [ ] `business_management` (optional)
- [ ] Authorize → copy the short-lived token (good ~1 hour)
- [ ] Grab **App ID** and **App Secret** from app dashboard → Settings → Basic

### 6–8. Automated by the CLI

Create your `.env` first:

```bash
cp .env.example .env
# put FB_APP_ID and FB_APP_SECRET in .env now (from step 5)
```

Then run:

```bash
uv run python -m app.cli setup --short-token "PASTE_SHORT_LIVED_TOKEN"
```

This will:
- **(6)** call `/me/accounts`, find your linked Page, read its
  `instagram_business_account` → your `IG_USER_ID`
- **(7)** exchange the short-lived token for a long-lived (~60-day) token
- **(8)** smoke-test `GET /{IG_USER_ID}?fields=username,followers_count,media_count`
- write `IG_USER_ID` and `IG_ACCESS_TOKEN` into `.env` (the token is never printed)

If you have multiple Pages, pass `--page-id <id>` to pick one.

#### Or do steps 6–8 by hand (Graph API Explorer)
```
GET /me/accounts                                  → note the linked Page's id
GET /{page-id}?fields=instagram_business_account  → that id is your IG_USER_ID
GET /oauth/access_token?grant_type=fb_exchange_token
    &client_id={app-id}&client_secret={app-secret}
    &fb_exchange_token={short-lived-token}        → long-lived token
GET /{IG_USER_ID}?fields=username,followers_count,media_count   → smoke test
```

---

## Done when
- [ ] `.env` has all four values filled
- [ ] `uv run python -c "from app.config import settings; settings.require_ig_credentials(); print('creds OK')"` prints `creds OK`

## After Phase 0
Token refresh is **manual** in MVP (no scheduler). Before the ~60-day expiry, run:
```bash
uv run python -m app.cli refresh-token
```
Put a calendar reminder ~day 50. (Auto-refresh is Phase 2.)

Next coding step is **Phase 2** — build `app/ig_client.py` and verify V1–V6 against
the real API, saving fixtures to `tests/fixtures/`. Those fixtures unblock the
parallel analysis + render waves.
