"""Tests for the server-side SVG chart generators (theme-reactive, pure)."""

from __future__ import annotations

from app.render.svg import sentiment_donut_svg, timetrend_area_svg


def test_donut_empty_returns_blank():
    assert sentiment_donut_svg({}) == ""
    assert sentiment_donut_svg({"positive": 0, "neutral": 0}) == ""


def test_donut_one_circle_per_nonzero_segment():
    s = sentiment_donut_svg({"positive": 30, "neutral": 40, "negative": 30})
    assert s.startswith("<svg")
    assert s.count("<circle") == 3
    assert "var(--pos)" in s and "var(--neg)" in s and "var(--neu)" in s


def test_donut_skips_zero_segments():
    s = sentiment_donut_svg({"positive": 10, "neutral": 0, "negative": 0})
    assert s.count("<circle") == 1


def test_area_empty_returns_blank():
    assert timetrend_area_svg([]) == ""


def test_area_has_stacked_polygons_and_total_line():
    rows = [
        {"date": "2025-01-01", "total": 3, "pos": 1, "neg": 1, "neu": 1, "unanalyzed": 0},
        {"date": "2025-01-02", "total": 5, "pos": 3, "neg": 1, "neu": 1, "unanalyzed": 0},
        {"date": "2025-01-03", "total": 2, "pos": 0, "neg": 1, "neu": 1, "unanalyzed": 0},
    ]
    s = timetrend_area_svg(rows)
    assert s.startswith("<svg")
    assert "<polygon" in s
    assert "<polyline" in s
