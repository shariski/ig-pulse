# syntax=docker/dockerfile:1
#
# IG Pulse runtime image. Built by GitHub Actions for linux/amd64 and pushed to
# ghcr.io/shariski/ig-pulse; the VPS only pulls (it lacks the disk/RAM to build
# a torch image). torch is the CPU build — see pyproject [tool.uv.sources].

FROM python:3.12-slim

# uv (pinned-ish via the official distroless image) for fast, lockfile-exact installs.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

# Chrome for kaleido v1 (Plotly PNG export). kaleido no longer bundles Chromium;
# the distro chromium package brings the binary + all its runtime libs via apt,
# and choreographer auto-discovers /usr/bin/chromium (run headless --no-sandbox).
# Early layer so it's cached across app changes. fonts-liberation = chart text.
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    NLTK_DATA=/usr/local/share/nltk_data \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1) Dependencies only — cached as long as pyproject.toml / uv.lock are unchanged.
#    --frozen guarantees we install exactly what's locked (CPU torch on linux).
#    --no-install-project: we run as `app.main:app` from /app, not as an installed wheel.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra ml

# 2) Bake the NLTK 'stopwords' corpus so the first request never hits the network
#    (app/analysis/stopwords.py calls nltk.download on a cold cache otherwise).
RUN python -c "import nltk; nltk.download('stopwords', download_dir='/usr/local/share/nltk_data')"

# 3) Smoke-test Plotly PNG export at build time so a broken Chrome/kaleido setup
#    fails CI instead of silently 500-ing the export downloads in production.
RUN python -c "import plotly.graph_objects as go; go.Figure().to_image(format='png')"

# 4) Application source.
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
