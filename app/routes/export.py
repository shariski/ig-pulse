"""Export routes: a format-picker modal + the PNG download (B8).

Reuses the same analysis + render + export modules as the dashboard fragments,
so an exported PNG is exactly what's on screen, just at Instagram dimensions.
"""

from __future__ import annotations

import logging
from collections import Counter

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.analysis import phrases, timetrend, wordfreq
from app.render import charts, export
from app.render import wordcloud as wc_render
from app.routes.analysis import scope_data
from app.templating import templates

router = APIRouter()
logger = logging.getLogger("ig_pulse.routes.export")

CHART_NAMES = {"sentiment", "wordfreq", "timetrend", "phrases"}


@router.get("/export/{name}", response_class=HTMLResponse)
def export_modal(
    request: Request, name: str, scope_type: str = "all", scope_value: str | None = None
):
    if name not in CHART_NAMES:
        return HTMLResponse("", status_code=404)
    qs = f"scope_type={scope_type}" + (f"&scope_value={scope_value}" if scope_value else "")
    return templates.TemplateResponse(
        request, "partials/_export_modal.html", {"name": name, "scope_qs": qs}
    )


@router.get("/export/{name}/download")
def export_download(
    name: str, fmt: str = "square", scope_type: str = "all", scope_value: str | None = None
):
    if name not in CHART_NAMES:
        return Response("unknown chart", status_code=404)
    comments, analyses = scope_data(scope_type, scope_value)
    try:
        if name == "sentiment":
            dist = Counter(analyses.get(c.id, "unanalyzed") for c in comments)
            png = export.figure_to_png(charts.sentiment_pie(dict(dist)), fmt)
        elif name == "timetrend":
            fig = charts.timetrend_line(timetrend.daily_trend(comments, analyses))
            png = export.figure_to_png(fig, fmt)
        elif name == "phrases":
            png = export.figure_to_png(charts.phrase_bar(phrases.top_phrases(comments)), fmt)
        else:  # wordfreq
            img = wc_render.render_wordcloud(wordfreq.word_frequencies(comments, 100))
            png = export.image_to_png(img, fmt)
    except ValueError as e:
        return Response(str(e), status_code=400)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="ig-pulse-{name}-{fmt}.png"'},
    )
