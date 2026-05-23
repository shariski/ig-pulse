"""Tests for app/render/charts.py — synthetic inputs only."""

import plotly.graph_objects as go

from app.render.charts import (
    fig_to_html,
    phrase_bar,
    sentiment_pie,
    timetrend_line,
    word_freq_bar,
)

# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

DIST = {"positive": 88, "neutral": 116, "negative": 85, "unanalyzed": 2}

ROWS = [
    {"date": "2024-01-01", "total": 30, "pos": 10, "neg": 5, "neu": 14, "unanalyzed": 1},
    {"date": "2024-01-02", "total": 45, "pos": 20, "neg": 10, "neu": 14, "unanalyzed": 1},
    {"date": "2024-01-03", "total": 22, "pos": 8, "neg": 6, "neu": 7, "unanalyzed": 1},
]

PHRASES = [("bagus sekali", 15), ("tidak suka", 10), ("sangat keren", 7)]

WORDS = [("bagus", 50), ("keren", 40), ("suka", 35), ("mantap", 30),
         ("hebat", 25), ("buruk", 20), ("jelek", 15), ("menarik", 12),
         ("biasa", 10), ("luar", 9), ("dalam", 8), ("oke", 7),
         ("wow", 6), ("hmm", 5), ("lucu", 5), ("sedih", 4),
         ("senang", 3), ("marah", 3), ("bingung", 2), ("takut", 2),
         ("extra_word", 1)]  # 21 items; top_n=20 should exclude the last


# ---------------------------------------------------------------------------
# sentiment_pie
# ---------------------------------------------------------------------------

class TestSentimentPie:
    def test_returns_figure(self):
        assert isinstance(sentiment_pie(DIST), go.Figure)

    def test_has_one_pie_trace(self):
        fig = sentiment_pie(DIST)
        pie_traces = [t for t in fig.data if isinstance(t, go.Pie)]
        assert len(pie_traces) == 1

    def test_correct_number_of_slices(self):
        fig = sentiment_pie(DIST)
        # All 4 keys have non-zero values
        assert len(fig.data[0].labels) == 4

    def test_values_match_input(self):
        fig = sentiment_pie(DIST)
        total = sum(fig.data[0].values)
        assert total == sum(DIST.values())

    def test_indonesian_labels(self):
        fig = sentiment_pie(DIST)
        labels = list(fig.data[0].labels)
        assert "Positif" in labels
        assert "Negatif" in labels
        assert "Netral" in labels
        assert "Belum dianalisis" in labels

    def test_zero_values_excluded(self):
        dist = {"positive": 5, "negative": 0, "neutral": 3, "unanalyzed": 0}
        fig = sentiment_pie(dist)
        assert len(fig.data[0].labels) == 2

    def test_empty_input_no_crash(self):
        fig = sentiment_pie({})
        assert isinstance(fig, go.Figure)
        # No data traces (pie has no values)
        assert len(fig.data) == 0

    def test_all_zero_no_crash(self):
        fig = sentiment_pie({"positive": 0, "negative": 0})
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0

    def test_empty_has_annotation(self):
        fig = sentiment_pie({})
        assert any("Belum ada data" in (a.text or "") for a in fig.layout.annotations)


# ---------------------------------------------------------------------------
# timetrend_line
# ---------------------------------------------------------------------------

class TestTimetrendLine:
    def test_returns_figure(self):
        assert isinstance(timetrend_line(ROWS), go.Figure)

    def test_has_four_traces(self):
        # total, pos, neg, neu
        fig = timetrend_line(ROWS)
        assert len(fig.data) == 4

    def test_x_values_are_dates(self):
        fig = timetrend_line(ROWS)
        total_trace = fig.data[0]
        assert list(total_trace.x) == ["2024-01-01", "2024-01-02", "2024-01-03"]

    def test_total_y_values(self):
        fig = timetrend_line(ROWS)
        assert list(fig.data[0].y) == [30, 45, 22]

    def test_indonesian_title_and_labels(self):
        fig = timetrend_line(ROWS)
        assert "WIB" in fig.layout.title.text
        assert "Tanggal" in fig.layout.xaxis.title.text
        assert "Komentar" in fig.layout.yaxis.title.text

    def test_empty_input_no_crash(self):
        fig = timetrend_line([])
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0

    def test_empty_has_annotation(self):
        fig = timetrend_line([])
        assert any("Belum ada data" in (a.text or "") for a in fig.layout.annotations)


