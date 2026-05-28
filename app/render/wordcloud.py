"""Word cloud PNG renderer (export only).

Accepts pre-filtered word frequencies (already stopword-cleaned by the caller)
and returns a PIL Image — no disk I/O here; the export module handles that.
Styled to the editorial palette: cream surface, dark ink with occasional
burnt-orange accent words, to echo the on-screen cards.

Note: the default WordCloud font is not Lora (the lib needs a .ttf path for a
custom font; not bundled). Emoji are largely filtered upstream (architecture R6).
"""

from PIL import Image, ImageDraw, ImageFont
from wordcloud import WordCloud as WordCloudLib

_BG = "#faf7f2"
_INK = "#1a1815"
_ACCENT = "#ff5b35"
_FOOTER_H = 64  # extra height (px) appended for the caption strip


def _color_func(word, font_size, position, orientation, random_state=None, **kwargs):
    """Dark ink for most words; ~1 in 5 gets the burnt-orange accent."""
    r = random_state.random() if random_state is not None else 0.5
    return _ACCENT if r < 0.2 else _INK


def _draw_footer_caption(
    cloud_img: Image.Image,
    caption: str,
    background_color: str,
) -> Image.Image:
    """Extend the image with a caption strip along the bottom (B8 transparency)."""
    w, h = cloud_img.size
    out = Image.new("RGB", (w, h + _FOOTER_H), color=background_color)
    out.paste(cloud_img, (0, 0))
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=24)
    bbox = draw.textbbox((0, 0), caption, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (w - text_w) // 2
    y = h + (_FOOTER_H - text_h) // 2 - bbox[1]
    draw.text((x, y), caption, font=font, fill=_INK)
    return out


def render_wordcloud(
    freqs: list[tuple[str, int]],
    width: int = 1080,
    height: int = 1080,
    background_color: str = _BG,
    footer_caption: str | None = None,
) -> Image.Image:
    """Render word frequencies as a word cloud and return a PIL Image.

    Args:
        freqs: (word, count) tuples, sorted desc, stopword-filtered (top ~100).
        width/height: pixels (default 1080 square).
        background_color: surface colour (default cream).
        footer_caption: Optional caption drawn along the bottom of the image
            (B8: surface active filters/exclusions in the exported PNG).

    Returns:
        PIL Image, or a blank cream Image if freqs is empty.
    """
    if not freqs:
        base = Image.new("RGB", (width, height), color=background_color)
    else:
        wc = WordCloudLib(
            width=width,
            height=height,
            background_color=background_color,
            color_func=_color_func,
            prefer_horizontal=0.9,
            margin=8,
        ).generate_from_frequencies(dict(freqs))
        base = wc.to_image()

    if footer_caption:
        base = _draw_footer_caption(base, footer_caption, background_color)
    return base
