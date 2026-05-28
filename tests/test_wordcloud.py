from PIL import Image

from app.render.wordcloud import render_wordcloud


def test_returns_image_of_correct_size():
    freqs = [("nasi", 5), ("goreng", 3), ("enak", 2)]
    img = render_wordcloud(freqs, width=800, height=600)
    assert isinstance(img, Image.Image)
    assert img.size == (800, 600)


def test_default_size_is_1080x1080():
    freqs = [("nasi", 5), ("goreng", 3), ("enak", 2)]
    img = render_wordcloud(freqs)
    assert img.size == (1080, 1080)


def test_empty_freqs_returns_blank_image_without_raising():
    img = render_wordcloud([], width=400, height=400)
    assert isinstance(img, Image.Image)
    assert img.size == (400, 400)


def test_footer_caption_extends_image_height():
    """When footer_caption is provided, the returned image is taller than the
    cloud (the caption strip is appended). Verifies the renderer accepts the
    new kwarg and returns a PIL Image — visual correctness checked manually."""
    freqs = [("nasi", 5), ("goreng", 3), ("enak", 2)]
    base = render_wordcloud(freqs, width=400, height=400)
    with_caption = render_wordcloud(
        freqs, width=400, height=400, footer_caption="Sentimen: Negatif"
    )
    assert isinstance(with_caption, Image.Image)
    assert with_caption.size[0] == base.size[0]
    assert with_caption.size[1] > base.size[1]


def test_footer_caption_none_leaves_size_unchanged():
    freqs = [("nasi", 5), ("goreng", 3)]
    img = render_wordcloud(freqs, width=400, height=400, footer_caption=None)
    assert img.size == (400, 400)
