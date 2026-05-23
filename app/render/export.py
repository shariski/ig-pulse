"""PNG export for the 'share back to audience' flow (B8)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

PRESETS: dict[str, tuple[int, int]] = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "story": (1080, 1920),
}


def _validate_preset(preset: str) -> tuple[int, int]:
    if preset not in PRESETS:
        raise ValueError(
            f"Unknown preset {preset!r}. Valid presets: {list(PRESETS.keys())}"
        )
    return PRESETS[preset]


def _apply_watermark(img: Image.Image, handle: str) -> Image.Image:
    """Overlay creator handle text at bottom-right, white ~60% opacity with drop shadow."""
    img = img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)

    font = ImageFont.load_default(size=36)

    # Measure text
    bbox = draw.textbbox((0, 0), handle, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = 24
    x = img.width - text_w - margin
    y = img.height - text_h - margin

    # Drop shadow (black, 40% opacity, offset 2px)
    shadow_color = (0, 0, 0, 102)
    draw.text((x + 2, y + 2), handle, font=font, fill=shadow_color)

    # White text at ~60% opacity
    text_color = (255, 255, 255, 153)
    draw.text((x, y), handle, font=font, fill=text_color)

    return img.convert("RGB")


def figure_to_png(fig, preset: str = "square", watermark: str | None = None) -> bytes:
    """Render a Plotly Figure to PNG bytes at the given preset size.

    Args:
        fig: A plotly.graph_objects.Figure.
        preset: One of 'square', 'portrait', 'story'.
        watermark: Optional creator handle text overlaid bottom-right.

    Returns:
        Raw PNG bytes.
    """
    w, h = _validate_preset(preset)
    png_bytes: bytes = fig.to_image(format="png", width=w, height=h, scale=2)

    if watermark:
        img = Image.open(io.BytesIO(png_bytes))
        img = _apply_watermark(img, watermark)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    return png_bytes


def image_to_png(img: Image.Image, preset: str = "square", watermark: str | None = None) -> bytes:
    """Resize/letterbox a PIL Image to the preset dimensions and return PNG bytes.

    Args:
        img: A PIL Image (e.g. a word cloud PNG).
        preset: One of 'square', 'portrait', 'story'.
        watermark: Optional creator handle text overlaid bottom-right.

    Returns:
        Raw PNG bytes.
    """
    w, h = _validate_preset(preset)

    # Letterbox: fit inside W×H preserving aspect ratio, pad with black
    img_rgb = img.convert("RGB")
    img_rgb.thumbnail((w, h), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    offset_x = (w - img_rgb.width) // 2
    offset_y = (h - img_rgb.height) // 2
    canvas.paste(img_rgb, (offset_x, offset_y))

    if watermark:
        canvas = _apply_watermark(canvas, watermark)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()