# ---------------------------------------------------------------------------
# phrase_bar
# ---------------------------------------------------------------------------

class TestPhraseBar:
    def test_returns_figure(self):
        assert isinstance(phrase_bar(PHRASES), go.Figure)

    def test_has_one_bar_trace(self):
        fig = phrase_bar(PHRASES)
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Bar)

    def test_correct_number_of_bars(self):
        fig = phrase_bar(PHRASES)
        assert len(fig.data[0].y) == len(PHRASES)

    def test_highest_at_top(self):
        # After reversing, the last element of PHRASES (lowest count) should be first y-value
        fig = phrase_bar(PHRASES)
        # y is reversed so highest phrase is last in the list (top of horizontal bar)
        assert fig.data[0].y[-1] == PHRASES[0][0]

    def test_indonesian_title(self):
        fig = phrase_bar(PHRASES)
        assert "Frasa" in fig.layout.title.text

    def test_empty_input_no_crash(self):
        fig = phrase_bar([])
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0

    def test_empty_has_annotation(self):
        fig = phrase_bar([])
        assert any("Belum ada data" in (a.text or "") for a in fig.layout.annotations)


# ---------------------------------------------------------------------------
# word_freq_bar
# ---------------------------------------------------------------------------

class TestWordFreqBar:
    def test_returns_figure(self):
        assert isinstance(word_freq_bar(WORDS), go.Figure)

    def test_default_top_n_20(self):
        fig = word_freq_bar(WORDS)  # WORDS has 21 items
        assert len(fig.data[0].y) == 20

    def test_custom_top_n(self):
        fig = word_freq_bar(WORDS, top_n=5)
        assert len(fig.data[0].y) == 5

    def test_highest_at_top(self):
        fig = word_freq_bar(WORDS)
        # highest frequency word should be at the top (last in reversed y list)
        assert fig.data[0].y[-1] == WORDS[0][0]

    def test_indonesian_title(self):
        fig = word_freq_bar(WORDS)
        assert "Kata" in fig.layout.title.text or "Frekuensi" in fig.layout.title.text

    def test_top_n_larger_than_input(self):
        short = [("a", 3), ("b", 2)]
        fig = word_freq_bar(short, top_n=20)
        assert isinstance(fig, go.Figure)
        assert len(fig.data[0].y) == 2

    def test_empty_input_no_crash(self):
        fig = word_freq_bar([])
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0

    def test_empty_has_annotation(self):
        fig = word_freq_bar([])
        assert any("Belum ada data" in (a.text or "") for a in fig.layout.annotations)


# ---------------------------------------------------------------------------
# fig_to_html
# ---------------------------------------------------------------------------

class TestFigToHtml:
    def test_returns_str(self):
        fig = sentiment_pie(DIST)
        result = fig_to_html(fig)
        assert isinstance(result, str)

    def test_non_empty(self):
        fig = sentiment_pie(DIST)
        assert len(fig_to_html(fig)) > 0

    def test_contains_plotly_cdn_reference(self):
        fig = sentiment_pie(DIST)
        html = fig_to_html(fig)
        assert "plotly" in html.lower()

    def test_not_full_html(self):
        fig = sentiment_pie(DIST)
        html = fig_to_html(fig)
        assert "<html" not in html.lower()

    def test_works_with_all_chart_types(self):
        for fig in [
            sentiment_pie(DIST),
            timetrend_line(ROWS),
            phrase_bar(PHRASES),
            word_freq_bar(WORDS),
        ]:
            html = fig_to_html(fig)
            assert isinstance(html, str) and len(html) > 0

    def test_works_with_empty_figures(self):
        for fig in [
            sentiment_pie({}),
            timetrend_line([]),
            phrase_bar([]),
            word_freq_bar([]),
        ]:
            html = fig_to_html(fig)
            assert isinstance(html, str) and len(html) > 0
