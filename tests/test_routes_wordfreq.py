"""Integration tests for the wordfreq HTMX fragment route.

Verifies the route-layer wiring of the new ``sentiment`` and ``exclude`` query
parameters added in Task 6 of the wordfreq enhancement plan. The fixtures
``authed_client``, ``seeded_comments`` and ``seeded_with_sentiment`` live in
``tests/conftest.py`` and mirror the inline setup used by ``test_routes.py``.
"""

from __future__ import annotations

import pytest


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


def test_save_stopword_inserts_row_and_returns_fragment(authed_client, seeded_comments):
    r = authed_client.post("/analysis/wordfreq/stopwords?word=iya")
    assert r.status_code == 200
    assert "cloud-words" in r.text or "frag_wordfreq" in r.text  # refreshed fragment

    # Verify it landed in DB
    from app.db import connect
    conn = connect(authed_client.db_path)
    try:
        rows = list(conn.execute("SELECT word FROM user_stopwords"))
    finally:
        conn.close()
    assert ("iya",) in [tuple(r) for r in rows]


def test_save_stopword_rejects_invalid_word(authed_client):
    r = authed_client.post("/analysis/wordfreq/stopwords?word=<script>")
    assert r.status_code == 400


def test_remove_saved_stopword(authed_client, seeded_comments):
    authed_client.post("/analysis/wordfreq/stopwords?word=iya")
    r = authed_client.delete("/analysis/wordfreq/stopwords?word=iya")
    assert r.status_code == 200

    from app.db import connect
    conn = connect(authed_client.db_path)
    try:
        rows = list(conn.execute("SELECT word FROM user_stopwords"))
    finally:
        conn.close()
    assert rows == []


@pytest.mark.skip(reason="template added in Task 12")
def test_sample_modal_returns_html(authed_client, seeded_comments):
    r = authed_client.get("/analysis/wordfreq/sample?word=nasi&n=5")
    assert r.status_code == 200
    # Renders the partial (we'll create it in Task 12 — for now just assert HTML)
    assert "modal" in r.text.lower() or "sampel" in r.text.lower()


@pytest.mark.skip(reason="template added in Task 12")
def test_sample_modal_filters_by_sentiment(authed_client, seeded_with_sentiment):
    # 'negativeword' appears ONLY in negative-bucket comments per fixture; the
    # filter must keep the route 200 (content verification deferred to Task 12).
    r = authed_client.get(
        "/analysis/wordfreq/sample?word=negativeword&sentiment=negative&n=10"
    )
    assert r.status_code == 200


def test_sample_modal_rejects_invalid_word(authed_client):
    r = authed_client.get("/analysis/wordfreq/sample?word=<script>")
    assert r.status_code == 400


@pytest.mark.skip(reason="template added in Task 12")
def test_sample_modal_empty_for_no_match(authed_client, seeded_comments):
    r = authed_client.get("/analysis/wordfreq/sample?word=doesnotexist")
    assert r.status_code == 200
    assert "tidak ada komentar" in r.text.lower()


@pytest.mark.skip(reason="template added in Task 13")
def test_filtered_panel_lists_saved_stopwords(authed_client):
    authed_client.post("/analysis/wordfreq/stopwords?word=iya")
    r = authed_client.get("/analysis/wordfreq/filtered")
    assert r.status_code == 200
    assert "iya" in r.text


def test_filtered_panel_endpoint_exists(authed_client):
    """The route must be registered. Until Task 13 lands the template, the
    handler reaches Jinja and raises TemplateNotFound (not a 404). We accept
    either a non-404 response OR a TemplateNotFound — both prove the routing
    is wired."""
    from jinja2 import TemplateNotFound

    try:
        r = authed_client.get("/analysis/wordfreq/filtered")
    except TemplateNotFound:
        return  # routing worked; only the template is missing (Task 13)
    assert r.status_code != 404
