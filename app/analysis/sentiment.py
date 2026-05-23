"""Sentiment analysis over comments using a multilingual transformer.

Sentiment is OPINION, not fact (CLAUDE.md B4). Canonical labels:
positive / negative / neutral / unanalyzed. Empty, emoji-only, or <3-char
comments are NEVER sent to the model — they get ``unanalyzed`` (B3: no silent
dropping, no fake-neutral).

Results are written to ``comment_analysis``. Idempotent: re-running only analyzes
comments that don't already have a row. The model is configurable
(``settings.sentiment_model``); the FINAL choice is made empirically against the
creator's own labels via scripts/sentiment_compare.py (risks.md R1, plan Phase 4).

``transformers``/``torch`` are imported lazily inside the inference helpers, so
this module (and its pure helpers ``is_analyzable`` / ``_canonical``) import fine
without the ML stack installed.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime

from app.config import settings
from app.db import connect, run_migrations

logger = logging.getLogger("ig_pulse.sentiment")

# Map each candidate model's raw labels -> our canonical set.
LABEL_MAPS: dict[str, dict[str, str]] = {
    "tabularisai/multilingual-sentiment-analysis": {
        "Very Negative": "negative",
        "Negative": "negative",
        "Neutral": "neutral",
        "Positive": "positive",
        "Very Positive": "positive",
    },
    "cardiffnlp/twitter-xlm-roberta-base-sentiment": {
        "negative": "negative",
        "neutral": "neutral",
        "positive": "positive",
        "LABEL_0": "negative",
        "LABEL_1": "neutral",
        "LABEL_2": "positive",
    },
}

MIN_CHARS = 3


def is_analyzable(text: str) -> bool:
    """A comment is analyzable only if it has >=3 chars AND some alphanumeric
    content. Emoji-only / blank / single-laugh comments are not (B3)."""
    t = (text or "").strip()
    return len(t) >= MIN_CHARS and any(ch.isalnum() for ch in t)


def _canonical(model_name: str, raw_label: str) -> str:
    """Map a model's raw label to positive/negative/neutral (default neutral)."""
    mapping = LABEL_MAPS.get(model_name, {})
    return mapping.get(raw_label) or mapping.get(raw_label.title(), "neutral")


def classify_texts(
    texts: list[str],
    model_name: str | None = None,
    *,
    batch_size: int = 32,
    revision: str | None = None,
) -> list[tuple[str, float]]:
    """Run the model over texts, returning (canonical_label, score) per text.

    Caller must pass only analyzable texts. Imports transformers lazily.
    """
    model_name = model_name or settings.sentiment_model
    from transformers import pipeline  # lazy: requires the `ml` extra

    clf = pipeline("sentiment-analysis", model=model_name, revision=revision, truncation=True)
    out: list[tuple[str, float]] = []
    for i in range(0, len(texts), batch_size):
        for r in clf(texts[i : i + batch_size]):
            out.append((_canonical(model_name, r["label"]), float(r["score"])))
    return out


def _upsert_analysis(
    conn: sqlite3.Connection,
    comment_id: str,
    label: str,
    score: float | None,
    model_name: str,
    model_version: str,
    analyzed_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO comment_analysis
            (comment_id, sentiment_label, sentiment_score, model_name, model_version, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(comment_id) DO UPDATE SET
            sentiment_label=excluded.sentiment_label,
            sentiment_score=excluded.sentiment_score,
            model_name=excluded.model_name,
            model_version=excluded.model_version,
            analyzed_at=excluded.analyzed_at
        """,
        (comment_id, label, score, model_name, model_version, analyzed_at),
    )


def analyze_comments(
    conn: sqlite3.Connection | None = None,
    model_name: str | None = None,
    *,
    batch_size: int = 32,
    revision: str | None = None,
) -> dict:
    """Analyze all not-yet-analyzed comments and write to comment_analysis.

    Idempotent: comments that already have an analysis row are skipped, so this
    can be re-run safely. Returns {analyzed, skipped}.
    """
    own = conn is None
    db = conn if conn is not None else connect()
    if own:
        run_migrations(db)
    model_name = model_name or settings.sentiment_model
    revision = revision or settings.sentiment_model_revision
    version = revision or "unpinned"

    rows = db.execute(
        """
        SELECT c.id, c.text FROM comments c
        LEFT JOIN comment_analysis a ON a.comment_id = c.id
        WHERE a.comment_id IS NULL
        """
    ).fetchall()

    analyzable = [(r["id"], r["text"]) for r in rows if is_analyzable(r["text"])]
    skipped = [r["id"] for r in rows if not is_analyzable(r["text"])]
    now = datetime.now(UTC).isoformat()

    for cid in skipped:
        _upsert_analysis(db, cid, "unanalyzed", None, model_name, version, now)

    if analyzable:
        labels = classify_texts(
            [t for _, t in analyzable], model_name, batch_size=batch_size, revision=revision
        )
        for (cid, _), (label, score) in zip(analyzable, labels, strict=True):
            _upsert_analysis(db, cid, label, score, model_name, version, now)

    db.commit()
    logger.info(
        "sentiment: analyzed=%d skipped=%d model=%s", len(analyzable), len(skipped), model_name
    )
    result = {"analyzed": len(analyzable), "skipped": len(skipped)}
    if own:
        db.close()
    return result
