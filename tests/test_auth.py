"""Tests for password hashing + (later) auth dependencies."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app import auth, registry
from app.auth import hash_password, verify_password


def test_hash_is_not_plaintext_and_verifies():
    h = hash_password("correct horse")
    assert h != "correct horse"
    assert h.startswith("$argon2")
    assert verify_password(h, "correct horse") is True


def test_verify_rejects_wrong_password():
    h = hash_password("s3cret-pass")
    assert verify_password(h, "wrong") is False


def test_hashes_are_salted_unique():
    assert hash_password("same") != hash_password("same")


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    c = registry.connect()
    registry.run_migrations(c)
    uid = registry.create_user(c, "alice", auth.hash_password("pw"))
    aid = registry.create_account(c, uid, "1", "alice_ig", "tok", None)
    other = registry.create_user(c, "bob", auth.hash_password("pw"))
    other_aid = registry.create_account(c, other, "2", "bob_ig", "tok2", None)
    c.close()

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")

    @app.exception_handler(auth._Redirect)
    async def _redir(request, exc):
        return RedirectResponse(exc.to, status_code=302)

    @app.get("/whoami")
    def whoami(user=auth.current_user):
        return PlainTextResponse(user["username"])

    @app.get("/acct")
    def acct(account=auth.current_account):
        return PlainTextResponse(str(account["id"]))

    @app.post("/setsession")
    def setsession(request: Request, uid: int, aid: int):
        request.session["user_id"] = uid
        request.session["account_id"] = aid
        return PlainTextResponse("ok")

    return TestClient(app), uid, aid, other_aid


def test_current_user_redirects_when_anonymous(app_client):
    client, *_ = app_client
    r = client.get("/whoami", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/login"


def test_current_account_blocks_foreign_account(app_client):
    client, uid, aid, other_aid = app_client
    client.post(f"/setsession?uid={uid}&aid={other_aid}")  # alice tries bob's account
    r = client.get("/acct", follow_redirects=False)
    assert r.status_code in (302, 307)  # ownership re-check fails -> redirect, not 200


def test_current_account_allows_own_account(app_client):
    client, uid, aid, other_aid = app_client
    client.post(f"/setsession?uid={uid}&aid={aid}")
    assert client.get("/acct").text == str(aid)
