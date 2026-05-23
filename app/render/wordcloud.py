"""
Word cloud PNG renderer.

Accepts pre-filtered word frequencies (already stopword-cleaned by the caller)
and returns a PIL Image — no disk I/O here; the export module handles that.

Note: the default WordCloud font may not render emoji glyphs. Emoji are
largely filtered upstream by the stopword pipeline (see architecture R6), so
this is acceptable for MVP.
"""

from PIL import Image
from wordcloud import WordCloud as WordCloudLib


def render_wordcloud(
    freqs: list[tuple[str, int]],
    width: int = 1080,
    height: int = 1080,
    background_color: str = "white",
) -> Image.Image:
    """
    Render word frequencies as a word cloud and return a PIL Image.

    Args:
        freqs: List of (word, count) tuples, sorted descending, stopword-filtered.
               Top 100 is the expected input from the word frequency analysis.
        width: Image width in pixels (default 1080 for IG square).
        height: Image height in pixels (default 1080 for IG square).
        background_color: Background colour string passed to WordCloud.

    Returns:
        PIL Image of the word cloud, or a blank white Image if freqs is empty.
    """
    if not freqs:
        return Image.new("RGB", (width, height), color="white")

    freq_dict = dict(freqs)
    wc = WordCloudLib(
        width=width,
        height=height,
        background_color=background_color,
    ).generate_from_frequencies(freq_dict)
    return wc.to_image()
