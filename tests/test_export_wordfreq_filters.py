"""Verify /export/wordfreq passes filter params through (B8: export must
reflect what the user is viewing)."""

from unittest.mock import patch


def test_export_wordfreq_passes_exclude_to_word_frequencies(authed_client, seeded_comments):
    with patch("app.routes.export.wordfreq.word_frequencies") as spy:
        spy.return_value = [("nasi", 3)]  # short-circuit; we only care about input
        r = authed_client.get(
            "/export/wordfreq/download?exclude=iya&exclude=mantap&sentiment=all"
        )
        # Status may be 200 (success) or 503 (kaleido/wordcloud missing on test env).
        # Either way, wordfreq.word_frequencies should have been invoked with the exclude set.
        assert spy.called
        called_kwargs = spy.call_args.kwargs
        called_args = spy.call_args.args
        ex = called_kwargs.get("exclude_words")
        if ex is None and len(called_args) > 2:
            ex = called_args[2]
        assert ex is not None and {"iya", "mantap"}.issubset(ex)


def test_export_wordfreq_sentiment_filter_narrows_comment_set(
    authed_client, seeded_with_sentiment
):
    """When sentiment=negative is passed, the export only sees negative comments."""
    with patch("app.routes.export.wordfreq.word_frequencies") as spy:
        spy.return_value = []  # short-circuit; we only care about input
        r = authed_client.get("/export/wordfreq/download?sentiment=negative")
        assert spy.called
        comments_passed = spy.call_args.args[0]
        # All comments passed should contain "negativeword" (the fixture marker)
        # because seeded_with_sentiment seeds only that word into negative-labeled comments.
        assert all("negativeword" in c.text for c in comments_passed), (
            f"Got: {[c.text for c in comments_passed]}"
        )
