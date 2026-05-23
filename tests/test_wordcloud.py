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
