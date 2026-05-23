"""Tests for app.analysis.stopwords — no real IG data needed."""

from app.analysis.stopwords import get_stopwords


def test_returns_nonempty_set():
    sw = get_stopwords()
    assert isinstance(sw, set)
    assert len(sw) > 0


def test_cached_across_calls():
    """get_stopwords() must return the same object on repeated calls (cached)."""
    sw1 = get_stopwords()
    sw2 = get_stopwords()
    assert sw1 is sw2


def test_known_indonesian_word_present():
    """'yang' is in Sastrawi stopwords."""
    sw = get_stopwords()
    assert "yang" in sw


def test_known_indonesian_words_present():
    """A sample of Sastrawi Indonesian stopwords must all be present."""
    sw = get_stopwords()
    for word in ["untuk", "pada", "ke", "namun", "antara"]:
        assert word in sw, f"Expected Sastrawi word {word!r} in stopwords"


def test_known_english_word_present():
    """'the' is in NLTK English stopwords (or at minimum the set is ≥ Sastrawi size)."""
    sw = get_stopwords()
    # If NLTK download succeeded, 'the' must be present.
    # If NLTK failed (network-less CI), we at least have Indonesian words — skip EN assertion.
    try:
        from nltk.corpus import stopwords as nltk_sw
        nltk_sw.words("english")  # raises LookupError if not downloaded
        assert "the" in sw
        assert "is" in sw
    except LookupError:
        # NLTK data unavailable — graceful fallback is acceptable, skip EN assertion
        pass


def test_custom_chat_noise_present():
    """'wkwk' must be in the custom stopword list."""
    sw = get_stopwords()
    assert "wkwk" in sw


def test_custom_tokens_present():
    """A sample of custom tokens must all be present."""
    sw = get_stopwords()
    custom_expected = ["wkwk", "haha", "hehe", "bgt", "sih", "nih", "dong", "aja"]
    for token in custom_expected:
        assert token in sw, f"Expected custom token {token!r} in stopwords"


def test_all_tokens_are_lowercase():
    """Every token in the set must be lowercase (matching tokenize() output)."""
    sw = get_stopwords()
    for token in sw:
        assert token == token.lower(), f"Non-lowercase token found: {token!r}"


def test_custom_url_artefacts_present():
    """URL artefacts like 'http', 'https', 'www' should be in custom list."""
    sw = get_stopwords()
    for token in ["http", "https", "www"]:
        assert token in sw, f"Expected URL artefact {token!r} in stopwords"
