"""Tests for sentiment's pure helpers (no torch/transformers needed)."""

from __future__ import annotations

import pytest

from app.analysis.sentiment import _canonical, is_analyzable


@pytest.mark.parametrize(
    "text,expected",
    [
        ("mantap banget", True),
        ("ok", False),  # < 3 chars
        ("", False),
        ("   ", False),
        ("🔥🔥🔥", False),  # emoji-only, no alphanumeric
        ("😂", False),
        ("wkwk", True),  # 4 alphanumeric chars (stopword-ness is wordfreq's job, not here)
        ("a1b", True),
    ],
)
def test_is_analyzable(text, expected):
    assert is_analyzable(text) is expected


def test_canonical_tabularisai_5class():
    m = "tabularisai/multilingual-sentiment-analysis"
    assert _canonical(m, "Very Positive") == "positive"
    assert _canonical(m, "Positive") == "positive"
    assert _canonical(m, "Neutral") == "neutral"
    assert _canonical(m, "Negative") == "negative"
    assert _canonical(m, "Very Negative") == "negative"


def test_canonical_cardiff_3class_and_label_ids():
    m = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    assert _canonical(m, "positive") == "positive"
    assert _canonical(m, "LABEL_2") == "positive"
    assert _canonical(m, "LABEL_0") == "negative"


def test_canonical_unknown_defaults_neutral():
    assert _canonical("some/unknown-model", "whatever") == "neutral"
