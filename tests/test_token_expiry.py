"""Tests for token-expiry tracking: cli._expiry_iso + dashboard._days_left (R4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.cli import _expiry_iso
from app.routes.dashboard import _days_left


def test_expiry_iso_none_or_zero():
    assert _expiry_iso(None) is None
    assert _expiry_iso(0) is None


def test_expiry_iso_then_days_left_roundtrip():
    iso = _expiry_iso(60 * 86400)  # 60 days from now
    assert iso is not None
    assert _days_left(iso) in (59, 60)  # allow for timing/rounding


def test_days_left_none_and_unparseable():
    assert _days_left(None) is None
    assert _days_left("") is None
    assert _days_left("not-a-date") is None


def test_days_left_naive_timestamp_treated_as_utc():
    naive = (datetime.now(UTC) + timedelta(days=10)).replace(tzinfo=None).isoformat()
    assert _days_left(naive) in (9, 10)
