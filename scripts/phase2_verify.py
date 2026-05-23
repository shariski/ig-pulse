"""Phase 2 — verify Graph API behavior against the REAL account and save fixtures.

Read-only. Makes a handful of real calls, saves raw JSON to tests/fixtures/, and
prints findings for the V1–V6 questions in docs/api-integration.md. Run once after
Phase 0:

    uv run python -m scripts.phase2_verify

Fixtures are gitignored (they hold real audience usernames/text — risks.md R7).
"""

from __future__ import annotations

import asyncio
import json

from app.config import settings
from app.ig_client import IGClient, parse_business_use_case_usage

FIX = settings.fixtures_dir


def _save(name: str, obj: object) -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    p = FIX / name
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  saved {p}  ({p.stat().st_size} B)")


async def _try(label: str, coro):
    """Run a verification step, surfacing errors instead of aborting the run."""
    try:
        return await coro
    except Exception as e:  # noqa: BLE001 - verification wants to SEE failures
        print(f"  !! {label} FAILED: {type(e).__name__}: {e}")
        return None


async def main() -> None:
    settings.require_ig_credentials()
    async with IGClient() as ig:
        uid = settings.ig_user_id

        # --- profile + V5 (rate-limit header) ---
        print("== profile / V5 rate-limit header ==")
        resp = await _try(
            "profile", ig._get(uid, {"fields": "username,followers_count,media_count"})
        )
        if resp is not None:
            prof = resp.json()
            print(
                f"  @{prof.get('username')}  followers={prof.get('followers_count')}  "
                f"media={prof.get('media_count')}"
            )
            rl = resp.headers.get("X-Business-Use-Case-Usage")
            (FIX / "rate_limit_headers.txt").write_text(str(rl), encoding="utf-8")
            print(f"  V5 header: {rl!r}  -> max usage% = {parse_business_use_case_usage(rl)}")

        # --- V1: media pagination ---
        print("== V1 media pagination ==")
        media_fields = (
            "id,caption,media_type,permalink,timestamp,like_count,comments_count,thumbnail_url"
        )
        resp = await _try("media", ig._get(f"{uid}/media", {"fields": media_fields, "limit": 25}))
        items: list[dict] = []
        if resp is not None:
            media = resp.json()
            _save("media_list.json", media)
            items = media.get("data", [])
            after = media.get("paging", {}).get("cursors", {}).get("after")
            print(f"  {len(items)} posts in page 1; next cursor: {'yes' if after else 'no'}")

        # --- V2: comments (encoding) on the most-recent post that has comments ---
        print("== V2 comments / encoding ==")
        with_comments = [m for m in items if (m.get("comments_count") or 0) > 0]
        print(f"  posts with comments in page 1: {len(with_comments)}")
        comments: list[dict] = []
        target_mid = None
        if with_comments:
            target_mid = with_comments[0]["id"]
            cfields = "id,text,username,timestamp,like_count"
            resp = await _try(
                "comments", ig._get(f"{target_mid}/comments", {"fields": cfields, "limit": 50})
            )
            if resp is not None:
                cmt = resp.json()
                _save("comments_with_emoji.json", cmt)
                comments = cmt.get("data", [])
                print(f"  {len(comments)} comments on post {target_mid}")
                for c in comments[:5]:
                    print(f"    @{c.get('username')}: {c.get('text')!r}")

        # --- V3 + V6: replies ---
        print("== V3/V6 replies ==")
        rfields = "id,text,username,timestamp,like_count"
        for c in comments[:8]:
            cid = c["id"]
            resp = await _try(
                f"replies({cid})",
                ig._get(f"{cid}/replies", {"fields": rfields, "limit": 50}),
            )
            if resp is not None:
                data = resp.json().get("data", [])
                if data:
                    _save("replies.json", resp.json())
                    print(f"  comment {cid} has {len(data)} replies (saved)")
                    break
        else:
            print("  no replies found on the sampled comments")

        print(f"\nTotal real API calls this run: {ig.api_calls_made}")


if __name__ == "__main__":
    asyncio.run(main())
