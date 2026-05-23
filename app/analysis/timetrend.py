"""Time-trend analysis: group comments by calendar day in WIB (Asia/Jakarta)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.models import Comment

_WIB = ZoneInfo("Asia/Jakarta")


def daily_trend(
    comments: list[Comment],
    sentiment_by_id: dict[str, str] | None = None,
) -> list[dict]:
    """Group comments by WIB calendar day and return a sentiment split per day.

    Args:
        comments: List of Comment objects to analyse.
        sentiment_by_id: Optional mapping of comment_id -> sentiment label
            ("positive" | "negative" | "neutral" | "unanalyzed").
            Comments whose id is absent, or when the mapping is None, are
            counted as "unanalyzed".

    Returns:
        List of dicts sorted by date ascending, one per day that has comments:
        {"date": "YYYY-MM-DD", "total": int, "pos": int, "neg": int,
         "neu": int, "unanalyzed": int}
    """
    if sentiment_by_id is None:
        sentiment_by_id = {}

    # day_buckets maps "YYYY-MM-DD" -> {"pos", "neg", "neu", "unanalyzed"}
    day_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"pos": 0, "neg": 0, "neu": 0, "unanalyzed": 0}
    )

    for comment in comments:
        ts = comment.timestamp
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")

        # Treat naive timestamps as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        # Convert to WIB to determine the calendar day
        dt_wib = dt.astimezone(_WIB)
        day = dt_wib.strftime("%Y-%m-%d")

        label = sentiment_by_id.get(comment.id, "unanalyzed")
        bucket = day_buckets[day]
        if label == "positive":
            bucket["pos"] += 1
        elif label == "negative":
            bucket["neg"] += 1
        elif label == "neutral":
            bucket["neu"] += 1
        else:
            bucket["unanalyzed"] += 1

    result = []
    for day in sorted(day_buckets):
        b = day_buckets[day]
        total = b["pos"] + b["neg"] + b["neu"] + b["unanalyzed"]
        result.append(
            {
                "date": day,
                "total": total,
                "pos": b["pos"],
                "neg": b["neg"],
                "neu": b["neu"],
                "unanalyzed": b["unanalyzed"],
            }
        )

    return result
