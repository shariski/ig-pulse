# API Integration — Meta Instagram Graph API

This doc covers the one-time setup to get a working access token, and what you need to verify against real data before building analysis code.

## Confirmed facts (verified as of writing)

- Instagram Basic Display API is dead (shut down Dec 4, 2024). Graph API is the only path.
- Graph API requires Creator or Business account linked to a Facebook Page.
- For analyzing **your own account only**, no Meta App Review is needed — the app stays in development mode permanently.
- Rate limit formula: 4800 × Impressions over last 24h. For a personal-tier account with normal traffic, this is multiple thousand calls/day available. Not a bottleneck for our use case.
- Token: short-lived (~1 hour) → long-lived (60 days) → refresh before expiry.

## Setup walkthrough (one-time, ~30–60 min)

### Step 1: Confirm IG account type and Facebook Page link

1. Open IG app → Settings → Account → confirm "Creator" or "Business" account.
2. In IG app: Settings → Business/Creator tools → Connect a Facebook Page.
3. If no FB Page exists, create one at facebook.com/pages/create. Can be empty, no posts needed. Free.

Verify by going to your FB Page → Settings → Linked Accounts. Your IG should be listed.

### Step 2: Create Meta Developer account

1. Go to developers.facebook.com → "Get Started".
2. Log in with the Facebook account that admins the Page from Step 1.
3. Accept developer terms.

### Step 3: Create an app

1. developers.facebook.com/apps → "Create App".
2. Use case: "Other" → app type: "Business".
3. Name: e.g. "ig-pulse-personal". (Visible only to you.)
4. After creation, you land on the app dashboard.

### Step 4: Add Instagram Graph API product

1. App dashboard → "Add Product" → find "Instagram Graph API" → Set Up.
2. This adds the product and exposes its config.

### Step 5: Get an access token

The fastest path is via Graph API Explorer:

1. developers.facebook.com/tools/explorer
2. Top-right: select your app from the dropdown.
3. Click "Generate Access Token".
4. Permissions to request (add each via the dropdown):
   - `instagram_basic`
   - `instagram_manage_comments`
   - `pages_show_list`
   - `pages_read_engagement`
   - `business_management` (optional, for some metadata)
5. Authorize → you get a short-lived user token (good for ~1 hour).

### Step 6: Get your IG Business Account ID

In Graph API Explorer with the token from Step 5:

```
GET /me/accounts
```

This returns your FB Pages. Note the `id` of the page linked to your IG.

```
GET /{page-id}?fields=instagram_business_account
```

Returns `{ "instagram_business_account": { "id": "1784xxxxxxxx" } }`. **This is your `IG_USER_ID`.** Save it.

### Step 7: Exchange for long-lived token

```
GET /oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={app-id}
  &client_secret={app-secret}
  &fb_exchange_token={short-lived-token}
```

Returns a token good for ~60 days. Save it as `IG_ACCESS_TOKEN` in `.env`.

App ID and App Secret are on app dashboard → Settings → Basic.

### Step 8: Smoke test

```
GET /{IG_USER_ID}?fields=username,followers_count,media_count
```

Should return your handle and counts. If yes, setup is done.

## What to verify on Day 1 of coding

These are flagged because docs are sometimes ambiguous and the real behavior is what we have to code against. Verify before building anything that depends on them.

### V1: Pagination for `/media`

How many posts per page does `/{ig-user-id}/media` return by default? What's the max `limit`? How does the `after` cursor work?

Verify by: pulling all your posts and counting API calls. Save the raw paginated responses to `tests/fixtures/media_pagination.json`.

### V2: Comment text encoding

Do comment `text` fields come back as raw UTF-8 (with emoji as their Unicode codepoints), or HTML-escaped, or something else? How are mentions (`@user`) and hashtags rendered?

Verify by: pull comments from a post you know contains emoji and mentions. Save raw response to `tests/fixtures/comments_with_emoji.json`. Document the encoding behavior in `app/ig_client.py` docstring.

### V3: Replies endpoint behavior

Does `/{comment-id}/replies` return replies sorted by timestamp? By engagement? Does it paginate?

Verify by: pick a comment with > 5 replies. Pull all replies. Save to `tests/fixtures/replies.json`.

### V4: Deleted-comment behavior

If a user deletes a comment or their account, what does the API return for that comment ID on subsequent fetches? Does it 404, return null fields, or silently skip?

Verify by: ask a friend to comment on your post, fetch it, ask them to delete, fetch again. Document behavior. This affects how `ig_client.py` handles "missing on re-fetch."

### V5: Rate limit header format

The header is `X-Business-Use-Case-Usage` with a JSON-encoded value. Confirm format and parse correctly.

Verify by: make 5 consecutive calls, log the header value each time. Save examples to `tests/fixtures/rate_limit_headers.txt`.

### V6: Reply comment_count field

Do replies themselves report `comment_count`? (We assume no — replies don't have sub-replies — but verify.) This affects whether we recurse on replies or stop at depth 1.

Verify by: fetch a reply via `/{comment-id}?fields=id,text,replies` and inspect.

## Token expiry handling

Long-lived token = 60 days. Refresh endpoint:

```
GET /refresh_access_token
  ?grant_type=ig_refresh_token
  &access_token={current-token}
```

Add a CLI command `python -m app.cli refresh-token` that:
1. Calls the refresh endpoint.
2. Updates `.env` with the new token.
3. Prints new expiry date.

User runs this manually before the 60-day mark. Calendar reminder is the user's responsibility (Phase 1). Automatic refresh is Phase 2.

## Environment variables

`.env.example` content:

```
# Meta / Instagram Graph API
FB_APP_ID=your_app_id_here
FB_APP_SECRET=your_app_secret_here
IG_USER_ID=your_ig_business_account_id_here
IG_ACCESS_TOKEN=your_long_lived_token_here

# App config
DATABASE_PATH=./ig_pulse.db
LOG_LEVEL=INFO
TIMEZONE=Asia/Jakarta
```

## What we don't do with the API

- Don't call publishing endpoints. We don't post.
- Don't call insights endpoints in MVP (no follower analytics, no impressions chart). Comments only.
- Don't subscribe to webhooks. Pull model is enough.
- Don't fetch story comments (different endpoint, different permissions, often empty for non-business-tier accounts).
