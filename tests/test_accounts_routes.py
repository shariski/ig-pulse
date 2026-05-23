from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import registry


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    from app.main import app
    with TestClient(app) as c:
        c.post("/register", data={"username": "al", "password": "password1", "confirm": "password1"})  # noqa: E501
        yield c


def test_accounts_page_has_add_form(client):
    r = client.get("/accounts")
    assert r.status_code == 200
    assert "Hubungkan" in r.text  # add-account form present


def test_switch_foreign_blocked(client):
    conn = registry.connect()
    other = registry.create_user(conn, "ev", "h")
    foreign = registry.create_account(conn, other, "9", "ev_ig", "t", None)
    conn.close()
    r = client.post("/accounts/switch", data={"account_id": foreign}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/accounts"  # blocked


def test_switch_own_ok(client):
    conn = registry.connect()
    uid = registry.get_user_by_name(conn, "al")["id"]
    mine = registry.create_account(conn, uid, "5", "al_ig", "t", None)
    conn.close()
    r = client.post("/accounts/switch", data={"account_id": mine}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/"


def test_add_account_creates(client, monkeypatch):
    from app import ig_setup

    monkeypatch.setattr(
        "app.routes.accounts.discover_account",
        lambda short_token, **kw: ig_setup.AccountInfo(  # noqa: E501
            "IG1", "myhandle", "LONGTOK", "2026-07-01T00:00:00Z"
        ),
    )
    monkeypatch.setattr("app.routes.accounts._kickoff_fetch", lambda *a, **k: None)
    r = client.post("/accounts/add", data={"short_token": "SHORT"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/"
    conn = registry.connect()
    accts = registry.list_accounts(conn, registry.get_user_by_name(conn, "al")["id"])
    conn.close()
    assert len(accts) == 1 and accts[0]["username"] == "myhandle"
