from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import registry


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(registry.settings, "register_code", None)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_register_creates_user_and_redirects(client):
    r = client.post("/register", data={"username": "alice", "password": "password1",
                                       "confirm": "password1"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/accounts"
    # user persisted -> same username again errors
    r2 = client.post("/register", data={"username": "alice", "password": "password1",
                                        "confirm": "password1"})
    assert r2.status_code == 200 and "dipakai" in r2.text.lower()


def test_register_password_mismatch(client):
    r = client.post("/register", data={"username": "x", "password": "aaaaaaaa",
                                       "confirm": "bbbbbbbb"})
    assert r.status_code == 200 and "sandi" in r.text.lower()


def test_login_roundtrip_and_wrong_password(client):
    client.post("/register", data={"username": "joe", "password": "password1",
                                   "confirm": "password1"})
    client.get("/logout")
    bad = client.post("/login", data={"username": "joe", "password": "nope"})
    assert bad.status_code == 200 and "salah" in bad.text.lower()
    good = client.post("/login", data={"username": "joe", "password": "password1"},
                       follow_redirects=False)
    assert good.status_code == 302 and good.headers["location"] == "/accounts"
