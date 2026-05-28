"""Integration tests for the wordfreq HTMX fragment route.

Verifies the route-layer wiring of the new ``sentiment`` and ``exclude`` query
parameters added in Task 6 of the wordfreq enhancement plan. The fixtures
``authed_client``, ``seeded_comments`` and ``seeded_with_sentiment`` live in
``tests/conftest.py`` and mirror the inline setup used by ``test_routes.py``.
"""

from __future__ import annotations


def test_wordfreq_fragment_renders_without_filters(authed_client, seeded_comments):
    r = authed_client.get("/analysis/wordfreq")
    assert r.status_code == 200
    # Either the fragment heading copy or the cloud markup must be present.
    assert "frekuensi" in r.text.lower() or "cloud-words" in r.text


def test_wordfreq_fragment_excludes_listed_word(authed_client, seeded_comments):
    """``?exclude=nasi`` must drop the 'nasi' token from the rendered cloud."""
    # Baseline: without the filter, 'nasi' appears in the cloud.
    baseline = authed_client.get("/analysis/wordfreq")
    assert baseline.status_code == 200
    assert ">nasi<" in baseline.text  # sanity-check the seed actually produced it

    r = authed_client.get("/analysis/wordfreq?exclude=nasi")
    assert r.status_code == 200
    # No cloud-word span with text 'nasi' should remain.
    assert ">nasi<" not in r.text


def test_wordfreq_fragment_sentiment_filter_negative(
    authed_client, seeded_with_sentiment
):
    """When ``sentiment=negative``, words that ONLY appear in positive comments
    must be absent from the cloud."""
    r = authed_client.get("/analysis/wordfreq?sentiment=negative")
    assert r.status_code == 200
    assert "positiveword" not in r.text
    # Sanity: a word from the negative bucket SHOULD appear.
    assert "negativeword" in r.text


def test_wordfreq_fragment_multiple_exclude_params(authed_client, seeded_comments):
    """Repeated ``?exclude=`` query params combine: each listed word is dropped."""
    r = authed_client.get("/analysis/wordfreq?exclude=nasi&exclude=mantap")
    assert r.status_code == 200
    assert ">nasi<" not in r.text
    assert ">mantap<" not in r.text


def test_wordfreq_fragment_unknown_sentiment_is_treated_as_all(
    authed_client, seeded_with_sentiment
):
    """Garbage ``sentiment=`` values must not 4xx — they're silently coerced to
    'all' so a stale URL doesn't break the HTMX swap."""
    r = authed_client.get("/analysis/wordfreq?sentiment=zzz")
    assert r.status_code == 200
    # Words from all buckets remain visible.
    assert "positiveword" in r.text
    assert "negativeword" in r.text


def test_wordfreq_fragment_sentiment_filter_no_results_returns_empty_state(
    authed_client, seeded_comments
):
    """seeded_comments has NO sentiment analyses; filtering to 'positive' yields
    zero comments and a graceful empty-state body (not a 500)."""
    r = authed_client.get("/analysis/wordfreq?sentiment=positive")
    assert r.status_code == 200
    assert "state-empty" in r.text
