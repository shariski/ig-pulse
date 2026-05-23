"""Route smoke tests against a temp empty (migrated) DB — verifies the web wiring
(templates, routers) without depending on real fetched data. Catches integration
regressions like the Starlette TemplateResponse signature change."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "test.db")
    conn = db.connect()
    db.run_migrations(conn)
    conn.close()
    from app.main import app

    with TestClient(app) as c:  # `with` runs the lifespan (startup migrations)
        yield c


def test_dashboard_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Laporan percakapan" in r.text  # hero eyebrow
    assert "01 / 04" in r.text  # cards rendered


@pytest.mark.parametrize(
    "ep",
    [
        "/analysis/sentiment",
        "/analysis/wordfreq",
        "/analysis/timetrend",
        "/analysis/phrases",
        "/analysis/sentiment/sample?bucket=positive",
        "/export/sentiment",
    ],
)
def test_fragments_return_200_on_empty_db(client, ep):
    # Empty DB -> graceful empty states, never a 500.
    assert client.get(ep).status_code == 200


def test_scope_post_rerenders_grid(client):
    r = client.post("/scope", data={"scope_type": "all"})
    assert r.status_code == 200
    assert "01 / 04" in r.text  # grid re-rendered with the 4 cards


def test_unknown_export_is_404(client):
    assert client.get("/export/nonsense").status_code == 404
