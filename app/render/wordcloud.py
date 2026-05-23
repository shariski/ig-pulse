"""Word cloud PNG renderer (export only).

Accepts pre-filtered word frequencies (already stopword-cleaned by the caller)
and returns a PIL Image — no disk I/O here; the export module handles that.
Styled to the editorial palette: cream surface, dark ink with occasional
burnt-orange accent words, to echo the on-screen cards.

Note: the default WordCloud font is not Lora (the lib needs a .ttf path for a
custom font; not bundled). Emoji are largely filtered upstream (architecture R6).
"""

from PIL import Image
from wordcloud import WordCloud as WordCloudLib

_BG = "#faf7f2"
_INK = "#1a1815"
_ACCENT = "#ff5b35"


def _color_func(word, font_size, position, orientation, random_state=None, **kwargs):
    """Dark ink for most words; ~1 in 5 gets the burnt-orange accent."""
    r = random_state.random() if random_state is not None else 0.5
    return _ACCENT if r < 0.2 else _INK


def render_wordcloud(
    freqs: list[tuple[str, int]],
    width: int = 1080,
    height: int = 1080,
    background_color: str = _BG,
) -> Image.Image:
    """Render word frequencies as a word cloud and return a PIL Image.

    Args:
        freqs: (word, count) tuples, sorted desc, stopword-filtered (top ~100).
        width/height: pixels (default 1080 square).
        background_color: surface colour (default cream).

    Returns:
        PIL Image, or a blank cream Image if freqs is empty.
    """
    if not freqs:
        return Image.new("RGB", (width, height), color=background_color)

    wc = WordCloudLib(
        width=width,
        height=height,
        background_color=background_color,
        color_func=_color_func,
        prefer_horizontal=0.9,
        margin=8,
    ).generate_from_frequencies(dict(freqs))
    return wc.to_image()
