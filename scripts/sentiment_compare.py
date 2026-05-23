"""Compare the two candidate sentiment models on YOUR real comments (risks.md R1).

Run after `uv sync --extra ml` (downloads both models on first run):

    uv run python -m scripts.sentiment_compare [N]

Prints a side-by-side so you can judge which model matches your audience's tone.
Rows where the two models DISAGREE are marked `<>` — those are the cases that
decide which model you trust. No DB writes; read-only.
"""

from __future__ import annotations

import random
import sys

from app.analysis.sentiment import classify_texts, is_analyzable
from app.config import settings
from app.db import connect, get_comments_in_scope


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    conn = connect()
    comments = [c for c in get_comments_in_scope(conn, "all") if is_analyzable(c.text)]
    conn.close()

    random.seed(42)
    sample = random.sample(comments, min(n, len(comments)))
    texts = [c.text for c in sample]

    a, b = settings.sentiment_model, settings.sentiment_model_fallback
    print(f"Model A = {a}")
    print(f"Model B = {b}")
    print(f"Sampling {len(sample)} analyzable comments...\n")

    la = classify_texts(texts, a)
    lb = classify_texts(texts, b)

    agree = 0
    for c, (al, _), (bl, _) in zip(sample, la, lb, strict=True):
        if al == bl:
            agree += 1
        mark = "  " if al == bl else "<>"
        print(f"{mark} A:{al:<8} B:{bl:<8} | {c.text[:70]!r}")

    pct = round(100 * agree / len(sample)) if sample else 0
    print(f"\nAgreement: {agree}/{len(sample)} ({pct}%). Rows marked <> are where they differ.")


if __name__ == "__main__":
    main()
