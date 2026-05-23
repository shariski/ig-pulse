"""Unit tests for app.analysis.timetrend.daily_trend."""

from __future__ import annotations

from app.analysis.timetrend import daily_trend
from app.models import Comment


def _make_comment(id: str, timestamp: str) -> Comment:
    return Comment(
        id=id,
        post_id="post1",
        text="test",
        timestamp=timestamp,
        fetched_at="2025-01-01T00:00:00+0000",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestDailyTrendBasic:
    def test_empty_list(self):
        assert daily_trend([]) == []

    def test_single_comment_no_sentiment(self):
        c = _make_comment("c1", "2025-03-14T09:20:00+0000")
        rows = daily_trend([c])
        assert len(rows) == 1
        row = rows[0]
        assert row["date"] == "2025-03-14"  # UTC 09:20 → WIB 16:20, still same calendar day
        assert row["total"] == 1
        assert row["unanalyzed"] == 1
        assert row["pos"] == row["neg"] == row["neu"] == 0

    def test_buckets_sum_to_total(self):
        comments = [
            _make_comment("c1", "2025-03-14T09:00:00+0000"),
            _make_comment("c2", "2025-03-14T10:00:00+0000"),
            _make_comment("c3", "2025-03-14T11:00:00+0000"),
        ]
        sentiment = {"c1": "positive", "c2": "negative", "c3": "neutral"}
        rows = daily_trend(comments, sentiment)
        assert len(rows) == 1
        row = rows[0]
        assert row["total"] == 3
        assert row["pos"] + row["neg"] + row["neu"] + row["unanalyzed"] == row["total"]


class TestWIBDayBucketing:
    def test_utc_midnight_crossing_into_next_wib_day(self):
        """2025-03-14T20:00:00+0000 is 2025-03-15T03:00:00+07:00 in WIB."""
        c = _make_comment("c1", "2025-03-14T20:00:00+0000")
        rows = daily_trend([c])
        assert len(rows) == 1
        assert rows[0]["date"] == "2025-03-15"

    def test_utc_timestamp_that_stays_same_wib_day(self):
        """2025-03-14T09:00:00+0000 is 2025-03-14T16:00:00+07:00 — same day."""
        c = _make_comment("c1", "2025-03-14T09:00:00+0000")
        rows = daily_trend([c])
        assert rows[0]["date"] == "2025-03-14"

    def test_wib_boundary_just_before_midnight(self):
        """2025-03-14T16:59:59+0000 = 2025-03-14T23:59:59 WIB — still 2025-03-14."""
        c = _make_comment("c1", "2025-03-14T16:59:59+0000")
        rows = daily_trend([c])
        assert rows[0]["date"] == "2025-03-14"

    def test_wib_boundary_at_midnight(self):
        """2025-03-14T17:00:00+0000 = 2025-03-15T00:00:00 WIB — becomes 2025-03-15."""
        c = _make_comment("c1", "2025-03-14T17:00:00+0000")
        rows = daily_trend([c])
        assert rows[0]["date"] == "2025-03-15"

    def test_non_utc_source_offset_converted_correctly(self):
        """A comment with +07:00 offset stays in the same day it was created."""
        # 2025-03-14T10:00:00+07:00 = 2025-03-14T03:00:00+00:00 = WIB 2025-03-14T10:00:00
        c = _make_comment("c1", "2025-03-14T10:00:00+07:00")
        rows = daily_trend([c])
        assert rows[0]["date"] == "2025-03-14"

    def test_naive_timestamp_treated_as_utc(self):
        """A timestamp without timezone info is assumed UTC."""
        c = _make_comment("c1", "2025-03-14T20:00:00")
        rows = daily_trend([c])
        # UTC 20:00 → WIB 2025-03-15T03:00
        assert rows[0]["date"] == "2025-03-15"


class TestSentimentSplit:
    def test_all_positive(self):
        comments = [_make_comment(f"c{i}", "2025-03-14T09:00:00+0000") for i in range(3)]
        sentiment = {c.id: "positive" for c in comments}
        row = daily_trend(comments, sentiment)[0]
        assert row["pos"] == 3
        assert row["neg"] == row["neu"] == row["unanalyzed"] == 0

    def test_mixed_sentiments_on_same_day(self):
        comments = [
            _make_comment("c1", "2025-03-14T09:00:00+0000"),
            _make_comment("c2", "2025-03-14T10:00:00+0000"),
            _make_comment("c3", "2025-03-14T11:00:00+0000"),
            _make_comment("c4", "2025-03-14T12:00:00+0000"),
        ]
        sentiment = {"c1": "positive", "c2": "negative", "c3": "neutral"}
        # c4 has no entry in sentiment_by_id → unanalyzed
        row = daily_trend(comments, sentiment)[0]
        assert row["pos"] == 1
        assert row["neg"] == 1
        assert row["neu"] == 1
        assert row["unanalyzed"] == 1
        assert row["total"] == 4

    def test_unknown_label_counted_as_unanalyzed(self):
        c = _make_comment("c1", "2025-03-14T09:00:00+0000")
        row = daily_trend([c], {"c1": "some_unknown_label"})[0]
        assert row["unanalyzed"] == 1

    def test_sentiment_none_all_unanalyzed(self):
        comments = [_make_comment(f"c{i}", "2025-03-14T09:00:00+0000") for i in range(5)]
        row = daily_trend(comments, None)[0]
        assert row["unanalyzed"] == 5
        assert row["pos"] == row["neg"] == row["neu"] == 0

    def test_missing_id_in_sentiment_dict_is_unanalyzed(self):
        c = _make_comment("c1", "2025-03-14T09:00:00+0000")
        # sentiment_by_id is provided but doesn't contain c1
        row = daily_trend([c], {"other_id": "positive"})[0]
        assert row["unanalyzed"] == 1


class TestAscendingOrder:
    def test_multiple_days_sorted_ascending(self):
        comments = [
            _make_comment("c1", "2025-03-16T09:00:00+0000"),
            _make_comment("c2", "2025-03-14T09:00:00+0000"),
            _make_comment("c3", "2025-03-15T09:00:00+0000"),
        ]
        rows = daily_trend(comments)
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates)
        assert dates == ["2025-03-14", "2025-03-15", "2025-03-16"]

    def test_each_day_gets_own_bucket(self):
        comments = [
            _make_comment("c1", "2025-03-14T09:00:00+0000"),
            _make_comment("c2", "2025-03-14T15:00:00+0000"),  # still 2025-03-14 WIB
            _make_comment("c3", "2025-03-15T09:00:00+0000"),
        ]
        rows = daily_trend(comments)
        assert len(rows) == 2
        assert rows[0]["total"] == 2
        assert rows[1]["total"] == 1
