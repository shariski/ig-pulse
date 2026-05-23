"""Tests for app/render/export.py — including kaleido smoke test (R9)."""

import io

import plotly.graph_objects as go
import pytest
from PIL import Image

from app.render.export import figure_to_png, image_to_png


def _make_figure() -> go.Figure:
    return go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))


def _make_pil_image(w: int = 400, h: int = 300) -> Image.Image:
    return Image.new("RGB", (w, h), color=(100, 150, 200))


# ---------------------------------------------------------------------------
# kaleido smoke test (R9)
# ---------------------------------------------------------------------------


def test_kaleido_smoke():
    """kaleido must produce valid PNG bytes on this machine (R9)."""
    fig = _make_figure()
    result = figure_to_png(fig, "square")
    assert isinstance(result, bytes), "figure_to_png must return bytes"
    assert len(result) > 0, "PNG output must be non-empty"
    assert result[:4] == b"\x89PNG", "Output must start with PNG magic bytes"


# ---------------------------------------------------------------------------
# figure_to_png dimensions
# ---------------------------------------------------------------------------


def test_figure_to_png_square_dimensions():
    result = figure_to_png(_make_figure(), "square")
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080 * 2, 1080 * 2), "scale=2 → 2160×2160 raw pixels"


def test_figure_to_png_portrait_dimensions():
    result = figure_to_png(_make_figure(), "portrait")
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080 * 2, 1350 * 2)


# ---------------------------------------------------------------------------
# image_to_png
# ---------------------------------------------------------------------------


def test_image_to_png_returns_png_bytes():
    result = image_to_png(_make_pil_image(), "square")
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


def test_image_to_png_square_dimensions():
    result = image_to_png(_make_pil_image(), "square")
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080, 1080)


def test_image_to_png_portrait_dimensions():
    result = image_to_png(_make_pil_image(), "portrait")
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080, 1350)


# ---------------------------------------------------------------------------
# watermark path
# ---------------------------------------------------------------------------


def test_figure_to_png_with_watermark():
    result = figure_to_png(_make_figure(), "square", watermark="@handle")
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


def test_image_to_png_with_watermark():
    result = image_to_png(_make_pil_image(), "square", watermark="@myhandle")
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# unknown preset raises ValueError
# ---------------------------------------------------------------------------


def test_figure_to_png_unknown_preset_raises():
    with pytest.raises(ValueError, match="Unknown preset"):
        figure_to_png(_make_figure(), "widescreen")


def test_image_to_png_unknown_preset_raises():
    with pytest.raises(ValueError, match="Unknown preset"):
        image_to_png(_make_pil_image(), "4k")
