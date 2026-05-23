"""Tests for app.analysis.tokenize — synthetic strings only, no real IG data."""


from app.analysis.tokenize import tokenize

# --- basic behaviour ---

def test_lowercasing():
    assert tokenize("Bagus BANGET Kak") == ["bagus", "banget", "kak"]


def test_empty_string():
    assert tokenize("") == []


def test_whitespace_only():
    assert tokenize("   \t\n  ") == []


# --- URL / mention / hashtag stripping ---

def test_url_http_stripped():
    result = tokenize("lihat https://example.com ini")
    assert "https" not in result
    assert "example" not in result
    assert "lihat" in result
    assert "ini" in result


def test_url_www_stripped():
    result = tokenize("kunjungi www.example.com sekarang")
    assert "www" not in result
    assert "kunjungi" in result


def test_mention_stripped():
    result = tokenize("@username keren bgt")
    assert "username" not in result
    assert "keren" in result
    assert "bgt" in result


def test_hashtag_stripped():
    result = tokenize("#viral #trending mantap")
    assert "viral" not in result
    assert "trending" not in result
    assert "mantap" in result


def test_hashtag_only_returns_empty():
    assert tokenize("#viral #trending") == []


# --- punctuation splitting ---

def test_punctuation_splits_words():
    result = tokenize("bagus, sekali!")
    assert result == ["bagus", "sekali"]


def test_hyphen_splits_words():
    # "produk-nya" → two tokens (hyphen is ASCII punct, treated as separator)
    result = tokenize("produk-nya bagus")
    assert "produk" in result
    assert "nya" in result


def test_ellipsis_splits_words():
    result = tokenize("hehe... mantap jiwa~")
    assert result == ["hehe", "mantap", "jiwa"]


# --- mixed Indonesian / English ---

def test_mixed_id_en():
    result = tokenize("this is bagus banget very good")
    assert result == ["this", "is", "bagus", "banget", "very", "good"]


def test_mixed_with_slang():
    result = tokenize("wkwk keren bgt sih")
    assert result == ["wkwk", "keren", "bgt", "sih"]


# --- emoji ---

def test_emoji_only_comment_not_silently_empty():
    """An emoji-only string must return non-empty (B3: no silent dropping)."""
    result = tokenize("😂")
    assert result == ["😂"], f"Expected ['😂'], got {result!r}"


def test_consecutive_emoji_become_separate_tokens():
    """Each emoji codepoint is its own token — '😂😂' → ['😂', '😂']."""
    result = tokenize("😂😂")
    assert result == ["😂", "😂"]


def test_emoji_kept_in_mixed_text():
    result = tokenize("bagus banget kak! 😍")
    assert "😍" in result
    assert "bagus" in result


def test_multiple_different_emoji():
    result = tokenize("wkwk 😂 🔥")
    assert "😂" in result
    assert "🔥" in result
    assert "wkwk" in result


def test_emoji_from_custom_stopwords_list():
    """Common emoji (❤, 🙏) are kept as tokens here; stopwords layer decides later."""
    result = tokenize("❤️ 🙏")
    # ❤ (U+2764) should be a token; variation selector U+FE0F is discarded
    assert "❤" in result
    assert "🙏" in result


# --- short tokens ---

def test_single_letter_token_kept():
    """Short tokens are NOT dropped at tokenization layer."""
    result = tokenize("a b c")
    assert result == ["a", "b", "c"]


def test_digits_kept():
    result = tokenize("produk 10 unit")
    assert "10" in result
